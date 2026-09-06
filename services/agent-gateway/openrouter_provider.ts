export type OpenRouterModel = {
  id: string;
  name: string;
  contextLength: number;
  promptPrice: string;
  completionPrice: string;
  supportedParameters: string[];
};
export type ChatMessage = { role: "system" | "user" | "assistant" | "tool"; content: string | null; tool_call_id?: string; tool_calls?: ToolCall[] };
export type ToolDefinition = { type: "function"; function: { name: string; description?: string; parameters: Record<string, unknown> } };
export type ToolCall = { id: string; type: "function"; function: { name: string; arguments: string } };
export type OpenRouterResult = { model: string; messages: ChatMessage[]; text: string; usage?: { promptTokens: number; completionTokens: number; totalTokens: number } };
export type OpenRouterEvent = { type: "text_delta"; delta: string } | { type: "usage"; usage: NonNullable<OpenRouterResult["usage"]> } | { type: "turn_completed"; result: OpenRouterResult };

type JsonRecord = Record<string, unknown>;
type Fetcher = typeof fetch;
type ToolExecutor = (name: string, args: unknown) => Promise<unknown>;

export class OpenRouterProviderError extends Error {
  constructor(public readonly kind: "quota" | "provider_unavailable" | "provider_error", public readonly status: number) { super(kind); }
}

function record(value: unknown): JsonRecord { return value && typeof value === "object" && !Array.isArray(value) ? value as JsonRecord : {}; }
function price(value: unknown): string { return typeof value === "string" || typeof value === "number" ? String(value) : "Infinity"; }
function model(value: unknown): OpenRouterModel {
  const item = record(value);
  return {
    id: typeof item.id === "string" ? item.id : "",
    name: typeof item.name === "string" ? item.name : "",
    contextLength: typeof item.context_length === "number" ? item.context_length : 0,
    promptPrice: price(record(item.pricing).prompt), completionPrice: price(record(item.pricing).completion),
    supportedParameters: Array.isArray(item.supported_parameters) ? item.supported_parameters.filter((value): value is string => typeof value === "string") : [],
  };
}

export class OpenRouterProvider {
  constructor(
    private readonly apiKey: string,
    private readonly fetcher: Fetcher = fetch,
    private readonly baseUrl = "https://openrouter.ai/api/v1",
    private readonly freeOnly = true,
  ) {
    if (!apiKey.trim()) throw new Error("OPENROUTER_API_KEY is required");
    if (!freeOnly && process.env.OPENROUTER_PAID_ENABLED !== "true") throw new Error("OpenRouter paid tier requires billing gate");
  }

  static fromEnvironment(fetcher: Fetcher = fetch): OpenRouterProvider {
    return new OpenRouterProvider(process.env.OPENROUTER_API_KEY ?? "", fetcher, undefined, process.env.OPENROUTER_FREE_ONLY !== "false");
  }

  async listModels(required: ("tools" | "streaming")[] = []): Promise<OpenRouterModel[]> {
    const query = new URLSearchParams({ output_modalities: "text", limit: "1000", ...(this.freeOnly ? { max_price: "0", max_output_price: "0" } : {}) });
    if (required.length) query.set("supported_parameters", required.join(","));
    const response = await this.request(`${this.baseUrl}/models?${query}`);
    const data = record(response).data;
    return (Array.isArray(data) ? data : []).map(model).filter((item) => item.id && (!this.freeOnly || (Number(item.promptPrice) === 0 && Number(item.completionPrice) === 0)));
  }

  async complete(messages: ChatMessage[], options: { model: string; tools?: ToolDefinition[]; maxToolRounds?: number; executeTool?: ToolExecutor }): Promise<OpenRouterResult> {
    const selected = await this.listModels(options.tools?.length ? ["tools"] : []);
    const metadata = selected.find((item) => item.id === options.model);
    if (!metadata) throw new Error("OpenRouter model is not approved or is unavailable");
    const conversation = [...messages];
    const maxRounds = options.maxToolRounds ?? 3;
    let usage: OpenRouterResult["usage"];
    for (let round = 0; round <= maxRounds; round++) {
      const body = await this.chat(conversation, options.model, options.tools, false);
      const choices = record(body).choices;
      const choice = record(Array.isArray(choices) ? choices[0] : undefined);
      const message = record(choice.message) as ChatMessage;
      const bodyUsage = record(record(body).usage);
      if (typeof bodyUsage.prompt_tokens === "number" && typeof bodyUsage.completion_tokens === "number" && typeof bodyUsage.total_tokens === "number") usage = { promptTokens: bodyUsage.prompt_tokens, completionTokens: bodyUsage.completion_tokens, totalTokens: bodyUsage.total_tokens };
      conversation.push(message);
      const calls = Array.isArray(message.tool_calls) ? message.tool_calls : [];
      if (!calls.length) return { model: options.model, messages: conversation, text: typeof message.content === "string" ? message.content : "", ...(usage ? { usage } : {}) };
      if (!options.executeTool) throw new Error("OpenRouter tool executor is required");
      if (round === maxRounds) throw new Error("OpenRouter tool loop limit reached");
      for (const call of calls) {
        let args: unknown;
        try { args = JSON.parse(call.function.arguments); } catch { throw new Error("OpenRouter tool arguments are invalid"); }
        conversation.push({ role: "tool", tool_call_id: call.id, content: JSON.stringify(await options.executeTool(call.function.name, args)) });
      }
    }
    throw new Error("OpenRouter completion failed");
  }

  async *stream(messages: ChatMessage[], options: { model: string; tools?: ToolDefinition[] } ): AsyncGenerator<OpenRouterEvent> {
    const selected = await this.listModels(options.tools?.length ? ["tools", "streaming"] : ["streaming"]);
    if (!selected.some((item) => item.id === options.model)) throw new Error("OpenRouter model is not approved or is unavailable");
    const response = await this.chat(messages, options.model, options.tools, true);
    if (!(response instanceof Response) || !response.body) throw new Error("OpenRouter streaming response is unavailable");
    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let buffer = "";
    let text = "";
    let usage: OpenRouterResult["usage"];
    for (;;) {
      const chunk = await reader.read();
      buffer += decoder.decode(chunk.value, { stream: !chunk.done });
      const lines = buffer.split("\n"); buffer = lines.pop() ?? "";
      for (const line of lines) {
        if (!line.startsWith("data: ")) continue;
        if (line.slice(6).trim() === "[DONE]") continue;
        const data = record(JSON.parse(line.slice(6)));
        const choices = data.choices;
        const delta = record(record(Array.isArray(choices) ? choices[0] : undefined).delta).content;
        if (typeof delta === "string" && delta) { text += delta; yield { type: "text_delta", delta }; }
        const u = record(data.usage);
        if (typeof u.prompt_tokens === "number" && typeof u.completion_tokens === "number" && typeof u.total_tokens === "number") usage = { promptTokens: u.prompt_tokens, completionTokens: u.completion_tokens, totalTokens: u.total_tokens };
      }
      if (chunk.done) break;
    }
    if (usage) yield { type: "usage", usage };
    yield { type: "turn_completed", result: { model: options.model, messages, text, ...(usage ? { usage } : {}) } };
  }

  private async chat(messages: ChatMessage[], modelId: string, tools: ToolDefinition[] | undefined, stream: false): Promise<JsonRecord>;
  private async chat(messages: ChatMessage[], modelId: string, tools: ToolDefinition[] | undefined, stream: true): Promise<Response>;
  private async chat(messages: ChatMessage[], modelId: string, tools: ToolDefinition[] | undefined, stream: boolean): Promise<JsonRecord | Response> {
    if (this.freeOnly && !modelId.endsWith(":free") && modelId !== "openrouter/free") throw new Error("free-only OpenRouter requires a free model");
    const response = await this.fetcher(`${this.baseUrl}/chat/completions`, { method: "POST", headers: { authorization: `Bearer ${this.apiKey}`, "content-type": "application/json" }, body: JSON.stringify({ model: modelId, messages, ...(tools?.length ? { tools } : {}), stream }) });
    if (!response.ok) throw this.error(response.status);
    return stream ? response : response.json() as Promise<JsonRecord>;
  }

  private async request(url: string): Promise<unknown> {
    const response = await this.fetcher(url, { headers: { authorization: `Bearer ${this.apiKey}` } });
    if (!response.ok) throw this.error(response.status);
    return response.json();
  }

  private error(status: number): OpenRouterProviderError { return new OpenRouterProviderError(status === 429 ? "quota" : status >= 500 ? "provider_unavailable" : "provider_error", status); }
}
