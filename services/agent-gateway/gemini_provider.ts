export type GeminiCitation = { title: string; uri: string };
export type GeminiUsage = { promptTokens: number; candidateTokens: number; totalTokens: number };
export type GeminiResult = {
  text: string;
  model: string;
  queriedAt: string;
  searchQueries: string[];
  citations: GeminiCitation[];
  usage?: GeminiUsage;
  finishReason?: string;
};
type JsonRecord = Record<string, unknown>;
type Fetcher = typeof fetch;

export class GeminiProviderError extends Error {
  constructor(public readonly kind: "quota" | "provider_unavailable" | "provider_error", public readonly status: number) {
    super(kind);
  }
}

function record(value: unknown): JsonRecord {
  return value && typeof value === "object" && !Array.isArray(value) ? value as JsonRecord : {};
}

function textParts(candidate: JsonRecord): string {
  const content = record(candidate.content);
  return Array.isArray(content.parts)
    ? content.parts.map((part) => record(part).text).filter((text): text is string => typeof text === "string").join("")
    : "";
}

function result(body: unknown, model: string, queriedAt: string): GeminiResult {
  const candidates = record(body).candidates;
  const candidate = record(Array.isArray(candidates) ? candidates[0] : undefined);
  const metadata = record(candidate.groundingMetadata);
  const citations = (Array.isArray(metadata.groundingChunks) ? metadata.groundingChunks : [])
    .map((chunk) => record(record(chunk).web))
    .filter((web) => typeof web.uri === "string")
    .map((web) => ({ uri: web.uri as string, title: typeof web.title === "string" ? web.title : web.uri as string }));
  const usage = record(record(body).usageMetadata);
  const promptTokens = usage.promptTokenCount;
  const candidateTokens = usage.candidatesTokenCount;
  const totalTokens = usage.totalTokenCount;
  return {
    text: textParts(candidate), model, queriedAt,
    searchQueries: Array.isArray(metadata.webSearchQueries) ? metadata.webSearchQueries.filter((q): q is string => typeof q === "string") : [],
    citations,
    ...(typeof promptTokens === "number" && typeof candidateTokens === "number" && typeof totalTokens === "number"
      ? { usage: { promptTokens, candidateTokens, totalTokens } } : {}),
    ...(typeof candidate.finishReason === "string" ? { finishReason: candidate.finishReason } : {}),
  };
}

export class GeminiProvider {
  constructor(
    private readonly apiKey: string,
    private readonly model = "gemini-2.5-flash",
    private readonly fetcher: Fetcher = fetch,
    private readonly baseUrl = "https://generativelanguage.googleapis.com/v1beta",
  ) {
    if (!apiKey.trim()) throw new Error("GEMINI_API_KEY is required");
    if (process.env.GEMINI_PAID_ENABLED === "true") throw new Error("Gemini paid tier is disabled");
    if (!/^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$/.test(model)) throw new Error("Gemini model is invalid");
  }

  static fromEnvironment(fetcher: Fetcher = fetch): GeminiProvider {
    return new GeminiProvider(process.env.GEMINI_API_KEY ?? "", process.env.GEMINI_MODEL || "gemini-2.5-flash", fetcher);
  }

  async generate(prompt: string, options: { grounding?: boolean; systemInstruction?: string; signal?: AbortSignal } = {}): Promise<GeminiResult> {
    if (!prompt.trim() || prompt.length > 32_768) throw new Error("Gemini prompt is invalid");
    const queriedAt = new Date().toISOString();
    const body = {
      ...(options.systemInstruction ? { system_instruction: { parts: [{ text: options.systemInstruction }] } } : {}),
      contents: [{ role: "user", parts: [{ text: prompt }] }],
      ...(options.grounding ? { tools: [{ google_search: {} }] } : {}),
    };
    const response = await this.fetcher(`${this.baseUrl}/models/${encodeURIComponent(this.model)}:generateContent`, {
      method: "POST", signal: options.signal, headers: { "content-type": "application/json", "x-goog-api-key": this.apiKey }, body: JSON.stringify(body),
    });
    if (!response.ok) throw this.error(response.status);
    return result(await response.json(), this.model, queriedAt);
  }

  private error(status: number): GeminiProviderError {
    return new GeminiProviderError(status === 429 ? "quota" : status >= 500 ? "provider_unavailable" : "provider_error", status);
  }
}
