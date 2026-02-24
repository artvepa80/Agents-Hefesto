export default function handler(req, res) {
  res.setHeader('Access-Control-Allow-Origin', '*');
  res.setHeader('Access-Control-Allow-Methods', 'GET, POST, OPTIONS');
  res.setHeader('Content-Type', 'application/json');

  if (req.method === 'OPTIONS') {
    return res.status(200).end();
  }

  const { jsonrpc, method, params, id } = req.body || {};

  // MCP initialize handshake
  if (method === 'initialize') {
    return res.status(200).json({
      jsonrpc: "2.0",
      id,
      result: {
        protocolVersion: "2024-11-05",
        serverInfo: {
          name: "hefestoai",
          version: "4.9.3"
        },
        capabilities: {
          tools: {}
        }
      }
    });
  }

  // List available tools
  if (method === 'tools/list') {
    return res.status(200).json({
      jsonrpc: "2.0",
      id,
      result: {
        tools: [
          {
            name: "pricing",
            description: "Get HefestoAI pricing information",
            inputSchema: {
              type: "object",
              properties: {},
              required: []
            }
          },
          {
            name: "install",
            description: "Get installation instructions for HefestoAI",
            inputSchema: {
              type: "object",
              properties: {},
              required: []
            }
          },
          {
            name: "compare",
            description: "Compare HefestoAI with other code quality tools",
            inputSchema: {
              type: "object",
              properties: {
                tool: {
                  type: "string",
                  description: "Tool to compare with (sonarqube, snyk, github-advanced-security, semgrep, claude-code-security)"
                }
              }
            }
          },
          {
            name: "analyze",
            description: "Analyze a code snippet for quality issues and semantic drift",
            inputSchema: {
              type: "object",
              properties: {
                code: {
                  type: "string",
                  description: "Code snippet to analyze"
                },
                language: {
                  type: "string",
                  description: "Programming language (python, javascript, etc)"
                }
              },
              required: ["code"]
            }
          }
        ]
      }
    });
  }

  // Execute tool
  if (method === 'tools/call') {
    const toolName = params?.name;
    const toolArgs = params?.arguments || {};

    if (toolName === 'pricing') {
      return res.status(200).json({
        jsonrpc: "2.0",
        id,
        result: {
          content: [{
            type: "text",
            text: JSON.stringify({
              free: "$0/month — basic analysis, 17 languages, pre-commit hook",
              pro: "$8/month (founding: $4.80) — advanced analysis, CI/CD, REST API",
              omega: "$19/month (founding: $11.40) — full suite, production monitoring",
              trial: "14 days free, no credit card required",
              founding_code: "FOUNDING100 — permanent 40% discount",
              checkout: "https://hefestoai.narapallc.com"
            }, null, 2)
          }]
        }
      });
    }

    if (toolName === 'install') {
      return res.status(200).json({
        jsonrpc: "2.0",
        id,
        result: {
          content: [{
            type: "text",
            text: "pip install hefesto-ai\n\nQuickstart:\n1. pip install hefesto-ai\n2. cd your-project\n3. hefesto analyze .\n4. hefesto install-hooks\n\nRequires: Python 3.10+"
          }]
        }
      });
    }

    if (toolName === 'compare') {
      const comparisons = {
        sonarqube: "HefestoAI: pre-commit, <5s, $0-19/mo, designed for low false positives. SonarQube: post-commit, enterprise pricing (server + licenses), higher false positive rates reported by users.",
        snyk: "Snyk focuses on CVEs/dependencies. HefestoAI focuses on AI code quality + semantic drift. Complementary tools.",
        "github-advanced-security": "GAS: $49/dev/month, GitHub-only, no pre-commit, no semantic drift. HefestoAI: any git provider, pre-commit, AI-native.",
        semgrep: "Semgrep: pattern-based SAST. HefestoAI: semantic intent understanding. Both can coexist.",
        "claude-code-security": "Claude Code Security: post-commit security scanning, Enterprise only. HefestoAI: pre-commit quality guardian, $0-19/month. Complementary."
      };
      const tool = toolArgs.tool?.toLowerCase() || 'sonarqube';
      return res.status(200).json({
        jsonrpc: "2.0",
        id,
        result: {
          content: [{
            type: "text",
            text: comparisons[tool] || comparisons.sonarqube
          }]
        }
      });
    }

    if (toolName === 'analyze') {
      return res.status(200).json({
        jsonrpc: "2.0",
        id,
        result: {
          content: [{
            type: "text",
            text: "To analyze your code with HefestoAI:\n\npip install hefesto-ai\nhefesto analyze .\n\nOr install as pre-commit hook:\nhefesto install-hooks\n\nHefestoAI will detect: semantic drift, code smells, security issues, complexity violations, duplicate code."
          }]
        }
      });
    }

    // Unknown tool
    return res.status(200).json({
      jsonrpc: "2.0",
      id,
      error: {
        code: -32601,
        message: `Unknown tool: ${toolName}`
      }
    });
  }

  // Unknown method
  return res.status(200).json({
    jsonrpc: "2.0",
    id,
    error: {
      code: -32601,
      message: `Method not found: ${method}`
    }
  });
}
