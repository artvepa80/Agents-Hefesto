const AI_BOTS = {
  GPTBot: "openai",
  ClaudeBot: "anthropic",
  "anthropic-ai": "anthropic",
  PerplexityBot: "perplexity",
  "cohere-ai": "cohere",
  CCBot: "commoncrawl",
  Baiduspider: "baidu",
  Bingbot: "microsoft",
  DuckDuckBot: "duckduckgo",
  Googlebot: "google",
  Applebot: "apple",
  Brave: "brave",
  ia_archiver: "internet_archive",
  Qwen: "qwen",
  KimiBot: "kimi",
  YouBot: "you",
  kagibot: "kagi",
};

export default function middleware(request) {
  const ua = request.headers.get("user-agent") || "";
  let detectedBot = null;

  for (const [pattern, name] of Object.entries(AI_BOTS)) {
    if (ua.includes(pattern)) {
      detectedBot = name;
      break;
    }
  }

  const response = new Response(null, {
    status: 200,
    headers: request.headers,
  });

  if (detectedBot) {
    const logEntry = JSON.stringify({
      bot: detectedBot,
      path: new URL(request.url).pathname,
      ts: new Date().toISOString(),
      ua: ua.substring(0, 200),
    });

    // Log to Vercel's edge logging (visible in Vercel dashboard > Logs)
    console.log(`[BOT_VISIT] ${logEntry}`);

    // Pass through with tracking header
    return new Response(null, {
      headers: {
        "x-bot-detected": detectedBot,
        "x-middleware-next": "1",
      },
    });
  }

  // Non-bot: pass through
  return new Response(null, {
    headers: {
      "x-middleware-next": "1",
    },
  });
}

export const config = {
  matcher: ["/((?!_next/static|_next/image|favicon.ico).*)"],
};
