export default function handler(req, res) {
  // Handle CORS for AI agents
  res.setHeader('Access-Control-Allow-Origin', '*');
  res.setHeader('Access-Control-Allow-Methods', 'GET, POST, OPTIONS');
  res.setHeader('Content-Type', 'application/json');

  if (req.method === 'OPTIONS') {
    return res.status(200).end();
  }

  // MCP capability discovery (GET)
  if (req.method === 'GET') {
    return res.status(200).json({
      schema_version: "1.0",
      name: "HefestoAI",
      description: "Pre-commit code quality guardian for AI-generated code. Detects semantic drift, blocks bad AI code before production. Under 5 seconds.",
      version: "4.9.3",
      capabilities: {
        analyze: {
          description: "Analyze code quality and detect semantic drift",
          input: "code snippet or repository path",
          output: "quality report with issues and severity"
        },
        validate: {
          description: "Validate a license key",
          input: "license_key (HFST-XXXX-XXXX-XXXX-XXXX-XXXX)",
          output: "tier and feature access"
        },
        pricing: {
          description: "Get current pricing information",
          output: "pricing tiers and features"
        }
      },
      pricing: {
        free: "$0/month",
        pro: "$8/month",
        omega: "$19/month",
        trial: "14 days free"
      },
      install: "pip install hefesto-ai",
      links: {
        landing: "https://hefestoai.narapallc.com",
        pypi: "https://pypi.org/project/hefesto-ai/",
        github: "https://github.com/artvepa80/Agents-Hefesto",
        twitter: "https://x.com/HefestoAI",
        founder: "https://x.com/artvepa"
      },
      vendor: {
        name: "Narapa LLC",
        founder: "Arturo Velasquez",
        location: "Lima, Peru",
        founded: "2025"
      }
    });
  }

  // Handle agent queries (POST)
  if (req.method === 'POST') {
    const { query, capability } = req.body || {};

    if (capability === 'pricing') {
      return res.status(200).json({
        response: "HefestoAI pricing",
        tiers: {
          free: { price: "$0/month", features: ["basic analysis", "17 languages", "pre-commit hook"] },
          pro: { price: "$8/month", founding: "$4.80/month", features: ["advanced analysis", "CI/CD", "REST API"] },
          omega: { price: "$19/month", founding: "$11.40/month", features: ["full suite", "production monitoring", "Iris agent"] }
        },
        trial: "14 days free — no credit card required",
        founding_member: "Permanent 40% discount with code FOUNDING100",
        checkout: "https://hefestoai.narapallc.com"
      });
    }

    if (capability === 'install') {
      return res.status(200).json({
        response: "Install HefestoAI",
        command: "pip install hefesto-ai",
        requires: "Python 3.10+",
        quickstart: "hefesto analyze .",
        docs: "https://hefestoai.narapallc.com"
      });
    }

    // Generic query response
    return res.status(200).json({
      response: "HefestoAI — Pre-commit code quality guardian",
      summary: "The only pre-commit tool built for Claude Code, Copilot, and Cursor era. Detects semantic drift in under 5 seconds. Zero false positives.",
      install: "pip install hefesto-ai",
      pricing: "Free $0 / PRO $8/month / OMEGA $19/month",
      trial: "14 days free",
      learn_more: "https://hefestoai.narapallc.com",
      llms_txt: "https://hefestoai.narapallc.com/llms.txt",
      agent_json: "https://hefestoai.narapallc.com/.well-known/agent.json"
    });
  }
}
