import { describe, expect, it, vi } from "vitest";
import { OpenRouterProvider } from "../services/agent-gateway/openrouter_provider.js";

function response(body: unknown, status = 200, headers: Record<string, string> = { "content-type": "application/json" }): Response { return new Response(JSON.stringify(body), { status, headers }); }

const models = { data: [{ id: "free/model:free", name: "Free", context_length: 4096, pricing: { prompt: "0", completion: "0" }, supported_parameters: ["tools", "streaming"] }, { id: "paid/model", name: "Paid", context_length: 4096, pricing: { prompt: "1", completion: "1" }, supported_parameters: ["tools"] }] };

describe("OpenRouter provider", () => {
  it("lists only free models and filters capabilities", async () => {
    const fetcher = vi.fn().mockResolvedValue(response(models));
    const result = await new OpenRouterProvider("secret", fetcher as typeof fetch).listModels(["tools", "streaming"]);
    expect(result.map((item) => item.id)).toEqual(["free/model:free"]);
    expect(String(fetcher.mock.calls[0][0])).toContain("max_price=0");
    expect(String(fetcher.mock.calls[0][0])).toContain("supported_parameters=tools%2Cstreaming");
  });

  it("runs a bounded function-call loop", async () => {
    const fetcher = vi.fn().mockResolvedValueOnce(response(models)).mockResolvedValueOnce(response({ choices: [{ message: { role: "assistant", content: null, tool_calls: [{ id: "call-1", type: "function", function: { name: "quote", arguments: "{\"symbol\":\"2330\"}" } }] } }] })).mockResolvedValueOnce(response({ choices: [{ message: { role: "assistant", content: "100" } }] }));
    const provider = new OpenRouterProvider("secret", fetcher as typeof fetch);
    const result = await provider.complete([{ role: "user", content: "price" }], { model: "free/model:free", tools: [{ type: "function", function: { name: "quote", parameters: { type: "object" } } }], executeTool: async (name, args) => ({ name, args }) });
    expect(result.text).toBe("100");
    expect(result.messages.at(-1)?.role).toBe("assistant");
  });

  it("requires an explicit paid billing gate and maps quota safely", async () => {
    expect(() => new OpenRouterProvider("secret", fetch, "https://example.test", false)).toThrow("billing gate");
    const provider = new OpenRouterProvider("secret", vi.fn().mockResolvedValue(response({ error: { message: "secret" } }, 429)) as typeof fetch);
    await expect(provider.listModels()).rejects.toMatchObject({ kind: "quota", status: 429, message: "quota" });
  });
});
