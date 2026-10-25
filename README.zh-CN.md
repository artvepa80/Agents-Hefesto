# HefestoAI — 面向 AI 生成代码的发布真实性检查引擎

[English](README.md) | **简体中文** | [日本語](README.ja.md)

> 本文是英文 README 的精简译本。如有出入，以 [README.md](README.md) 为准。

HefestoAI 在 AI 助手写完代码之后、代码发布之前运行。它检查项目所声明的内容（依赖、配置、安装产物）是否与实际行为一致，并对代码本身执行安全和复杂度检查。

开源（MIT），支持 Python 3.10+。软件包提供 22 种格式的分析器（7 种代码语言 + 11 种 DevOps 格式 + 4 种云格式）；`hefesto analyze` 会运行全部 22 种。

## 安装

```bash
pip install hefesto-ai

# 分析 TypeScript、JavaScript、Java、Go、Rust、C# 需要：
pip install "hefesto-ai[multilang]"
```

## 快速开始

```bash
cd your-project
hefesto analyze . --fail-on critical

# PR 审查：只分析变更的代码
hefesto pr-review
hefesto pr-review --post --pr 42  # 通过 gh CLI 发布行内评论
```

## GitHub Action

```yaml
# .github/workflows/hefesto.yml
name: HefestoAI
on: [pull_request, push]
permissions:
  contents: read
  security-events: write
jobs:
  hefesto:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: artvepa80/Agents-Hefesto@v4
        with:
          fail_on: HIGH
          sarif: 'true'
```

检查结果显示在 **Security > Code scanning** 和 PR 注释中。`@v4` 跟随所有 4.x 版本；如需固定版本，请使用 `artvepa80/Agents-Hefesto@v4.20.3` 或提交 SHA。Action 分析的格式与 `hefesto analyze` 相同：Python、YAML、Terraform、Shell、Dockerfile、SQL、PowerShell、JSON、TOML、Makefile、Groovy、COBOL、CloudFormation、ARM、Helm 和 Serverless，以及漂移检查；TypeScript、JavaScript、Java、Go、Rust 和 C# 需要使用 CLI 并安装 `hefesto-ai[multilang]`。

## 检查内容（示例）

| 问题 | 严重级别 |
|------|----------|
| HARDCODED_SECRET（代码中的 API 密钥、密码） | CRITICAL |
| SQL_INJECTION_RISK | HIGH |
| COMMAND_INJECTION | HIGH |
| PICKLE_USAGE（导入 `pickle` / `cPickle` 的那一行；不单独标出 `pickle.loads()` 调用） | HIGH |
| UNDECLARED_DEPENDENCY（导入了但未在 pyproject.toml 中声明） | MEDIUM |
| PACKAGING_VERSION_DRIFT（pyproject、CHANGELOG、README 版本不一致） | MEDIUM |

## MCP 服务器

AI 代理可以通过 MCP 调用 HefestoAI：

```bash
npx @smithery/cli@latest mcp add artvepa80/hefestoai
```

一键添加到 Cursor：

[![Add HefestoAI MCP server to Cursor](https://cursor.com/deeplink/mcp-install-dark.svg)](https://cursor.com/link/mcp/install?name=hefestoai&config=eyJ1cmwiOiJodHRwczovL2hlZmVzdG9haS5uYXJhcGFsbGMuY29tL2FwaS9tY3AtcHJvdG9jb2wifQ%3D%3D)

按钮通过 `cursor.com/link` 打开 Cursor 的安装提示（GitHub 不渲染 `cursor://` 链接）。直接深度链接：`cursor://anysphere.cursor-deeplink/mcp/install?name=hefestoai&config=eyJ1cmwiOiJodHRwczovL2hlZmVzdG9haS5uYXJhcGFsbGMuY29tL2FwaS9tY3AtcHJvdG9jb2wifQ%3D%3D`。同一服务器也写在仓库根目录的 `.mcp.json` 中。无需 API 密钥。

MCP 端点：`https://hefestoai.narapallc.com/api/mcp-protocol`（JSON-RPC 2.0）。MCP 的 `analyze` 工具运行开源引擎（托管的 MCP 运行近期的 hefesto-ai 版本），处理你发送的文件：最多 20 个文件，每个 100 KB，总计 256 KB，20 秒。不存储任何内容。分析整个仓库请在本地运行 `hefesto analyze .`。托管的 MCP 服务器为闭源，由 Narapa LLC 运营。

## 支持的语言

- 代码：Python（原生 AST，完整支持）、TypeScript、JavaScript、Java、Go、Rust、C#（TreeSitter，需要 `[multilang]`）
- `hefesto analyze` 运行的 DevOps 与云格式：YAML、Terraform、Shell、Dockerfile、SQL、PowerShell、JSON、TOML、Makefile、Groovy、COBOL（16 条免费规则，COBOL001–COBOL016）、CloudFormation、ARM、Helm、Serverless。后缀重叠时的优先级见 [docs/design/devops-analyzers-wiring.md](https://github.com/artvepa80/Agents-Hefesto/blob/main/docs/design/devops-analyzers-wiring.md)。

## 遥测

CLI 默认向 PostHog 发送假名化使用数据（随机安装 ID）（随机 ID；`analyze` 还会发送文件数、问题数、耗时、退出码、版本、操作系统和 Python 版本；不含代码、文件路径、检查结果和仓库名）。可用 `hefesto telemetry disable`、`HEFESTO_TELEMETRY=0` 或 `DO_NOT_TRACK=1` 关闭。GitHub Action 只有设置 `telemetry: 1` 才发送使用数据。另外，`hefesto analyze` 会向 pypi.org 查询最新版本（超时 1.5 秒，缓存 24 小时），`hefesto telemetry disable` 不会停止这项检查。从 4.20.3 起，设置 `HEFESTO_NO_UPDATE_CHECK=1`、`HEFESTO_TELEMETRY=0` 或 `DO_NOT_TRACK=1` 即可跳过（4.20.2 及更早版本没有关闭它的设置）。详情：[docs/telemetry.md](https://github.com/artvepa80/Agents-Hefesto/blob/main/docs/telemetry.md)

## 价格

免费且开源（MIT）。PRO 每月 8 美元，OMEGA 每月 19 美元。详情：[hefestoai.narapallc.com](https://hefestoai.narapallc.com/?utm_source=github&utm_medium=readme&utm_campaign=growth_q4_2026&utm_content=pricing_zh#pricing)

## 链接

- 网站：[hefestoai.narapallc.com](https://hefestoai.narapallc.com/?utm_source=github&utm_medium=readme&utm_campaign=growth_q4_2026&utm_content=readme_zh)
- PyPI：[hefesto-ai](https://pypi.org/project/hefesto-ai/)
- 完整文档（英文）：[README.md](README.md)
