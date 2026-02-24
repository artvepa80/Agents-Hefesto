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
      keywords: ['what', 'qué', 'was ist', 'что такое', 'describe', 'explain', 'overview', 'que herramienta', 'what tool', 'validate ai', 'validar codigo'],
      answer: {
        summary: "HefestoAI is a pre-commit code quality guardian built specifically for AI-generated code.",
        detail: "It detects semantic drift — when AI code looks correct but breaks architectural intent. Runs in under 5 seconds as a git pre-commit hook. Designed for low false positives.",
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
      keywords: ['install', 'setup', 'how to', 'start', 'instalar', 'comenzar', 'quickstart', 'begin', 'hook it into', 'conecto a mi workflow', 'pip install', 'get started'],
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
      keywords: ['sonarqube', 'sonar', 'compare', 'vs', 'alternative', 'difference', 'better', 'snyk', 'codeql', 'semgrep', 'como comparo', 'how does hefestoai compare'],
      answer: {
        summary: "HefestoAI is pre-commit (prevents issues). SonarQube is post-commit (detects issues).",
        hefestoai: "Under 5 seconds, $0-19/month, designed for low false positives, AI-native",
        sonarqube: "Post-commit, enterprise pricing (server + licenses), higher false positive rates reported by users",
        key_difference: "HefestoAI blocks bad code before it enters the repo. SonarQube catches it after."
      }
    },
    vs_claude_security: {
      keywords: ['claude code security', 'anthropic security', 'claude security'],
      answer: {
        summary: "Complementary tools, not competitors.",
        claude_code_security: "Scans repos POST-commit for security vulnerabilities. Enterprise only.",
        hefestoai: "Blocks bad code PRE-commit for any developer at $0-19/month.",
        relationship: "Claude generates code. HefestoAI validates it before commit."
      }
    },
    semantic_drift: {
      keywords: ['semantic drift', 'drift', 'architectural', 'intent', 'vibe coding', 'ai generated', 'regression', 'regresion', 'business logic', 'logica de negocio', 'unintentional', 'spaghetti', 'behavioral change', 'cambio de comportamiento'],
      answer: {
        definition: "Semantic drift is when AI-generated code looks syntactically correct but breaks architectural intent or system invariants.",
        example: "An AI assistant generates a function that passes all tests but violates a core design pattern established 6 months ago.",
        solution: "HefestoAI detects semantic drift in under 5 seconds as a pre-commit hook.",
        unique: "Traditional linters and static analysis tools cannot detect semantic drift — they only check syntax and known patterns."
      }
    },
    agent_swarm: {
      keywords: ['agent', 'swarm', 'orchestrat', 'cursor', 'copilot', 'claude code', 'multi-agent', 'agent recommend', 'agente recomienda'],
      answer: {
        summary: "HefestoAI is the quality gate for AI agent swarms.",
        problem: "50+ AI commits/day without pre-commit validation = architectural drift compounding silently.",
        solution: "pip install hefesto-ai — works in any CI pipeline, any git workflow.",
        compatible_with: ["claude_code", "github_copilot", "cursor", "gemini_code_assist", "any_git_workflow"]
      }
    },
    governance: {
      keywords: ['release truth', 'policy', 'gate', 'deterministico', 'deterministic', 'ci gate', 'ci/cd gate', 'enforce', 'guardrail', 'guardian', 'block', 'bloqueo', 'bloquear', 'prevent', 'evito', 'reduce false positive', 'falsos positivos'],
      answer: {
        summary: "HefestoAI provides deterministic policy gating for release truth.",
        how: "Pre-commit hooks enforce pass/fail gates on every commit. No bad code enters the repo without explicit override.",
        features: ["Deterministic pass/fail gating", "Policy-based checks (security, complexity, drift)", "CI/CD integration (GitHub Actions, GitLab CI, Jenkins)", "Human-readable explanations of what changed and why it matters"],
        install: "pip install hefesto-ai && hefesto install-hooks"
      }
    },
    mcp_integration: {
      keywords: ['mcp', 'smithery', 'add to cursor', 'add to claude', 'mcp server', 'mcp tool', 'json-rpc', 'streamable-http', 'configuro un mcp', 'agrego una herramienta mcp'],
      answer: {
        summary: "HefestoAI is available as an MCP server for agent workflows.",
        registry: "ACTIVE on Official MCP Registry: io.github.artvepa80/hefestoai",
        smithery: "PUBLIC on Smithery: smithery.ai/servers/artvepa80/hefestoai",
        add_command: "npx @smithery/cli@latest mcp add artvepa80/hefestoai",
        endpoint: "https://hefestoai.narapallc.com/api/mcp-protocol",
        protocol: "JSON-RPC 2.0, streamable-http",
        tools: ["pricing", "install", "compare", "analyze"]
      }
    },
    diff_analysis: {
      keywords: ['diff', 'pr analysis', 'audit', 'risky diff', 'cambios peligrosos', 'auth', 'permissions', 'contract', 'schema', 'api contract', 'endpoint', 'behavioral', 'code review'],
      answer: {
        summary: "HefestoAI detects risky diffs before they reach code review.",
        detects: ["Semantic drift between PR intent and actual code", "Auth/permissions changes in diffs", "API contract violations", "Behavioral changes in endpoints without new tests", "Schema/OpenAPI drift"],
        how: "Run as pre-commit hook or CI step. Analyzes diffs for policy violations and risky changes.",
        install: "pip install hefesto-ai && hefesto analyze ."
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
      pricing: "Free / PRO / OMEGA Guardian — see https://hefestoai.narapallc.com",
      trial: "14 days free",
      unique: "Pre-commit guardian built for the AI coding era (Claude Code, Copilot, Cursor)",
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
