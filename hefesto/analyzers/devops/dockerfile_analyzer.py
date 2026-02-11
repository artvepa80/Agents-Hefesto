"""
Dockerfile Analyzer for Hefesto DevOps Support (internal).

Detects container hardening and supply-chain issues with low false-positive bias:
- Non-pinned base images (:latest / missing tag)
- Remote script execution during build (curl|sh / wget|bash)
- Secret exposure (ARG/ENV + known token patterns; COPY of sensitive files)
- Privilege escalation (USER root / missing USER)
- Weak permissions (chmod 777 / 666)

Copyright 2025 Narapa LLC, Miami, Florida
"""

import re
from typing import List, Optional, Tuple

from hefesto.core.analysis_models import (
    AnalysisIssue,
    AnalysisIssueSeverity,
    AnalysisIssueType,
)


class _DockerContext:
    def __init__(self):
        self.has_from = False
        self.last_user = None
        self.has_any_user = False
        self.issues: List[AnalysisIssue] = []

    def add_issue(self, issue: AnalysisIssue):
        self.issues.append(issue)


class DockerfileAnalyzer:
    ENGINE = "internal:dockerfile_analyzer"

    RE_FROM = re.compile(r"^\s*FROM\s+(?P<img>\S+)", re.IGNORECASE)

    RUN_RCE_PATTERNS: List[Tuple[re.Pattern, str, float, AnalysisIssueSeverity, str]] = [
        (
            re.compile(
                r"^\s*RUN\s+.*\b(curl|wget)\b[^\n]*\|\s*(sh|bash)\b",
                re.IGNORECASE,
            ),
            "Remote script piped to shell during build (RCE/supply-chain risk)",
            0.97,
            AnalysisIssueSeverity.CRITICAL,
            "DOCKER010",
        ),
        (
            re.compile(
                r"^\s*RUN\s+.*\b(curl|wget)\b[^\n]*(sh\s+-c|bash\s+-c)\b",
                re.IGNORECASE,
            ),
            "Remote content executed via shell -c during build (supply-chain risk)",
            0.90,
            AnalysisIssueSeverity.HIGH,
            "DOCKER011",
        ),
    ]

    ADD_REMOTE = (
        re.compile(r"^\s*ADD\s+https?://", re.IGNORECASE),
        "ADD from remote URL is non-reproducible and bypasses verification",
        0.88,
        AnalysisIssueSeverity.HIGH,
        "DOCKER012",
    )

    SECRET_STRICT: List[Tuple[re.Pattern, str, float, AnalysisIssueSeverity, str]] = [
        (
            re.compile(r"\b(AKIA|ASIA|AIDA)[0-9A-Z]{16}\b"),
            "AWS Access Key ID appears in Dockerfile",
            0.98,
            AnalysisIssueSeverity.CRITICAL,
            "DOCKER020",
        ),
        (
            re.compile(r"\bghp_[A-Za-z0-9]{36}\b"),
            "GitHub token appears in Dockerfile",
            0.98,
            AnalysisIssueSeverity.CRITICAL,
            "DOCKER021",
        ),
        (
            re.compile(r"\bsk-[A-Za-z0-9]{20,}\b"),
            "API key appears in Dockerfile",
            0.95,
            AnalysisIssueSeverity.CRITICAL,
            "DOCKER022",
        ),
    ]

    SECRET_GENERIC: List[Tuple[re.Pattern, str, float, AnalysisIssueSeverity, str]] = [
        (
            re.compile(
                r"^\s*(ARG|ENV)\s+\w*(PASSWORD|SECRET|TOKEN|API_KEY|PRIVATE)\w*\b",
                re.IGNORECASE,
            ),
            "Potential secret declared in ARG/ENV (visible in build args/image history)",
            0.88,
            AnalysisIssueSeverity.HIGH,
            "DOCKER023",
        ),
    ]

    COPY_SENSITIVE: List[Tuple[re.Pattern, str, float, AnalysisIssueSeverity, str]] = [
        (
            re.compile(
                r"^\s*COPY\s+.*\b("
                r"\.env|\.pem|\.key|id_rsa|id_ed25519|credentials|\.npmrc|\.pypirc|\.netrc"
                r")\b",
                re.IGNORECASE,
            ),
            "Sensitive file copied into image",
            0.92,
            AnalysisIssueSeverity.HIGH,
            "DOCKER024",
        ),
    ]

    PERMS: List[Tuple[re.Pattern, str, float, AnalysisIssueSeverity, str]] = [
        (
            re.compile(
                r"^\s*RUN\s+.*\bchmod\b[^\n]*\b777\b",
                re.IGNORECASE,
            ),
            "chmod 777 grants world-writable permissions",
            0.95,
            AnalysisIssueSeverity.HIGH,
            "DOCKER030",
        ),
        (
            re.compile(
                r"^\s*RUN\s+.*\bchmod\b[^\n]*\b666\b",
                re.IGNORECASE,
            ),
            "chmod 666 grants world-writable file permissions",
            0.85,
            AnalysisIssueSeverity.MEDIUM,
            "DOCKER031",
        ),
    ]

    RE_USER = re.compile(r"^\s*USER\s+(?P<user>\S+)", re.IGNORECASE)

    def analyze(self, file_path: str, content: str) -> List[AnalysisIssue]:
        ctx = _DockerContext()
        lines = content.split("\n")

        for line_num, raw in enumerate(lines, start=1):
            line = raw.strip()
            if not line or line.startswith("#"):
                continue

            self._analyze_line(ctx, file_path, line_num, raw, line)

        self._check_final_state(ctx, file_path, lines)
        return ctx.issues

    def _analyze_line(
        self, ctx: _DockerContext, file_path: str, line_num: int, raw: str, line: str
    ):
        if self._check_from(ctx, file_path, line_num, raw, line):
            pass

        if self._check_user(ctx, line):
            pass

        self._check_remote(ctx, file_path, line_num, raw, line)
        self._check_rce(ctx, file_path, line_num, raw, line)
        self._check_secrets(ctx, file_path, line_num, raw, line)
        self._check_perms(ctx, file_path, line_num, raw, line)

    def _check_from(
        self, ctx: _DockerContext, file_path: str, line_num: int, raw: str, line: str
    ) -> bool:
        m_from = self.RE_FROM.match(line)
        if not m_from:
            return False

        ctx.has_from = True
        image_ref = m_from.group("img")
        if image_ref.startswith("$"):
            return True

        if image_ref.lower().endswith(":latest"):
            ctx.add_issue(
                self._create_issue(
                    file_path,
                    line_num,
                    1,
                    AnalysisIssueType.DOCKERFILE_LATEST_TAG,
                    AnalysisIssueSeverity.HIGH,
                    "Using :latest tag is non-reproducible and risky",
                    "Pin to a specific tag or digest (e.g., python:3.11-slim)",
                    0.95,
                    "DOCKER002",
                    raw,
                    extra={"image": image_ref},
                )
            )
        elif ":" not in image_ref and "@" not in image_ref and image_ref.lower() != "scratch":
            ctx.add_issue(
                self._create_issue(
                    file_path,
                    line_num,
                    1,
                    AnalysisIssueType.DOCKERFILE_LATEST_TAG,
                    AnalysisIssueSeverity.MEDIUM,
                    f"No tag specified for '{image_ref}' (defaults to latest)",
                    f"Add explicit version tag (e.g., {image_ref}:<version>)",
                    0.85,
                    "DOCKER003",
                    raw,
                    extra={"image": image_ref},
                )
            )
        return True

    def _check_user(self, ctx: _DockerContext, line: str) -> bool:
        m_user = self.RE_USER.match(line)
        if m_user:
            ctx.has_any_user = True
            ctx.last_user = m_user.group("user")
            return True
        return False

    def _check_remote(
        self, ctx: _DockerContext, file_path: str, line_num: int, raw: str, line: str
    ):
        if self.ADD_REMOTE[0].search(line):
            ctx.add_issue(
                self._create_issue(
                    file_path,
                    line_num,
                    1,
                    AnalysisIssueType.DOCKERFILE_INSECURE_BASE_IMAGE,
                    self.ADD_REMOTE[3],
                    self.ADD_REMOTE[1],
                    "Prefer COPY local files or download with checksum in RUN",
                    self.ADD_REMOTE[2],
                    self.ADD_REMOTE[4],
                    raw,
                )
            )

    def _check_rce(self, ctx: _DockerContext, file_path: str, line_num: int, raw: str, line: str):
        for pat, msg, conf, sev, rid in self.RUN_RCE_PATTERNS:
            mm = pat.search(line)
            if mm:
                ctx.add_issue(
                    self._create_issue(
                        file_path,
                        line_num,
                        mm.start() + 1,
                        AnalysisIssueType.DOCKERFILE_INSECURE_BASE_IMAGE,
                        sev,
                        msg,
                        "Download first, verify checksum, then execute.",
                        conf,
                        rid,
                        raw,
                    )
                )
                break

    def _check_secrets(
        self, ctx: _DockerContext, file_path: str, line_num: int, raw: str, line: str
    ):
        # Strict secrets
        for pat, msg, conf, sev, rid in self.SECRET_STRICT:
            mm = pat.search(line)
            if mm:
                ctx.add_issue(
                    self._create_issue(
                        file_path,
                        line_num,
                        mm.start() + 1,
                        AnalysisIssueType.DOCKERFILE_SECRET_EXPOSURE,
                        sev,
                        msg,
                        "Do not bake secrets into images. Use runtime secrets.",
                        conf,
                        rid,
                        raw,
                    )
                )
                return

        # Generic secrets
        for pat, msg, conf, sev, rid in self.SECRET_GENERIC:
            mm = pat.search(line)
            if mm:
                ctx.add_issue(
                    self._create_issue(
                        file_path,
                        line_num,
                        mm.start() + 1,
                        AnalysisIssueType.DOCKERFILE_SECRET_EXPOSURE,
                        sev,
                        msg,
                        "Avoid ARG/ENV secrets. Use runtime secret injection.",
                        conf,
                        rid,
                        raw,
                    )
                )
                return

        # Sensitive COPY
        for pat, msg, conf, sev, rid in self.COPY_SENSITIVE:
            mm = pat.search(line)
            if mm:
                ctx.add_issue(
                    self._create_issue(
                        file_path,
                        line_num,
                        mm.start() + 1,
                        AnalysisIssueType.DOCKERFILE_SECRET_EXPOSURE,
                        sev,
                        msg,
                        "Remove sensitive files from build context.",
                        conf,
                        rid,
                        raw,
                    )
                )
                return

    def _check_perms(self, ctx: _DockerContext, file_path: str, line_num: int, raw: str, line: str):
        for pat, msg, conf, sev, rid in self.PERMS:
            mm = pat.search(line)
            if mm:
                ctx.add_issue(
                    self._create_issue(
                        file_path,
                        line_num,
                        mm.start() + 1,
                        AnalysisIssueType.DOCKERFILE_WEAK_PERMISSIONS,
                        sev,
                        msg,
                        "Use least-privilege perms (e.g., 644 files, 755 dirs).",
                        conf,
                        rid,
                        raw,
                    )
                )
                break

    def _check_final_state(self, ctx: _DockerContext, file_path: str, lines: List[str]):
        if ctx.has_from and not ctx.has_any_user:
            ctx.add_issue(
                self._create_issue(
                    file_path,
                    1,
                    1,
                    AnalysisIssueType.DOCKERFILE_MISSING_USER,
                    AnalysisIssueSeverity.MEDIUM,
                    "No USER instruction - container runs as root by default",
                    "Add a non-root user and set USER for the final stage.",
                    0.80,
                    "DOCKER001",
                    lines[0] if lines else "",
                )
            )
        elif ctx.has_from and ctx.last_user is not None and ctx.last_user.lower() in ("root", "0"):
            ctx.add_issue(
                self._create_issue(
                    file_path,
                    1,
                    1,
                    AnalysisIssueType.DOCKERFILE_PRIVILEGE_ESCALATION,
                    AnalysisIssueSeverity.HIGH,
                    "Final USER is root - privilege escalation risk",
                    "Switch to a non-root user for runtime.",
                    0.85,
                    "DOCKER004",
                    f"USER {ctx.last_user}",
                    extra={"user": ctx.last_user},
                )
            )

    def _create_issue(
        self,
        file_path: str,
        line: int,
        column: int,
        issue_type: AnalysisIssueType,
        severity: AnalysisIssueSeverity,
        message: str,
        suggestion: str,
        confidence: float,
        rule_id: str,
        line_content: str,
        extra: Optional[dict] = None,
    ) -> AnalysisIssue:
        md = {"line_content": (line_content or "").strip()[:200]}
        if extra:
            md.update(extra)
        return AnalysisIssue(
            file_path=file_path,
            line=line,
            column=column,
            issue_type=issue_type,
            severity=severity,
            message=message,
            suggestion=suggestion,
            engine=self.ENGINE,
            confidence=confidence,
            rule_id=rule_id,
            metadata=md,
        )


__all__ = ["DockerfileAnalyzer"]
