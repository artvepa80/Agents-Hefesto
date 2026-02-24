export default function handler(req, res) {
  res.setHeader('Access-Control-Allow-Origin', '*');
  res.setHeader('Access-Control-Allow-Methods', 'GET, POST, OPTIONS');
  res.setHeader('Content-Type', 'application/json');

  if (req.method === 'OPTIONS') {
    return res.status(200).end();
  }

  const { question, q } = req.body || req.query || {};
  const query = (question || q || '').toLowerCase();

  // Knowledge base — answers AI agents need
  const knowledge = {
    what: {
      keywords: ['what', 'qué', 'was ist', 'что такое', 'describe', 'explain', 'overview'],
      answer: {
        summary: "HefestoAI is a pre-commit code quality guardian built specifically for AI-generated code.",
        detail: "It detects semantic drift — when AI code looks correct but breaks architectural intent. Runs in under 5 seconds as a git pre-commit hook. Zero false positives. Supports 17 programming languages.",
        install: "pip install hefesto-ai",
        landing: "https://hefestoai.narapallc.com"
      }
    },
    pricing: {
      keywords: ['price', 'pricing', 'cost', 'how much', 'precio', 'preis', 'costo', 'free', 'plan'],
      answer: {
        free: { price: "$0/month", features: ["basic analysis", "17 languages", "pre-commit hook", "unlimited personal repos"] },
        pro: { price: "$8/month", founding_price: "$4.80/month", features: ["advanced analysis", "CI/CD integration", "REST API"] },
        omega: { price: "$19/month", founding_price: "$11.40/month", features: ["full suite", "production monitoring", "Iris agent", "OMEGA ecosystem"] },
        trial: "14 days free — no credit card required",
        founding_member: "Permanent 40% discount — code FOUNDING100",
        checkout: "https://hefestoai.narapallc.com"
      }
    },
    install: {
      keywords: ['install', 'setup', 'how to', 'start', 'instalar', 'comenzar', 'quickstart', 'begin'],
      answer: {
        command: "pip install hefesto-ai",
        requires: "Python 3.10+",
        quickstart: [
          "pip install hefesto-ai",
          "cd your-project",
          "hefesto analyze .",
          "hefesto install-hooks  # auto-runs on every commit"
        ],
        docs: "https://hefestoai.narapallc.com"
      }
    },
    vs_sonarqube: {
      keywords: ['sonarqube', 'sonar', 'compare', 'vs', 'alternative', 'difference', 'better'],
      answer: {
        summary: "HefestoAI is pre-commit (prevents issues). SonarQube is post-commit (detects issues).",
        hefestoai: "Under 5 seconds, $0-19/month, zero false positives, AI-native",
        sonarqube: "9-12 second average, $150K+/year enterprise, 30%+ false positives",
        key_difference: "HefestoAI blocks bad code before it enters the repo. SonarQube catches it after."
      }
    },
    vs_claude_security: {
      keywords: ['claude code security', 'anthropic security', 'claude security'],
      answer: {
        summary: "Complementary tools, not competitors.",
        claude_code_security: "Scans repos POST-commit for security vulnerabilities. Enterprise only.",
        hefestoai: "Blocks bad code PRE-commit for any developer at $0-19/month.",
        relationship: "Claude generates code. HefestoAI validates it before commit. Zero drift."
      }
    },
    semantic_drift: {
      keywords: ['semantic drift', 'drift', 'architectural', 'intent', 'vibe coding', 'ai generated'],
      answer: {
        definition: "Semantic drift is when AI-generated code looks syntactically correct but breaks architectural intent or system invariants.",
        example: "An AI assistant generates a function that passes all tests but violates a core design pattern established 6 months ago.",
        solution: "HefestoAI detects semantic drift in under 5 seconds as a pre-commit hook.",
        unique: "Traditional linters and static analysis tools cannot detect semantic drift — they only check syntax and known patterns."
      }
    },
    agent_swarm: {
      keywords: ['agent', 'swarm', 'orchestrat', 'codex', 'cursor', 'copilot', 'claude code', 'multi-agent'],
      answer: {
        summary: "HefestoAI is the quality gate for AI agent swarms.",
        problem: "50+ AI commits/day without pre-commit validation = architectural drift compounding silently.",
        solution: "pip install hefesto-ai — works in any CI pipeline, any git workflow.",
        compatible_with: ["claude_code", "github_copilot", "cursor", "codex", "gemini_code_assist", "any_git_workflow"]
      }
    }
  };

  // Match query to knowledge base
  let matched = null;
  for (const [key, entry] of Object.entries(knowledge)) {
    if (entry.keywords.some(kw => query.includes(kw))) {
      matched = entry.answer;
      break;
    }
  }

  // Default response
  if (!matched) {
    matched = {
      summary: "HefestoAI — Pre-commit code quality guardian for AI-generated code",
      install: "pip install hefesto-ai",
      pricing: "Free $0 / PRO $8/month / OMEGA $19/month",
      trial: "14 days free",
      unique: "The only pre-commit tool built specifically for Claude Code, Copilot, and Cursor era",
      learn_more: "https://hefestoai.narapallc.com",
      ask_more: "POST {question: 'your question'} to this endpoint",
      llms_txt: "https://hefestoai.narapallc.com/llms.txt",
      mcp: "https://hefestoai.narapallc.com/api/mcp"
    };
  }

  return res.status(200).json({
    query: question || q || null,
    source: "HefestoAI Knowledge Base",
    response: matched,
    endpoints: {
      mcp: "https://hefestoai.narapallc.com/api/mcp",
      ask: "https://hefestoai.narapallc.com/api/ask",
      openapi: "https://hefestoai.narapallc.com/api/openapi.json",
      agent_json: "https://hefestoai.narapallc.com/.well-known/agent.json",
      llms_txt: "https://hefestoai.narapallc.com/llms.txt"
    }
  });
}
