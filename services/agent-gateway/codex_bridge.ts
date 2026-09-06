import { createHash, randomUUID } from "node:crypto";
import { resolve, sep } from "node:path";
import type { Json, RpcMessage } from "./server.js";
import { McpHost } from "./mcp_host.js";

type RpcClient = {
  initialize(experimentalApi?: boolean): Promise<Json>;
  request(method: string, params?: Json, timeoutMs?: number): Promise<Json>;
  onMessage(handler: (message: RpcMessage) => Promise<Json | undefined> | Json | undefined): void;
  respond(id: number, result: Json): void;
};

export type McpBinding = { serverId: string; configRef: string; toolGrants: string[] };
export type AgentEvent = {
  eventId: string;
  seq: number;
  threadId: string;
  turnId: string;
  itemId?: string;
  providerIds: { codexThreadId: string; codexTurnId: string };
  type: "text_delta" | "item_upsert" | "tool_request" | "tool_result" | "approval_request" | "approval_resolved" | "turn_completed" | "turn_cancelled" | "turn_error";
  payload: Record<string, Json>;
};

type ToolBinding = McpBinding & { toolName: string };
type PendingApproval = {
  rpcId: number;
  ownerId: string;
  threadId: string;
  turnId: string;
  requestId: string;
  paramsDigest: string;
  operation: "shell" | "write_file";
  expiresAt: number;
  timer: NodeJS.Timeout;
};

const ID = /^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$/;
const MAX_EVENTS = 512;

function record(value: unknown, message = "Codex App Server returned an invalid object"): Record<string, Json> {
  if (!value || Array.isArray(value) || typeof value !== "object") throw new Error(message);
  return value as Record<string, Json>;
}

function id(value: Json, name: string): string {
  if (typeof value !== "string" || !ID.test(value)) throw new Error(`${name} is invalid`);
  return value;
}

function nestedId(params: Record<string, Json>, key: "thread" | "turn" | "item"): string | undefined {
  const direct = params[`${key}Id`];
  if (typeof direct === "string") return direct;
  const nested = params[key];
  if (nested && !Array.isArray(nested) && typeof nested === "object" && typeof nested.id === "string") return nested.id;
  return undefined;
}

export class CodexBridge {
  private events: AgentEvent[] = [];
  private seq = 0;
  private threads = new Set<string>();
  private tools = new Map<string, Map<string, ToolBinding>>();
  private approvals = new Map<string, PendingApproval>();
  private cancelOnTurnStart = new Set<string>();

  constructor(
    private ownerId: string,
    private workspace: string,
    private client: RpcClient,
    private mcp: McpHost,
  ) {
    if (!/^[0-9a-f-]{36}$/i.test(ownerId)) throw new Error("owner id is invalid");
    this.workspace = resolve(workspace);
    client.onMessage((message) => this.receive(message));
  }

  async initialize(): Promise<Json> {
    await this.client.initialize(true);
    const account = record(await this.client.request("account/read", { refreshToken: true }, 30_000));
    if (!account.account) throw new Error("Codex managed auth is unavailable");
    return account;
  }

  async startThread(model?: string, bindings: McpBinding[] = []): Promise<Json> {
    if (model !== undefined) id(model, "model");
    const dynamicTools: Json[] = [];
    const byName = new Map<string, ToolBinding>();
    for (const binding of bindings) {
      const discovered = record(await this.mcp.discover({ ownerId: this.ownerId, ...binding }));
      if (!Array.isArray(discovered.tools)) throw new Error("MCP discovery returned invalid tools");
      for (const rawTool of discovered.tools) {
        const tool = record(rawTool, "MCP discovery returned an invalid tool");
        const toolName = id(tool.name, "MCP tool name");
        if (byName.has(toolName)) throw new Error("MCP tool name is duplicated");
        byName.set(toolName, { ...binding, toolName });
        dynamicTools.push({ name: toolName, description: typeof tool.description === "string" ? tool.description : "", inputSchema: tool.inputSchema ?? {} });
      }
    }
    const response = record(await this.client.request("thread/start", {
      cwd: this.workspace,
      sandbox: "workspace-write",
      approvalPolicy: "on-request",
      serviceName: "janus-agent-gateway",
      ...(model ? { model } : {}),
      ...(dynamicTools.length ? { dynamicTools } : {}),
    }, 30_000));
    const thread = record(response.thread);
    const threadId = id(thread.id, "Codex thread id");
    this.threads.add(threadId);
    this.tools.set(threadId, byName);
    return response;
  }

  async resumeThread(threadId: string): Promise<Json> {
    id(threadId, "Codex thread id");
    const response = await this.client.request("thread/resume", { threadId }, 30_000);
    this.threads.add(threadId);
    return response;
  }

  async forkThread(threadId: string, lastTurnId?: string): Promise<Json> {
    this.requireThread(threadId);
    if (lastTurnId) id(lastTurnId, "Codex turn id");
    const response = record(await this.client.request("thread/fork", { threadId, ...(lastTurnId ? { lastTurnId } : {}) }, 30_000));
    const childId = id(record(response.thread).id, "Codex thread id");
    this.threads.add(childId);
    this.tools.set(childId, new Map(this.tools.get(threadId)));
    return response;
  }

  async readThread(threadId: string): Promise<Json> {
    this.requireThread(threadId);
    return this.client.request("thread/read", { threadId, includeTurns: true }, 30_000);
  }

  async startTurn(threadId: string, text: string, options: { interruptOnStart?: boolean } = {}): Promise<Json> {
    this.requireThread(threadId);
    if (!text.trim() || Buffer.byteLength(text) > 32_768) throw new Error("turn input is invalid");
    if (options.interruptOnStart) this.cancelOnTurnStart.add(threadId);
    try {
      return await this.client.request("turn/start", { threadId, input: [{ type: "text", text }] }, 30_000);
    } catch (error) {
      this.cancelOnTurnStart.delete(threadId);
      throw error;
    }
  }

  interrupt(threadId: string, turnId: string): Promise<Json> {
    this.requireThread(threadId);
    id(turnId, "Codex turn id");
    return this.client.request("turn/interrupt", { threadId, turnId }, 30_000);
  }

  startDeviceLogin(): Promise<Json> {
    return this.client.request("account/login/start", { type: "chatgptDeviceCode" }, 30_000);
  }

  cancelLogin(loginId: string): Promise<Json> {
    return this.client.request("account/login/cancel", { loginId: id(loginId, "login id") }, 30_000);
  }

  resolveApproval(requestId: string, threadId: string, turnId: string, paramsDigest: string, decision: "accept" | "decline" | "cancel"): void {
    const pending = this.approvals.get(requestId);
    if (!pending || pending.ownerId !== this.ownerId || pending.threadId !== threadId || pending.turnId !== turnId || pending.paramsDigest !== paramsDigest) {
      throw new Error("approval binding mismatch");
    }
    if (Date.now() >= pending.expiresAt) throw new Error("approval expired");
    this.approvals.delete(requestId);
    clearTimeout(pending.timer);
    this.client.respond(pending.rpcId, { decision });
    this.emit(pending.threadId, pending.turnId, "approval_resolved", { requestId, paramsDigest, decision });
  }

  eventsAfter(cursor = -1): { cursor: number; events: AgentEvent[] } {
    if (!Number.isInteger(cursor) || cursor < -1) throw new Error("cursor is invalid");
    const events = this.events.filter((event) => event.seq > cursor);
    return { cursor: events.at(-1)?.seq ?? cursor, events };
  }

  private async receive(message: RpcMessage): Promise<Json | undefined> {
    if (!message.method) return undefined;
    if (typeof message.id === "number") {
      if (message.method === "item/tool/call") return this.callTool(message);
      if (message.method === "item/commandExecution/requestApproval" || message.method === "item/fileChange/requestApproval") {
        this.requestApproval(message);
        return undefined;
      }
      throw new Error("Unsupported Codex server request");
    }
    this.notification(message.method, record(message.params ?? {}));
    return undefined;
  }

  private async callTool(message: RpcMessage): Promise<Json> {
    const params = record(message.params ?? {});
    const threadId = id(params.threadId, "Codex thread id");
    const turnId = id(params.turnId, "Codex turn id");
    this.requireThread(threadId);
    const toolName = id(params.tool, "Codex tool name");
    const binding = this.tools.get(threadId)?.get(toolName);
    if (!binding) throw new Error("Codex tool is not granted");
    const requestId = randomUUID();
    this.emit(threadId, turnId, "tool_request", { requestId, toolName }, typeof params.itemId === "string" ? params.itemId : undefined);
    const result = await this.mcp.call({
      ownerId: this.ownerId,
      serverId: binding.serverId,
      configRef: binding.configRef,
      toolGrants: binding.toolGrants,
      requestId,
      toolName,
      arguments: params.arguments ?? {},
    });
    this.emit(threadId, turnId, "tool_result", { requestId, toolName, result }, typeof params.itemId === "string" ? params.itemId : undefined);
    return { contentItems: [{ type: "inputText", text: JSON.stringify(result) }], success: true };
  }

  private requestApproval(message: RpcMessage): void {
    const params = record(message.params ?? {});
    const threadId = id(params.threadId, "Codex thread id");
    const turnId = id(params.turnId, "Codex turn id");
    this.requireThread(threadId);
    if (typeof message.id !== "number") throw new Error("approval request id is invalid");
    const operation = message.method === "item/commandExecution/requestApproval" ? "shell" : "write_file";
    if (typeof params.cwd === "string" && !this.inWorkspace(params.cwd)) throw new Error("approval scope is outside the turn sandbox");
    const requestId = String(message.id);
    const paramsDigest = `sha256:${createHash("sha256").update(JSON.stringify(params)).digest("hex")}`;
    const expiresAt = Date.now() + 300_000;
    const timer = setTimeout(() => {
      if (!this.approvals.delete(requestId)) return;
      this.client.respond(message.id!, { decision: "cancel" });
      this.emit(threadId, turnId, "approval_resolved", { requestId, paramsDigest, decision: "expired" });
    }, 300_000);
    timer.unref();
    this.approvals.set(requestId, { rpcId: message.id, ownerId: this.ownerId, threadId, turnId, requestId, paramsDigest, operation, expiresAt, timer });
    this.emit(threadId, turnId, "approval_request", {
      ownerId: this.ownerId,
      threadId,
      turnId,
      requestId,
      operation,
      scope: "turn_sandbox",
      paramsDigest,
      expiresAt: new Date(expiresAt).toISOString(),
      reason: typeof params.reason === "string" ? params.reason : "Codex requested approval",
    }, typeof params.itemId === "string" ? params.itemId : undefined);
  }

  private notification(method: string, params: Record<string, Json>): void {
    if (method === "serverRequest/resolved" && (typeof params.requestId === "string" || typeof params.requestId === "number")) {
      const pending = this.approvals.get(String(params.requestId));
      if (pending) {
        clearTimeout(pending.timer);
        this.approvals.delete(pending.requestId);
        this.emit(pending.threadId, pending.turnId, "approval_resolved", { requestId: pending.requestId, paramsDigest: pending.paramsDigest, decision: "cleared" });
      }
      return;
    }
    const threadId = nestedId(params, "thread");
    const turnId = nestedId(params, "turn");
    if (!threadId || !turnId || !this.threads.has(threadId)) return;
    if (method === "turn/started" && this.cancelOnTurnStart.delete(threadId)) {
      void this.client.request("turn/interrupt", { threadId, turnId }, 30_000).catch(() => undefined);
    }
    const itemId = nestedId(params, "item");
    if (method === "item/agentMessage/delta" && typeof params.delta === "string") {
      this.emit(threadId, turnId, "text_delta", { delta: params.delta }, itemId);
    } else if (method === "item/started" || method === "item/completed") {
      this.emit(threadId, turnId, "item_upsert", { lifecycle: method.endsWith("started") ? "started" : "completed", item: params.item ?? null }, itemId);
    } else if (method === "turn/completed") {
      this.cancelOnTurnStart.delete(threadId);
      const status = record(params.turn).status;
      this.emit(threadId, turnId, status === "interrupted" ? "turn_cancelled" : status === "failed" ? "turn_error" : "turn_completed", { status: typeof status === "string" ? status : "unknown" });
    } else if (method === "error") {
      this.emit(threadId, turnId, "turn_error", { error: params.error ?? null });
    }
  }

  private emit(threadId: string, turnId: string, type: AgentEvent["type"], payload: Record<string, Json>, itemId?: string): void {
    const event: AgentEvent = {
      eventId: randomUUID(), seq: this.seq++, threadId, turnId, type, payload,
      providerIds: { codexThreadId: threadId, codexTurnId: turnId }, ...(itemId ? { itemId } : {}),
    };
    this.events.push(event);
    if (this.events.length > MAX_EVENTS) this.events.shift();
  }

  private requireThread(threadId: string): void {
    if (!this.threads.has(threadId)) throw new Error("Codex thread is not owned by this bridge");
  }

  private inWorkspace(path: string): boolean {
    const candidate = resolve(path);
    return candidate === this.workspace || candidate.startsWith(`${this.workspace}${sep}`);
  }
}
