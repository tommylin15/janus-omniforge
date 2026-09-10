import { GeminiProvider } from "./gemini_provider.js";
import { OpenRouterProvider, type ChatMessage } from "./openrouter_provider.js";
import type { Json } from "./server.js";

export type DispatchRequest = {
  ownerId: string;
  threadId: string;
  turnId: string;
  runtime: "openrouter" | "gemini";
  model: string;
  messages: ChatMessage[];
  grounding?: boolean;
  continuation?: Record<string, Json>;
};

export async function dispatchAssistant(request: DispatchRequest): Promise<Json> {
  if (!request.messages.length || request.messages.length > 100) throw new Error("assistant messages are invalid");
  if (request.runtime === "openrouter") {
    const provider = OpenRouterProvider.fromEnvironment();
    const model = request.model === "openrouter/free"
      ? (await provider.listModels(["streaming"]))[0]?.id
      : request.model;
    if (!model) throw new Error("OpenRouter has no approved free streaming model");
    const events: Json[] = [];
    let seq = 0;
    for await (const event of provider.stream(request.messages, { model })) {
      events.push({ eventId: `${request.turnId}-${seq}`, seq: seq++, threadId: request.threadId,
        turnId: request.turnId, type: event.type, payload: event.type === "text_delta" ? { text: event.delta } : event.type === "usage" ? event.usage : event.result,
        providerIds: { runtime: "openrouter", model } });
    }
    return { events, continuation: { runtime: "openrouter", model } };
  }
  const prompt = request.messages.map((message) => `${message.role}: ${message.content ?? ""}`).join("\n");
  const result = await GeminiProvider.fromEnvironment().generate(prompt, { grounding: request.grounding === true });
  return { events: [
    { eventId: `${request.turnId}-0`, seq: 0, threadId: request.threadId, turnId: request.turnId,
      type: "text_delta", payload: { text: result.text }, providerIds: { runtime: "gemini", model: result.model } },
    { eventId: `${request.turnId}-1`, seq: 1, threadId: request.threadId, turnId: request.turnId,
      type: "turn_completed", payload: result, providerIds: { runtime: "gemini", model: result.model } },
  ], continuation: { runtime: "gemini", model: result.model } };
}
