export default function handler(req, res) {
  res.setHeader('Access-Control-Allow-Origin', '*');
  res.setHeader('Content-Type', 'application/json');

  return res.status(200).json({
    openapi: "3.0.0",
    info: {
      title: "HefestoAI API",
      description: "Pre-commit code quality guardian for AI-generated code. Detects semantic drift, blocks bad AI code before production.",
      version: "4.9.3",
      contact: {
        name: "Arturo Velasquez",
        url: "https://hefestoai.narapallc.com"
      },
      "x-logo": {
        url: "https://hefestoai.narapallc.com/logo.png"
      }
    },
    servers: [
      {
        url: "https://hefestoai.narapallc.com/api",
        description: "Production"
      }
    ],
    paths: {
      "/mcp": {
        get: {
          summary: "MCP capability discovery",
          description: "Returns HefestoAI capabilities for AI agent discovery (Model Context Protocol)",
          operationId: "getMcpCapabilities",
          tags: ["AI Agent Integration"],
          responses: {
            "200": {
              description: "HefestoAI MCP capabilities",
              content: {
                "application/json": {
                  schema: { "$ref": "#/components/schemas/McpResponse" }
                }
              }
            }
          }
        },
        post: {
          summary: "Query HefestoAI via MCP",
          operationId: "queryMcp",
          tags: ["AI Agent Integration"],
          requestBody: {
            content: {
              "application/json": {
                schema: {
                  type: "object",
                  properties: {
                    capability: {
                      type: "string",
                      enum: ["pricing", "install", "analyze"]
                    },
                    query: { type: "string" }
                  }
                }
              }
            }
          },
          responses: {
            "200": { description: "MCP response" }
          }
        }
      },
      "/ask": {
        get: {
          summary: "Ask HefestoAI a question (GET)",
          operationId: "askGet",
          tags: ["Knowledge Base"],
          parameters: [
            {
              name: "q",
              in: "query",
              description: "Natural language question about HefestoAI",
              schema: { type: "string" },
              example: "what is hefestoai"
            }
          ],
          responses: {
            "200": { description: "Answer from HefestoAI knowledge base" }
          }
        },
        post: {
          summary: "Ask HefestoAI a question (POST)",
          operationId: "askPost",
          tags: ["Knowledge Base"],
          requestBody: {
            content: {
              "application/json": {
                schema: {
                  type: "object",
                  properties: {
                    question: {
                      type: "string",
                      example: "how does hefestoai compare to sonarqube?"
                    }
                  }
                }
              }
            }
          },
          responses: {
            "200": { description: "Structured answer" }
          }
        }
      }
    },
    components: {
      schemas: {
        McpResponse: {
          type: "object",
          properties: {
            name: { type: "string" },
            version: { type: "string" },
            capabilities: { type: "object" },
            pricing: { type: "object" },
            install: { type: "string" }
          }
        }
      }
    },
    tags: [
      {
        name: "AI Agent Integration",
        description: "Endpoints for AI agent and MCP integration"
      },
      {
        name: "Knowledge Base",
        description: "Natural language Q&A about HefestoAI"
      }
    ],
    "x-llms-txt": "https://hefestoai.narapallc.com/llms.txt",
    "x-agent-json": "https://hefestoai.narapallc.com/.well-known/agent.json"
  });
}
