import { describe, expect, it, vi } from "vitest";
import { GeminiProvider } from "../services/agent-gateway/gemini_provider.js";

function response(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), { status, headers: { "content-type": "application/json" } });
}

describe("Gemini REST provider", () => {
  it("sends Google Search grounding and preserves citations and usage", async () => {
    const fetcher = vi.fn().mockResolvedValue(response({
      candidates: [{ content: { parts: [{ text: "Answer" }] }, finishReason: "STOP", groundingMetadata: {
        webSearchQueries: ["janus"], groundingChunks: [{ web: { uri: "https://example.test", title: "Example" } }],
      } }], usageMetadata: { promptTokenCount: 2, candidatesTokenCount: 3, totalTokenCount: 5 },
    }));
    const provider = new GeminiProvider("secret", "gemini-2.5-flash", fetcher as typeof fetch);
    const result = await provider.generate("Question", { grounding: true });
    const request = fetcher.mock.calls[0][1] as RequestInit;
    expect(fetcher.mock.calls[0][0]).toContain(":generateContent");
    expect(request.headers).toMatchObject({ "x-goog-api-key": "secret" });
    expect(JSON.parse(String(request.body))).toMatchObject({ tools: [{ google_search: {} }] });
    expect(result).toMatchObject({ text: "Answer", searchQueries: ["janus"], citations: [{ title: "Example", uri: "https://example.test" }], usage: { totalTokens: 5 } });
    expect(result.queriedAt).toMatch(/Z$/);
  });

  it.each([[429, "quota"], [503, "provider_unavailable"]] as const)("maps HTTP %s to %s without leaking provider text", async (status, kind) => {
    const provider = new GeminiProvider("secret", "gemini-2.5-flash", vi.fn().mockResolvedValue(response({ error: { message: "secret detail" } }, status)) as typeof fetch);
    await expect(provider.generate("Question")).rejects.toMatchObject({ kind, status, message: kind });
  });

  it("fails closed when paid Gemini is enabled", () => {
    vi.stubEnv("GEMINI_PAID_ENABLED", "true");
    expect(() => new GeminiProvider("secret")).toThrow("paid tier is disabled");
    vi.unstubAllEnvs();
  });
});
