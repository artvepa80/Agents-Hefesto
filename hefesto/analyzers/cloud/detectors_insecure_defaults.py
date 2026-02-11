from dataclasses import dataclass
from ipaddress import ip_network
from typing import Any, ClassVar, Optional, Tuple


@dataclass(frozen=True)
class InsecureDefaultsDetector:
    """
    Shared logic used by IaC analyzers + drift detectors to classify insecure defaults.
    Keep this deterministic and dependency-free.
    """

    # You can tune this list as you learn from customers:
    SENSITIVE_PORTS: ClassVar[Tuple[int, ...]] = (
        22,  # SSH
        23,  # Telnet
        3389,  # RDP
        5432,  # Postgres
        3306,  # MySQL
        6379,  # Redis
        27017,  # MongoDB
    )

    @staticmethod
    def is_public_cidr(cidr: str) -> bool:
        """
        Returns True for internet-routable CIDRs.
        Treat 0.0.0.0/0 and ::/0 as public.
        Also treat "all" / very broad networks as public.

        Deterministic: uses ipaddress parsing; invalid CIDRs => False.
        """
        try:
            net = ip_network(cidr, strict=False)
        except Exception:
            return False

        # explicit global-any
        if str(net) in ("0.0.0.0/0", "::/0"):
            return True

        # Private, loopback, link-local, multicast, reserved should NOT be treated as public.
        # ipaddress has flags that map to RFC sets.
        if getattr(net, "is_private", False):
            return False
        if getattr(net, "is_loopback", False):
            return False
        if getattr(net, "is_link_local", False):
            return False
        if getattr(net, "is_multicast", False):
            return False
        if getattr(net, "is_reserved", False):
            return False

        # If it's global, treat as public.
        # Some ipaddress versions expose is_global; guard with getattr.
        if getattr(net, "is_global", False):
            return True

        # Fallback: if it isn't clearly private/etc, consider it public-ish.
        return True

    @classmethod
    def is_sensitive_port(cls, port: Any) -> bool:
        """
        Treats None/invalid as non-sensitive; ports in SENSITIVE_PORTS are sensitive.
        Also treat very low ports (<=1024) as potentially sensitive? (No — keep deterministic.)
        """
        try:
            p = int(port)
        except Exception:
            return False
        return p in cls.SENSITIVE_PORTS

    @staticmethod
    def is_wildcard_permission(value: Any) -> bool:
        """
        Detect wildcard patterns in IAM-like statements:
        Action: "*" or "service:*"
        Resource: "*" or "arn:aws:*:*:*:*" style wide wildcard
        """
        if value is None:
            return False

        if isinstance(value, str):
            v = value.strip()
            return v == "*" or v.endswith(":*")

        if isinstance(value, (list, tuple, set)):
            return any(InsecureDefaultsDetector.is_wildcard_permission(v) for v in value)

        return False

    @classmethod
    def is_public_and_sensitive_rule(
        cls,
        proto: str,
        from_port: Any,
        to_port: Any,
        cidr4: Optional[str],
        cidr6: Optional[str],
    ) -> bool:
        """
        Used for drift severity:
        CRITICAL only if (public) AND (sensitive).
        """
        is_sensitive = False
        if str(proto) == "-1":
            is_sensitive = True
        else:
            is_sensitive = cls.is_sensitive_port(from_port) or cls.is_sensitive_port(to_port)

        is_public = False
        if cidr4 and cls.is_public_cidr(cidr4):
            is_public = True
        if cidr6 and cls.is_public_cidr(cidr6):
            is_public = True

        return is_sensitive and is_public

    @classmethod
    def is_sg_rule_public(cls, cidr4: Optional[str], cidr6: Optional[str]) -> bool:
        if cidr4 and cls.is_public_cidr(cidr4):
            return True
        if cidr6 and cls.is_public_cidr(cidr6):
            return True
        return False

    @classmethod
    def classify_sg_unexpected_severity(
        cls,
        proto: str,
        from_port: Any,
        to_port: Any,
        cidr4: Optional[str],
        cidr6: Optional[str],
    ) -> str:
        """
        CRITICAL only if public+sensitive, else HIGH (per your ship criteria).
        """
        if cls.is_public_and_sensitive_rule(proto, from_port, to_port, cidr4, cidr6):
            return "CRITICAL"
        return "HIGH"
