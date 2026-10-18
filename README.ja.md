# HefestoAI — AI が書いたコードのためのリリース検証エンジン

[English](README.md) | [简体中文](README.zh-CN.md) | **日本語**

> これは英語版 README の簡約翻訳です。内容に差異がある場合は [README.md](README.md) が優先されます。

HefestoAI は、AI アシスタントがコードを書いた後、そのコードが出荷される前に実行されます。プロジェクトが宣言している内容（依存関係、設定、インストール成果物）が実際の動作と一致しているかを確認し、コード自体のセキュリティと複雑度もチェックします。

オープンソース（MIT）、Python 3.10 以上。パッケージには 22 フォーマットのアナライザー（コード言語 7 + DevOps フォーマット 11 + クラウドフォーマット 4）が含まれ、`hefesto analyze` は 22 すべてを実行します。

## インストール

```bash
pip install hefesto-ai

# TypeScript、JavaScript、Java、Go、Rust、C# の解析には：
pip install "hefesto-ai[multilang]"
```

## クイックスタート

```bash
cd your-project
hefesto analyze . --fail-on critical

# PR レビュー：変更されたコードだけを解析
hefesto pr-review
hefesto pr-review --post --pr 42  # gh CLI でインラインコメントを投稿
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

検出結果は **Security > Code scanning** と PR のアノテーションに表示されます。`@v4` はすべての 4.x リリースに追従します。バージョンを固定する場合は `artvepa80/Agents-Hefesto@v4.20.2` またはコミット SHA を指定してください。Action は `hefesto analyze` と同じ形式を解析します：Python、YAML、Terraform、Shell、Dockerfile、SQL、PowerShell、JSON、TOML、Makefile、Groovy、COBOL、CloudFormation、ARM、Helm、Serverless とドリフトチェック。TypeScript、JavaScript、Java、Go、Rust、C# は CLI と `hefesto-ai[multilang]` が必要です。

## 検出内容（例）

| 問題 | 重大度 |
|------|--------|
| HARDCODED_SECRET（コード内の API キー、パスワード） | CRITICAL |
| SQL_INJECTION_RISK | HIGH |
| COMMAND_INJECTION | HIGH |
| PICKLE_USAGE（`pickle` / `cPickle` の import 行。`pickle.loads()` の呼び出しは個別に指摘しません） | HIGH |
| UNDECLARED_DEPENDENCY（import されているが pyproject.toml に未宣言） | MEDIUM |
| PACKAGING_VERSION_DRIFT（pyproject、CHANGELOG、README のバージョン不一致） | MEDIUM |

## MCP サーバー

AI エージェントは MCP 経由で HefestoAI を呼び出せます：

```bash
npx @smithery/cli@latest mcp add artvepa80/hefestoai
```

Cursor にワンクリックで追加：

[![Add HefestoAI MCP server to Cursor](https://cursor.com/deeplink/mcp-install-dark.svg)](https://cursor.com/link/mcp/install?name=hefestoai&config=eyJ1cmwiOiJodHRwczovL2hlZmVzdG9haS5uYXJhcGFsbGMuY29tL2FwaS9tY3AtcHJvdG9jb2wifQ%3D%3D)

ボタンは `cursor.com/link` 経由で Cursor のインストール画面を開きます（GitHub は `cursor://` リンクを表示しません）。直接のディープリンク：`cursor://anysphere.cursor-deeplink/mcp/install?name=hefestoai&config=eyJ1cmwiOiJodHRwczovL2hlZmVzdG9haS5uYXJhcGFsbGMuY29tL2FwaS9tY3AtcHJvdG9jb2wifQ%3D%3D`。同じサーバーはリポジトリ直下の `.mcp.json` にもあります。API キーは不要です。

MCP エンドポイント：`https://hefestoai.narapallc.com/api/mcp-protocol`（JSON-RPC 2.0）。MCP の `analyze` ツールは、送信されたファイルに対してオープンソースエンジンを実行します（ホスト型 MCP は最近の hefesto-ai リリースを実行します）。上限は 20 ファイル、各 100 KB、合計 256 KB、20 秒です。内容は保存されません。リポジトリ全体はローカルで `hefesto analyze .` を実行してください。ホスト型 MCP サーバーはクローズドソースで、Narapa LLC が運営しています。

## 対応言語

- コード：Python（ネイティブ AST、フルサポート）、TypeScript、JavaScript、Java、Go、Rust、C#（TreeSitter、`[multilang]` が必要）
- `hefesto analyze` が実行する DevOps / クラウドフォーマット：YAML、Terraform、Shell、Dockerfile、SQL、PowerShell、JSON、TOML、Makefile、Groovy、COBOL（無料ルール 16 個、COBOL001–COBOL016）、CloudFormation、ARM、Helm、Serverless。接尾辞が重なるときの優先順位は [docs/design/devops-analyzers-wiring.md](https://github.com/artvepa80/Agents-Hefesto/blob/main/docs/design/devops-analyzers-wiring.md)。

## テレメトリ

CLI は初期設定で匿名の利用データを PostHog に送信します（ランダムな ID。`analyze` ではファイル数、指摘数、実行時間、終了コード、バージョン、OS、Python のバージョンも送ります。コード、ファイルパス、指摘内容、リポジトリ名は含みません）。`hefesto telemetry disable`、`HEFESTO_TELEMETRY=0`、`DO_NOT_TRACK=1` のいずれかで止められます。GitHub Action は `telemetry: 1` を指定した場合のみ利用データを送ります。また `hefesto analyze` は pypi.org に最新バージョンを問い合わせます（タイムアウト 1.5 秒、24 時間キャッシュ）。この確認はテレメトリを止めても動き、4.20.1 には止める設定がありません。詳細：[docs/telemetry.md](https://github.com/artvepa80/Agents-Hefesto/blob/main/docs/telemetry.md)

## 料金

無料・オープンソース（MIT）。PRO は月額 8 ドル、OMEGA は月額 19 ドルです。詳細：[hefestoai.narapallc.com](https://hefestoai.narapallc.com/?utm_source=github&utm_medium=readme&utm_campaign=growth_q4_2026&utm_content=pricing_ja#pricing)

## リンク

- サイト：[hefestoai.narapallc.com](https://hefestoai.narapallc.com/?utm_source=github&utm_medium=readme&utm_campaign=growth_q4_2026&utm_content=readme_ja)
- PyPI：[hefesto-ai](https://pypi.org/project/hefesto-ai/)
- 完全なドキュメント（英語）：[README.md](README.md)
