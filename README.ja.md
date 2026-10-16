# HefestoAI — AI が書いたコードのためのリリース検証エンジン

[English](README.md) | [简体中文](README.zh-CN.md) | **日本語**

> これは英語版 README の簡約翻訳です。内容に差異がある場合は [README.md](README.md) が優先されます。

HefestoAI は、AI アシスタントがコードを書いた後、そのコードが出荷される前に実行されます。プロジェクトが宣言している内容（依存関係、設定、インストール成果物）が実際の動作と一致しているかを確認し、コード自体のセキュリティと複雑度もチェックします。

オープンソース（MIT）、Python 3.10 以上。パッケージには 22 フォーマットのアナライザー（コード言語 7 + DevOps フォーマット 11 + クラウドフォーマット 4）が含まれ、v4.19.0 の `hefesto analyze` はそのうち 13 を実行します。

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

検出結果は **Security > Code scanning** と PR のアノテーションに表示されます。`@v4` はすべての 4.x リリースに追従します。バージョンを固定する場合は `artvepa80/Agents-Hefesto@v4.19.0` またはコミット SHA を指定してください。Action は Python、YAML、Terraform、Shell、Dockerfile、SQL、COBOL とドリフトチェックを解析します。TypeScript、JavaScript、Java、Go、Rust、C# は CLI と `hefesto-ai[multilang]` が必要です。

## 検出内容（例）

| 問題 | 重大度 |
|------|--------|
| HARDCODED_SECRET（コード内の API キー、パスワード） | CRITICAL |
| SQL_INJECTION_RISK | HIGH |
| COMMAND_INJECTION | HIGH |
| PICKLE_USAGE（安全でないデシリアライズ） | HIGH |
| UNDECLARED_DEPENDENCY（import されているが pyproject.toml に未宣言） | MEDIUM |
| PACKAGING_VERSION_DRIFT（pyproject、CHANGELOG、README のバージョン不一致） | MEDIUM |

## MCP サーバー

AI エージェントは MCP 経由で HefestoAI を呼び出せます：

```bash
npx @smithery/cli@latest mcp add artvepa80/hefestoai
```

MCP エンドポイント：`https://hefestoai.narapallc.com/api/mcp-protocol`（JSON-RPC 2.0）。MCP の `analyze` ツールは、送信されたファイルに対してオープンソースエンジン（hefesto-ai 4.19.0）を実行します。上限は 20 ファイル、各 100 KB、合計 256 KB、20 秒です。内容は保存されません。リポジトリ全体はローカルで `hefesto analyze .` を実行してください。ホスト型 MCP サーバーはクローズドソースで、Narapa LLC が運営しています。

## 対応言語

- コード：Python（ネイティブ AST、フルサポート）、TypeScript、JavaScript、Java、Go、Rust、C#（TreeSitter、`[multilang]` が必要）
- `hefesto analyze` が実行する DevOps フォーマット：YAML、Terraform、Shell、Dockerfile、SQL、COBOL（無料ルール 16 個、COBOL001–COBOL016）

## 料金

無料・オープンソース（MIT）。PRO は月額 8 ドル、OMEGA は月額 19 ドルです。詳細：[hefestoai.narapallc.com](https://hefestoai.narapallc.com/?utm_source=github&utm_medium=readme&utm_campaign=growth_q4_2026&utm_content=pricing_ja#pricing)

## リンク

- サイト：[hefestoai.narapallc.com](https://hefestoai.narapallc.com/?utm_source=github&utm_medium=readme&utm_campaign=growth_q4_2026&utm_content=readme_ja)
- PyPI：[hefesto-ai](https://pypi.org/project/hefesto-ai/)
- 完全なドキュメント（英語）：[README.md](README.md)
