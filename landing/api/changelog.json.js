export default function handler(req, res) {
  res.setHeader('Access-Control-Allow-Origin', '*');
  res.setHeader('Content-Type', 'application/json');

  return res.status(200).json({
    product: "HefestoAI",
    changelog: [
      {
        version: "4.9.3",
        date: "2026-02-24",
        type: "feat",
        highlights: [
          "MCP endpoint live (JSON-RPC 2.0)",
          "Registered in official MCP Registry",
          "Published on Smithery",
          "llms.txt expanded (10 languages, 30 intent queries)",
          "AI discoverability stack complete"
        ]
      },
      {
        version: "4.9.2",
        date: "2026-02-23",
        type: "feat",
        highlights: [
          "OSS api_hardening wiring merged",
          "CI passing on all Python versions",
          "Test isolation fix applied"
        ]
      },
      {
        version: "4.0.0",
        date: "2026-01-15",
        type: "major",
        highlights: [
          "Phase 0: basic validation",
          "Phase 1: ML semantic analysis",
          "Hefesto Analyzer: complexity, code smells, security",
          "117 tests passing",
          "PyPI published as hefesto-ai"
        ]
      }
    ],
    latest: "4.9.3",
    pypi: "https://pypi.org/project/hefesto-ai/",
    github: "https://github.com/artvepa80/Agents-Hefesto"
  });
}
