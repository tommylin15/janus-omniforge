import { spawn, type ChildProcessWithoutNullStreams } from "node:child_process";
import { createHash, createHmac, randomUUID, timingSafeEqual } from "node:crypto";
import { chmod, mkdir, mkdtemp, readFile, rm, writeFile } from "node:fs/promises";
import { createServer, type IncomingMessage, type ServerResponse } from "node:http";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { createInterface } from "node:readline";
import { CodexBridge, type AgentEvent } from "./codex_bridge.js";
import { McpHost } from "./mcp_host.js";

export type Json = null | boolean | number | string | Json[] | { [key: string]: Json };
export type RpcMessage = { id?: number; method?: string; params?: Json; result?: Json; error?: { code?: number; message?: string } };
type Pending = { resolve: (value: Json) => void; reject: (error: Error) => void; timer: NodeJS.Timeout };
type RpcHandler = (message: RpcMessage) => Promise<Json | undefined> | Json | undefined;

const CODEX_VERSION = "0.153.0";
const JSON_HEADERS = { "content-type": "application/json" };

export class AppServerClient {
  private child?: ChildProcessWithoutNullStreams;
  private nextId = 1;
  private pending = new Map<number, Pending>();
  private handler?: RpcHandler;

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

export function makeServer(mcp = new McpHost()) {
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
        await logoutOwner(ownerId, resource);
        send(response, 200, { ownerId, loggedOut: true, sessionEvicted: true });
      } catch (error) {
        const status = (error as Error & { status?: number }).status === 404 ? 200 : 400;
        send(response, status, status === 200 ? { loggedOut: true, sessionEvicted: true } : { error: error instanceof Error ? error.message : "logout_failed" });
      } finally {
        running = false;
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
