import { spawn, type ChildProcessWithoutNullStreams } from "node:child_process";
import { createHash, createHmac, randomUUID, timingSafeEqual } from "node:crypto";
import { chmod, mkdir, mkdtemp, readFile, rm, writeFile } from "node:fs/promises";
import { createServer, type IncomingMessage, type ServerResponse } from "node:http";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { createInterface } from "node:readline";
import { CodexBridge, type AgentEvent } from "./codex_bridge.js";
import { dispatchAssistant } from "./assistant_dispatch.js";
import { McpHost } from "./mcp_host.js";

export type Json = null | boolean | number | string | Json[] | { [key: string]: Json };
export type RpcMessage = { id?: number; method?: string; params?: Json; result?: Json; error?: { code?: number; message?: string } };
type Pending = { resolve: (value: Json) => void; reject: (error: Error) => void; timer: NodeJS.Timeout };
type RpcHandler = (message: RpcMessage) => Promise<Json | undefined> | Json | undefined;

const CODEX_VERSION = "0.153.4";
const JSON_HEADERS = { "content-type": "application/json" };
const ID = /^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$/;

function loadAgentBundle(): void {
  const raw = process.env.JANUS_AGENT_PROVIDER_BUNDLE?.trim();
  if (!raw) return;
  const bundle = JSON.parse(raw) as Record<string, unknown>;
  for (const [target, source] of Object.entries({
    GEMINI_API_KEY: "gemini_api_key",
    OPENROUTER_API_KEY: "openrouter_api_key",
    MCP_OWNER_SIGNING_KEY: "mcp_owner_signing_key",
  })) {
    if (!process.env[target] && typeof bundle[source] === "string" && bundle[source].trim()) {
      process.env[target] = bundle[source].trim();
    }
  }
}

loadAgentBundle();

export class AppServerClient {
  private child?: ChildProcessWithoutNullStreams;
  private nextId = 1;
  private pending = new Map<number, Pending>();
  private handler?: RpcHandler;
  private failureHandler?: (error: Error) => void;

  constructor(
    private command = process.env.CODEX_BIN || "codex",
    private prefixArgs: string[] = [],
    private home = process.env.CODEX_HOME,
  ) {}

  start(): void {
    if (this.child) throw new Error("Codex App Server is already running");
    this.child = spawn(this.command, [...this.prefixArgs, "app-server", "--stdio"], {
      env: { ...process.env, ...(this.home ? { CODEX_HOME: this.home } : {}) },
      stdio: ["pipe", "pipe", "pipe"],
    });
    createInterface({ input: this.child.stdout }).on("line", (line) => this.receive(line));
    this.child.stderr.resume();
    this.child.once("error", (error) => this.fail(error));
    this.child.once("exit", (code) => this.fail(new Error(`Codex App Server exited (${code ?? "signal"})`)));
  }

  async initialize(experimentalApi = false): Promise<Json> {
    const result = await this.request("initialize", {
      clientInfo: { name: "janus-agent-gateway", version: "0.1.0" },
      capabilities: { experimentalApi },
    });
    this.notify("initialized", {});
    return result;
  }

  onMessage(handler: RpcHandler): void {
    this.handler = handler;
  }

  onFailure(handler: (error: Error) => void): void {
    this.failureHandler = handler;
  }

  request(method: string, params: Json = {}, timeoutMs = 15_000): Promise<Json> {
    if (!this.child) return Promise.reject(new Error("Codex App Server is not running"));
    const id = this.nextId++;
    return new Promise((resolve, reject) => {
      const timer = setTimeout(() => {
        this.pending.delete(id);
        reject(new Error(`Codex App Server request timed out: ${method}`));
      }, timeoutMs);
      this.pending.set(id, { resolve, reject, timer });
      this.child!.stdin.write(`${JSON.stringify({ jsonrpc: "2.0", id, method, params })}\n`);
    });
  }

  notify(method: string, params: Json = {}): void {
    this.child?.stdin.write(`${JSON.stringify({ jsonrpc: "2.0", method, params })}\n`);
  }

  respond(id: number, result: Json): void {
    this.child?.stdin.write(`${JSON.stringify({ jsonrpc: "2.0", id, result })}\n`);
  }

  async stop(): Promise<void> {
    const child = this.child;
    this.child = undefined;
    if (child && child.exitCode === null) {
      const exited = new Promise<void>((resolve) => child.once("exit", () => resolve()));
      child.stdin.end();
      child.kill("SIGTERM");
      await Promise.race([exited, new Promise<void>((resolve) => setTimeout(resolve, 2_000))]);
      if (child.exitCode === null) {
        child.kill("SIGKILL");
        await exited;
      }
    }
    this.fail(new Error("Codex App Server stopped"));
  }

  private receive(line: string): void {
    let message: RpcMessage;
    try {
      message = JSON.parse(line) as RpcMessage;
    } catch {
      this.fail(new Error("Codex App Server emitted invalid JSONL"));
      return;
    }
    if (message.method) {
      void this.dispatch(message);
      return;
    }
    if (typeof message.id !== "number") return;
    const pending = this.pending.get(message.id);
    if (!pending) return;
    clearTimeout(pending.timer);
    this.pending.delete(message.id);
    if (message.error) pending.reject(new Error(message.error.message || "Codex App Server request failed"));
    else pending.resolve(message.result ?? null);
  }

  private async dispatch(message: RpcMessage): Promise<void> {
    if (!this.handler) {
      if (typeof message.id === "number") this.writeError(message.id, -32601, "Client does not handle server requests");
      return;
    }
    try {
      const result = await this.handler(message);
      if (typeof message.id === "number" && result !== undefined) this.respond(message.id, result);
    } catch (error) {
      if (typeof message.id === "number") this.writeError(message.id, -32000, error instanceof Error ? error.message : "Client request failed");
    }
  }

  private writeError(id: number, code: number, message: string): void {
    this.child?.stdin.write(`${JSON.stringify({ jsonrpc: "2.0", id, error: { code, message } })}\n`);
  }

  private fail(error: Error): void {
    for (const pending of this.pending.values()) {
      clearTimeout(pending.timer);
      pending.reject(error);
    }
    this.pending.clear();
    this.failureHandler?.(error);
  }
}

async function accessToken(fetcher: typeof fetch): Promise<string> {
  const response = await fetcher("http://metadata.google.internal/computeMetadata/v1/instance/service-accounts/default/token", {
    headers: { "Metadata-Flavor": "Google" },
  });
  if (!response.ok) throw new Error(`service identity token unavailable (${response.status})`);
  const body = await response.json() as { access_token?: string };
  if (!body.access_token) throw new Error("service identity token missing");
  return body.access_token;
}

async function googleJson(fetcher: typeof fetch, url: string, init: RequestInit = {}): Promise<Json> {
  const token = await accessToken(fetcher);
  const response = await fetcher(url, {
    ...init,
    headers: { authorization: `Bearer ${token}`, ...JSON_HEADERS, ...init.headers },
  });
  if (!response.ok) {
    const error = new Error(`Google API request failed (${response.status})`) as Error & { status: number };
    error.status = response.status;
    throw error;
  }
  return response.json() as Promise<Json>;
}

export class OwnerAuthRegistry {
  private constructor(private resources: Map<string, string>) {}

  static parse(value: string): OwnerAuthRegistry {
    const parsed = JSON.parse(value) as unknown;
    if (!parsed || Array.isArray(parsed) || typeof parsed !== "object") throw new Error("CODEX_OWNER_SECRETS is invalid");
    const resources = new Map<string, string>();
    for (const [ownerId, resource] of Object.entries(parsed)) {
      if (!/^[0-9a-f-]{36}$/i.test(ownerId) || typeof resource !== "string" || !/^projects\/[^/]+\/secrets\/[^/]+$/.test(resource)) {
        throw new Error("CODEX_OWNER_SECRETS is invalid");
      }
      resources.set(ownerId.toLowerCase(), resource);
    }
    if (!resources.size) throw new Error("CODEX_OWNER_SECRETS is empty");
    return new OwnerAuthRegistry(resources);
  }

  resource(ownerId: string): string {
    if (!/^[0-9a-f-]{36}$/i.test(ownerId)) throw new Error("owner id is invalid");
    const resource = this.resources.get(ownerId.toLowerCase());
    if (!resource) throw new Error("owner is not allowlisted for Codex");
    return resource;
  }
}

export class ManagedAuthStore {
  private digest?: string;
  private version?: string;

  constructor(private resource: string, private fetcher: typeof fetch = fetch) {
    if (!/^projects\/[^/]+\/secrets\/[^/]+$/.test(resource)) throw new Error("CODEX_AUTH_SECRET is invalid");
  }

  async load(home: string): Promise<void> {
    const body = await googleJson(this.fetcher, `https://secretmanager.googleapis.com/v1/${this.resource}/versions/latest:access`) as { name?: string; payload?: { data?: string } };
    if (!body.payload?.data) throw new Error("Codex managed auth secret is empty");
    const raw = Buffer.from(body.payload.data, "base64");
    JSON.parse(raw.toString("utf8"));
    await mkdir(home, { recursive: true, mode: 0o700 });
    await writeFile(join(home, "auth.json"), raw, { mode: 0o600 });
    await chmod(join(home, "auth.json"), 0o600);
    this.digest = createHash("sha256").update(raw).digest("hex");
    this.version = body.name;
  }

  async persist(home: string): Promise<boolean> {
    const raw = await readFile(join(home, "auth.json"));
    const digest = createHash("sha256").update(raw).digest("hex");
    const rotated = digest !== this.digest;
    if (rotated) {
      const added = await googleJson(this.fetcher, `https://secretmanager.googleapis.com/v1/${this.resource}:addVersion`, {
        method: "POST",
        body: JSON.stringify({ payload: { data: raw.toString("base64") } }),
      }) as { name?: string };
      if (!added.name) throw new Error("Codex managed auth version name missing");
      const verified = await googleJson(this.fetcher, `https://secretmanager.googleapis.com/v1/${added.name}:access`) as { payload?: { data?: string } };
      if (!verified.payload?.data || createHash("sha256").update(Buffer.from(verified.payload.data, "base64")).digest("hex") !== digest) {
        throw new Error("Codex managed auth rotation verification failed");
      }
      this.digest = digest;
      this.version = added.name;
    }
    await this.destroyVersions(this.version);
    return rotated;
  }

  async destroy(): Promise<void> {
    await this.destroyVersions();
    this.digest = undefined;
    this.version = undefined;
  }

  private async destroyVersions(keep?: string): Promise<void> {
    let pageToken = "";
    do {
      const query = new URLSearchParams({ pageSize: "100", ...(pageToken ? { pageToken } : {}) });
      let body: { versions?: Array<{ name?: string; state?: string }>; nextPageToken?: string };
      try {
        body = await googleJson(this.fetcher, `https://secretmanager.googleapis.com/v1/${this.resource}/versions?${query}`) as typeof body;
      } catch (error) {
        if ((error as Error & { status?: number }).status === 404) return;
        throw error;
      }
      for (const version of body.versions ?? []) {
        if (version.name && version.name !== keep && version.state !== "DESTROYED") {
          await googleJson(this.fetcher, `https://secretmanager.googleapis.com/v1/${version.name}:destroy`, { method: "POST", body: "{}" });
        }
      }
      pageToken = body.nextPageToken ?? "";
    } while (pageToken);
  }
}

type LoginSession = {
  ownerId: string;
  root: string;
  home: string;
  auth: ManagedAuthStore;
  client: AppServerClient;
  timer: NodeJS.Timeout;
};

export class OwnerSessionRegistry {
  private sessions = new Map<string, LoginSession>();

  async start(ownerId: string, authSecret: string): Promise<Json> {
    const key = ownerId.toLowerCase();
    if (this.sessions.has(key)) throw new Error("owner login session already exists");
    const root = await mkdtemp(join(process.env.SANDBOX_ROOT || tmpdir(), "login-"));
    const home = join(root, "codex-home");
    const client = new AppServerClient(process.env.CODEX_BIN || "codex", [], home);
    try {
      await mkdir(home, { recursive: true, mode: 0o700 });
      client.start();
      await client.initialize();
      const result = object(await client.request("account/login/start", { type: "chatgptDeviceCode" }, 30_000));
      const loginId = typeof result.loginId === "string" ? result.loginId : "";
      if (!loginId) throw new Error("Codex login id missing");
      const timer = setTimeout(() => { void this.evict(ownerId, false); }, 10 * 60_000);
      timer.unref();
      this.sessions.set(key, { ownerId, root, home, auth: new ManagedAuthStore(authSecret), client, timer });
      const safe = Object.fromEntries(Object.entries(result).filter(([name, value]) => name !== "loginId" && ["authUrl", "verificationUrl", "userCode", "verificationUri", "verificationUriComplete", "expiresAt", "interval"].includes(name) && ["string", "number"].includes(typeof value)));
      return { ownerId, loginId, ...safe } as Json;
    } catch (error) {
      await client.stop();
      await rm(root, { recursive: true, force: true });
      throw error;
    }
  }

  async status(ownerId: string): Promise<Json> {
    const session = this.sessions.get(ownerId.toLowerCase());
    if (!session) throw new Error("owner login session not found");
    const account = object(await session.client.request("account/read", { refreshToken: true }, 30_000));
    if (!account.account) return { ownerId, status: "PENDING" };
    return { ownerId, status: "AUTHENTICATED", authRotated: await session.auth.persist(session.home) };
  }

  async evict(ownerId: string, logout: boolean): Promise<boolean> {
    const key = ownerId.toLowerCase();
    const session = this.sessions.get(key);
    if (!session) return false;
    this.sessions.delete(key);
    clearTimeout(session.timer);
    try {
      if (logout) await session.client.request("account/logout", {}, 30_000);
    } finally {
      await session.client.stop();
      await rm(session.root, { recursive: true, force: true });
    }
    return true;
  }
}

export class GcsCheckpointStore {
  constructor(private bucket: string, private fetcher: typeof fetch = fetch) {
    if (!/^[a-z0-9][a-z0-9._-]{1,220}[a-z0-9]$/.test(bucket)) throw new Error("AGENT_CHECKPOINT_BUCKET is invalid");
  }

  async put(id: string, value: Json): Promise<void> {
    const name = `agent-poc/${id}.json`;
    await googleJson(this.fetcher, `https://storage.googleapis.com/upload/storage/v1/b/${encodeURIComponent(this.bucket)}/o?uploadType=media&name=${encodeURIComponent(name)}`, {
      method: "POST",
      body: JSON.stringify(value),
    });
  }

  async get(id: string): Promise<Json> {
    const name = encodeURIComponent(`agent-poc/${id}.json`);
    return googleJson(this.fetcher, `https://storage.googleapis.com/storage/v1/b/${encodeURIComponent(this.bucket)}/o/${name}?alt=media`);
  }
}

type Checkpoint = { checkpointId: string; events: AgentEvent[] };

type CodexTurnSession = {
  ownerId: string;
  threadId: string;
  nativeThreadId: string;
  turnId: string;
  nativeTurnId: string;
  bridge: CodexBridge;
  client: AppServerClient;
  mcp: McpHost;
  root: string;
  lastReturnedSeq: number;
  timer: NodeJS.Timeout;
  cleanupPending?: string[];
};

/** Short-lived in-memory handles are intentional: the native approval RPC is process-bound. */
export class CodexTurnRegistry {
  private sessions = new Map<string, CodexTurnSession>();

  async start(ownerId: string, threadId: string, turnId: string, model: string,
    messages: Array<{ role?: string; content?: string }>, continuation: Record<string, Json>): Promise<Json> {
    if (!/^[0-9a-f-]{36}$/i.test(ownerId) || !ID.test(threadId) || !ID.test(turnId) || !ID.test(model)) {
      throw new Error("codex turn binding is invalid");
    }
    if (!messages.length || messages.some((message) => !message || typeof message.content !== "string" || !message.content.trim())) {
      throw new Error("codex turn messages are invalid");
    }
    if (continuation.runtime !== undefined && continuation.runtime !== "codex") throw new Error("codex continuation runtime is invalid");
    const resource = OwnerAuthRegistry.parse(process.env.CODEX_OWNER_SECRETS || "").resource(ownerId);
    const root = await mkdtemp(join(process.env.SANDBOX_ROOT || tmpdir(), "chat-turn-"));
    const home = join(root, "codex-home");
    const workspace = join(root, "workspace");
    const client = new AppServerClient(process.env.CODEX_BIN || "codex", [], home);
    const mcp = new McpHost();
    try {
      await mkdir(workspace, { mode: 0o700 });
      await new ManagedAuthStore(resource).load(home);
      client.start();
      const bridge = new CodexBridge(ownerId, workspace, client, mcp);
      client.onFailure(() => bridge.processError());
      await bridge.initialize();
      let nativeThread = typeof continuation.codexThreadId === "string" ? continuation.codexThreadId : "";
      if (!nativeThread) {
        const started = object(await bridge.startThread(model));
        nativeThread = typeof object(started.thread ?? null).id === "string" ? String(object(started.thread ?? null).id) : "";
      }
      if (!nativeThread) throw new Error("Codex thread id is missing");
      if (typeof continuation.codexThreadId === "string") await bridge.resumeThread(nativeThread);
      const started = object(await bridge.startTurn(nativeThread, messages.at(-1)?.content || ""));
      const nativeTurnId = typeof object(started.turn ?? null).id === "string" ? String(object(started.turn ?? null).id) : "";
      if (!nativeTurnId) throw new Error("Codex turn id is missing");
      const handle = randomUUID();
      const timer = setTimeout(() => void this.expire(handle), 600_000);
      timer.unref();
      this.sessions.set(handle, { ownerId, threadId, nativeThreadId: nativeThread, turnId, nativeTurnId,
        bridge, client, mcp, root, lastReturnedSeq: -1, timer });
      return this.wait(handle);
    } catch (error) {
      await Promise.allSettled([client.stop(), mcp.closeAll(), rm(root, { recursive: true, force: true })]);
      throw error;
    }
  }

  async wait(handle: string): Promise<Json> {
    const session = this.sessions.get(handle);
    if (!session) throw new Error("turn handle not found");
    for (let attempt = 0; attempt < 600; attempt++) {
      const events = session.bridge.eventsAfter(session.lastReturnedSeq).events.filter((event) => event.turnId === session.nativeTurnId);
      const terminal = events.find((event) => ["turn_completed", "turn_cancelled", "turn_error"].includes(event.type));
      const approval = events.find((event) => event.type === "approval_request");
      if (terminal || approval) {
        if (events.length) session.lastReturnedSeq = events.at(-1)!.seq;
        const status = terminal?.type === "turn_cancelled" ? "CANCELLED" : terminal?.type === "turn_error" ? "ERROR" : terminal ? "COMPLETED" : "AWAITING_APPROVAL";
        const result = { status, turnHandle: handle, ownerId: session.ownerId, threadId: session.threadId,
          nativeThreadId: session.nativeThreadId, turnId: session.turnId, nativeTurnId: session.nativeTurnId,
          cursor: session.lastReturnedSeq, events,
          continuation: { runtime: "codex", codexThreadId: session.nativeThreadId, codexTurnId: session.nativeTurnId, turnHandle: handle } };
        if (terminal) {
          await this.cleanup(handle);
          if (session.cleanupPending?.length) return { ...result, status: "CLEANUP_PENDING", cleanupPending: session.cleanupPending } as unknown as Json;
        }
        return result as unknown as Json;
      }
      await new Promise((resolve) => setTimeout(resolve, 50));
    }
    return { status: "IN_PROGRESS", turnHandle: handle, ownerId: session.ownerId, threadId: session.threadId,
      nativeThreadId: session.nativeThreadId, turnId: session.turnId, nativeTurnId: session.nativeTurnId, cursor: session.lastReturnedSeq,
      events: [], continuation: { runtime: "codex", codexThreadId: session.nativeThreadId, codexTurnId: session.nativeTurnId, turnHandle: handle } } as unknown as Json;
  }

  async resolve(handle: string, ownerId: string, threadId: string, nativeThreadId: string, turnId: string, nativeTurnId: string,
    requestId: string,
    paramsDigest: string, decision: "accept" | "decline" | "cancel"): Promise<Json> {
    const session = this.sessions.get(handle);
    if (!session || session.ownerId !== ownerId || session.threadId !== threadId || session.nativeThreadId !== nativeThreadId || session.turnId !== turnId || session.nativeTurnId !== nativeTurnId) throw new Error("turn handle binding mismatch");
    session.bridge.resolveApproval(requestId, nativeThreadId, nativeTurnId, paramsDigest, decision);
    return this.wait(handle);
  }

  async cancel(handle: string, ownerId: string, threadId: string, nativeThreadId: string, turnId: string, nativeTurnId: string): Promise<Json> {
    const session = this.sessions.get(handle);
    if (!session || session.ownerId !== ownerId || session.threadId !== threadId || session.nativeThreadId !== nativeThreadId || session.turnId !== turnId || session.nativeTurnId !== nativeTurnId) throw new Error("turn handle binding mismatch");
    await session.bridge.interrupt(nativeThreadId, nativeTurnId);
    return this.wait(handle);
  }

  async events(handle: string, ownerId: string, threadId: string, nativeThreadId: string, turnId: string, nativeTurnId: string, cursor: number): Promise<Json> {
    const session = this.sessions.get(handle);
    if (!session || session.ownerId !== ownerId || session.threadId !== threadId || session.nativeThreadId !== nativeThreadId || session.turnId !== turnId || session.nativeTurnId !== nativeTurnId) throw new Error("turn handle binding mismatch");
    if (!Number.isInteger(cursor) || cursor < -1) throw new Error("cursor is invalid");
    const result = session.bridge.eventsAfter(cursor);
    const events = result.events.filter((event) => event.turnId === session.nativeTurnId);
    if (events.some((event) => ["turn_completed", "turn_cancelled", "turn_error"].includes(event.type))) await this.cleanup(handle);
    return { ...result, events, ownerId, threadId, nativeThreadId, turnId, nativeTurnId,
      continuation: { runtime: "codex", codexThreadId: nativeThreadId, codexTurnId: nativeTurnId, turnHandle: handle } } as unknown as Json;
  }

  private async expire(handle: string): Promise<void> {
    const session = this.sessions.get(handle);
    if (!session) return;
    session.bridge.processError();
    await this.cleanup(handle);
  }

  private async cleanup(handle: string): Promise<void> {
    const session = this.sessions.get(handle);
    if (!session) return;
    const results = await Promise.allSettled([session.client.stop(), session.mcp.closeAll(), rm(session.root, { recursive: true, force: true })]);
    const pending = results.flatMap((result, index) => result.status === "rejected" ? [(["app_server", "mcp", "sandbox"] as const)[index]] : []);
    if (pending.length) {
      session.cleanupPending = pending;
      return;
    }
    this.sessions.delete(handle);
    clearTimeout(session.timer);
  }
}

async function dispatchCodexTurn(ownerId: string, threadId: string, model: string,
  messages: Array<{ role?: string; content?: string }>, continuation: Record<string, Json>): Promise<Json> {
  const resource = OwnerAuthRegistry.parse(process.env.CODEX_OWNER_SECRETS || "").resource(ownerId);
  const root = await mkdtemp(join(process.env.SANDBOX_ROOT || tmpdir(), "chat-turn-"));
  const home = join(root, "codex-home");
  const workspace = join(root, "workspace");
  const client = new AppServerClient(process.env.CODEX_BIN || "codex", [], home);
  const mcp = new McpHost();
  try {
    await mkdir(workspace, { mode: 0o700 });
    await new ManagedAuthStore(resource).load(home);
    client.start();
    const bridge = new CodexBridge(ownerId, workspace, client, mcp);
    await bridge.initialize();
    let nativeThread = typeof continuation.codexThreadId === "string" ? continuation.codexThreadId : "";
    if (!nativeThread) {
      const started = object(await bridge.startThread(model));
      const thread = object(started.thread ?? null);
      nativeThread = typeof thread.id === "string" ? thread.id : "";
    }
    if (!nativeThread) throw new Error("Codex thread id is missing");
    if (typeof continuation.codexThreadId === "string") await bridge.resumeThread(nativeThread);
    const text = messages.at(-1)?.content || "";
    const started = object(await bridge.startTurn(nativeThread, text));
    const nativeTurn = object(started.turn ?? null);
    const nativeTurnId = typeof nativeTurn.id === "string" ? nativeTurn.id : "";
    if (!nativeTurnId) throw new Error("Codex turn id is missing");
    for (let attempt = 0; attempt < 600; attempt++) {
      const events = bridge.eventsAfter(-1).events;
      if (events.some((event) => event.turnId === nativeTurnId && ["turn_completed", "turn_cancelled", "turn_error"].includes(event.type))) {
        return { events: events.filter((event) => event.turnId === nativeTurnId) as unknown as Json[],
          continuation: { runtime: "codex", codexThreadId: nativeThread, codexTurnId: nativeTurnId, model } };
      }
      await new Promise((resolve) => setTimeout(resolve, 50));
    }
    throw new Error("Codex turn did not reach a terminal event");
  } finally {
    await client.stop();
    await mcp.closeAll();
    await rm(root, { recursive: true, force: true });
  }
}

function object(value: Json): { [key: string]: Json } {
  if (!value || Array.isArray(value) || typeof value !== "object") throw new Error("Codex App Server returned an invalid object");
  return value;
}

export async function runPoc(ownerId: string, authSecret: string): Promise<Json> {
  const bucket = process.env.AGENT_CHECKPOINT_BUCKET;
  if (!bucket) throw new Error("external checkpoint setting is required");

  const root = await mkdtemp(join(process.env.SANDBOX_ROOT || tmpdir(), "turn-"));
  const home = join(root, "codex-home");
  const workspace = join(root, "workspace");
  const auth = new ManagedAuthStore(authSecret);
  const checkpoints = new GcsCheckpointStore(bucket);
  const client = new AppServerClient(process.env.CODEX_BIN || "codex", [], home);
  const mcp = new McpHost();
  try {
    await mkdir(workspace, { mode: 0o700 });
    await auth.load(home);
    client.start();
    const bridge = new CodexBridge(ownerId, workspace, client, mcp);
    await bridge.initialize();
    const thread = object(await bridge.startThread());
    const nativeThread = object(thread.thread ?? null);
    if (typeof nativeThread.id !== "string") throw new Error("Codex thread/start did not return a thread id");
    const started = object(await bridge.startTurn(nativeThread.id, "Run the sandbox shell command `sleep 30` before replying. Do not skip the command.", { interruptOnStart: true }));
    const nativeTurn = object(started.turn ?? null);
    if (typeof nativeTurn.id !== "string") throw new Error("Codex turn/start did not return a turn id");
    for (let attempt = 0; attempt < 40 && !bridge.eventsAfter().events.some((event) => event.type === "turn_cancelled"); attempt++) {
      await new Promise((resolve) => setTimeout(resolve, 50));
    }
    const events = bridge.eventsAfter().events;
    if (!events.some((event) => event.type === "turn_cancelled")) throw new Error("Codex cancellation event was not received");
    const checkpointId = randomUUID();
    const checkpoint: Checkpoint = { checkpointId, events };
    const authRotated = await auth.persist(home);
    await checkpoints.put(checkpointId, checkpoint as unknown as Json);
    return { ownerId, codexVersion: CODEX_VERSION, checkpointId, cursor: events.at(-1)!.seq, authRotated, sandbox: "workspace-write", cancelled: true, process: "stopped-after-response" };
  } finally {
    await client.stop();
    await mcp.closeAll();
    await rm(root, { recursive: true, force: true });
  }
}

export async function logoutOwner(ownerId: string, authSecret: string): Promise<void> {
  const root = await mkdtemp(join(process.env.SANDBOX_ROOT || tmpdir(), "logout-"));
  const home = join(root, "codex-home");
  const client = new AppServerClient(process.env.CODEX_BIN || "codex", [], home);
  try {
    await new ManagedAuthStore(authSecret).load(home);
    client.start();
    await client.initialize();
    await client.request("account/logout", {}, 30_000);
  } finally {
    await client.stop();
    await rm(root, { recursive: true, force: true });
  }
}

function send(response: ServerResponse, status: number, body: Json): void {
  response.writeHead(status, JSON_HEADERS);
  response.end(JSON.stringify(body));
}

async function signedBody(request: IncomingMessage): Promise<Json> {
  const key = process.env.MCP_OWNER_SIGNING_KEY;
  const timestamp = request.headers["x-janus-timestamp"];
  const signature = request.headers["x-janus-signature"];
  if (!key || key.length < 32 || typeof timestamp !== "string" || typeof signature !== "string") {
    throw new Error("MCP internal authentication is unavailable");
  }
  const issuedAt = Number(timestamp);
  if (!Number.isInteger(issuedAt) || Math.abs(Date.now() - issuedAt) > 60_000) throw new Error("MCP internal request expired");
  const chunks: Buffer[] = [];
  let bytes = 0;
  for await (const chunk of request) {
    const value = Buffer.from(chunk);
    bytes += value.length;
    if (bytes > 131_072) throw new Error("MCP internal request is too large");
    chunks.push(value);
  }
  const body = Buffer.concat(chunks);
  const expected = createHmac("sha256", key).update(timestamp).update(".").update(body).digest();
  const supplied = Buffer.from(signature.replace(/^v1=/, ""), "hex");
  if (supplied.length !== expected.length || !timingSafeEqual(supplied, expected)) throw new Error("MCP internal authentication failed");
  return JSON.parse(body.toString("utf8")) as Json;
}

export function makeServer(mcp = new McpHost(), sessions = new OwnerSessionRegistry(), turns = new CodexTurnRegistry()) {
  let running = false;
  return createServer(async (request: IncomingMessage, response: ServerResponse) => {
    const url = new URL(request.url || "/", "http://localhost");
    if (request.method === "GET" && url.pathname === "/health") {
      send(response, 200, { status: "ok", codexVersion: CODEX_VERSION });
      return;
    }
    if (request.method === "POST" && url.pathname === "/internal/v1/poc/codex") {
      if (process.env.CODEX_POC_ENABLED !== "true") return send(response, 404, { error: "not_found" });
      if (running) return send(response, 409, { error: "probe_already_running" });
      running = true;
      try {
        const body = object(await signedBody(request));
        const ownerId = typeof body.ownerId === "string" ? body.ownerId : "";
        if (body.ownerState !== "ACTIVE") throw new Error("owner is not active");
        const resource = OwnerAuthRegistry.parse(process.env.CODEX_OWNER_SECRETS || "").resource(ownerId);
        send(response, 200, await runPoc(ownerId, resource));
      } catch (error) {
        send(response, 400, { error: error instanceof Error ? error.message : "probe_failed" });
      } finally {
        running = false;
      }
      return;
    }
    if (request.method === "POST" && url.pathname === "/internal/v1/codex/auth:destroy") {
      try {
        const body = object(await signedBody(request));
        const ownerId = typeof body.ownerId === "string" ? body.ownerId : "";
        const resource = OwnerAuthRegistry.parse(process.env.CODEX_OWNER_SECRETS || "").resource(ownerId);
        await sessions.evict(ownerId, true);
        await new ManagedAuthStore(resource).destroy();
        send(response, 200, { ownerId, destroyed: true });
      } catch (error) {
        send(response, 400, { error: error instanceof Error ? error.message : "auth_destroy_failed" });
      }
      return;
    }
    if (request.method === "POST" && url.pathname === "/internal/v1/codex/session:logout") {
      if (running) return send(response, 409, { error: "session_busy" });
      running = true;
      try {
        const body = object(await signedBody(request));
        const ownerId = typeof body.ownerId === "string" ? body.ownerId : "";
        const resource = OwnerAuthRegistry.parse(process.env.CODEX_OWNER_SECRETS || "").resource(ownerId);
        if (!await sessions.evict(ownerId, true)) await logoutOwner(ownerId, resource);
        send(response, 200, { ownerId, loggedOut: true, sessionEvicted: true });
      } catch (error) {
        const status = (error as Error & { status?: number }).status === 404 ? 200 : 400;
        send(response, status, status === 200 ? { loggedOut: true, sessionEvicted: true } : { error: error instanceof Error ? error.message : "logout_failed" });
      } finally {
        running = false;
      }
      return;
    }
    if (request.method === "POST" && url.pathname === "/internal/v1/codex/session:login-start") {
      try {
        const body = object(await signedBody(request));
        const ownerId = typeof body.ownerId === "string" ? body.ownerId : "";
        const resource = OwnerAuthRegistry.parse(process.env.CODEX_OWNER_SECRETS || "").resource(ownerId);
        send(response, 200, await sessions.start(ownerId, resource));
      } catch (error) {
        send(response, 400, { error: error instanceof Error ? error.message : "login_start_failed" });
      }
      return;
    }
    if (request.method === "POST" && url.pathname === "/internal/v1/codex/session:login-status") {
      try {
        const body = object(await signedBody(request));
        const ownerId = typeof body.ownerId === "string" ? body.ownerId : "";
        OwnerAuthRegistry.parse(process.env.CODEX_OWNER_SECRETS || "").resource(ownerId);
        send(response, 200, await sessions.status(ownerId));
      } catch (error) {
        send(response, 400, { error: error instanceof Error ? error.message : "login_status_failed" });
      }
      return;
    }
    if (request.method === "POST" && url.pathname === "/internal/v1/assistant/turn:start") {
      try {
        const body = object(await signedBody(request));
        if (body.runtime !== "codex" || typeof body.ownerId !== "string" || typeof body.threadId !== "string" || typeof body.turnId !== "string" || typeof body.model !== "string" || !Array.isArray(body.messages)) throw new Error("codex turn start request is invalid");
        const continuation = body.continuation && typeof body.continuation === "object" && !Array.isArray(body.continuation) ? body.continuation as Record<string, Json> : {};
        send(response, 200, await turns.start(body.ownerId, body.threadId, body.turnId, body.model, body.messages as Array<{ role?: string; content?: string }>, continuation));
      } catch (error) {
        send(response, 400, { error: error instanceof Error ? error.message : "codex_turn_start_failed" });
      }
      return;
    }
    if (request.method === "POST" && url.pathname === "/internal/v1/assistant/turn:events") {
      try {
        const body = object(await signedBody(request));
        if (typeof body.turnHandle !== "string" || typeof body.ownerId !== "string" || typeof body.threadId !== "string" || typeof body.nativeThreadId !== "string" || typeof body.turnId !== "string" || typeof body.nativeTurnId !== "string") throw new Error("turn events binding is invalid");
        const cursor = body.cursor === undefined ? -1 : Number(body.cursor);
        send(response, 200, await turns.events(body.turnHandle, body.ownerId, body.threadId, body.nativeThreadId, body.turnId, body.nativeTurnId, cursor));
      } catch (error) {
        send(response, 400, { error: error instanceof Error ? error.message : "codex_turn_events_failed" });
      }
      return;
    }
    if (request.method === "POST" && url.pathname === "/internal/v1/assistant/approval") {
      try {
        const body = object(await signedBody(request));
        if (typeof body.turnHandle !== "string" || typeof body.ownerId !== "string" || typeof body.requestId !== "string" || typeof body.threadId !== "string" || typeof body.nativeThreadId !== "string" || typeof body.turnId !== "string" || typeof body.nativeTurnId !== "string" || typeof body.paramsDigest !== "string" || !["accept", "decline", "cancel"].includes(String(body.decision))) throw new Error("approval request is invalid");
        send(response, 200, await turns.resolve(body.turnHandle, body.ownerId, body.threadId, body.nativeThreadId, body.turnId, body.nativeTurnId, body.requestId, body.paramsDigest, body.decision as "accept" | "decline" | "cancel"));
      } catch (error) {
        send(response, 400, { error: error instanceof Error ? error.message : "codex_approval_failed" });
      }
      return;
    }
    if (request.method === "POST" && url.pathname === "/internal/v1/assistant/turn:cancel") {
      try {
        const body = object(await signedBody(request));
        if (typeof body.turnHandle !== "string" || typeof body.ownerId !== "string" || typeof body.threadId !== "string" || typeof body.nativeThreadId !== "string" || typeof body.turnId !== "string" || typeof body.nativeTurnId !== "string") throw new Error("cancel request is invalid");
        send(response, 200, await turns.cancel(body.turnHandle, body.ownerId, body.threadId, body.nativeThreadId, body.turnId, body.nativeTurnId));
      } catch (error) {
        send(response, 400, { error: error instanceof Error ? error.message : "codex_turn_cancel_failed" });
      }
      return;
    }
    if (request.method === "POST" && url.pathname === "/internal/v1/assistant/turn") {
      try {
        const body = object(await signedBody(request));
        const runtime = body.runtime;
        if (runtime !== "openrouter" && runtime !== "gemini" && runtime !== "codex") throw new Error("runtime dispatch is unavailable");
        if (typeof body.ownerId !== "string" || typeof body.threadId !== "string" || typeof body.turnId !== "string" || typeof body.model !== "string" || !Array.isArray(body.messages)) throw new Error("assistant turn request is invalid");
        if (body.grounding !== undefined && typeof body.grounding !== "boolean") throw new Error("grounding is invalid");
        const continuation = body.continuation && typeof body.continuation === "object" && !Array.isArray(body.continuation) ? body.continuation as Record<string, Json> : {};
        send(response, 200, runtime === "codex"
          ? await dispatchCodexTurn(body.ownerId, body.threadId, body.model, body.messages as Array<{ role?: string; content?: string }>, continuation)
          : await dispatchAssistant({ ownerId: body.ownerId, threadId: body.threadId,
            turnId: body.turnId, runtime, model: body.model, messages: body.messages as never[], grounding: body.grounding === true, continuation }));
      } catch (error) {
        send(response, 400, { error: error instanceof Error ? error.message : "assistant_turn_failed" });
      }
      return;
    }
    const mcpMethod = request.method === "POST" && /^\/internal\/v1\/mcp\/(discover|call|cancel|disconnect)$/.exec(url.pathname)?.[1];
    if (mcpMethod) {
      if (process.env.MCP_HOST_ENABLED !== "true") return send(response, 404, { error: "not_found" });
      try {
        const body = await signedBody(request);
        const result = mcpMethod === "discover" ? await mcp.discover(body)
          : mcpMethod === "call" ? await mcp.call(body)
          : mcpMethod === "cancel" ? mcp.cancel(body)
          : await mcp.disconnect(body);
        send(response, 200, result);
      } catch (error) {
        send(response, 400, { error: error instanceof Error ? error.message : "mcp_request_failed" });
      }
      return;
    }
    const match = /^\/internal\/v1\/poc\/checkpoints\/([0-9a-f-]{36})$/.exec(url.pathname);
    if (request.method === "GET" && match) {
      try {
        const cursor = Number(url.searchParams.get("cursor") ?? "-1");
        if (!Number.isInteger(cursor) || cursor < -1) throw new Error("cursor is invalid");
        const bucket = process.env.AGENT_CHECKPOINT_BUCKET;
        if (!bucket) throw new Error("external checkpoint setting is required");
        const checkpoint = object(await new GcsCheckpointStore(bucket).get(match[1]));
        const events = Array.isArray(checkpoint.events) ? checkpoint.events.filter((event) => object(event).seq as number > cursor) : [];
        send(response, 200, { checkpointId: match[1], cursor: events.length ? object(events.at(-1)!).seq : cursor, events });
      } catch (error) {
        send(response, 400, { error: error instanceof Error ? error.message : "checkpoint_failed" });
      }
      return;
    }
    send(response, 404, { error: "not_found" });
  });
}

if (process.env.NODE_ENV !== "test") {
  const port = Number(process.env.PORT || "8080");
  const mcp = new McpHost();
  const server = makeServer(mcp).listen(port, "0.0.0.0", () => console.log(`agent gateway listening on ${port}`));
  process.once("SIGTERM", () => server.close(() => void mcp.closeAll()));
}
