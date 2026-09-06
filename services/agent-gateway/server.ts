import { spawn, type ChildProcessWithoutNullStreams } from "node:child_process";
import { createHash, randomUUID } from "node:crypto";
import { chmod, mkdir, mkdtemp, readFile, rm, writeFile } from "node:fs/promises";
import { createServer, type IncomingMessage, type ServerResponse } from "node:http";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { createInterface } from "node:readline";

type Json = null | boolean | number | string | Json[] | { [key: string]: Json };
type RpcResponse = { id: number; result?: Json; error?: { message?: string } };
type Pending = { resolve: (value: Json) => void; reject: (error: Error) => void; timer: NodeJS.Timeout };

const CODEX_VERSION = "0.153.0";
const JSON_HEADERS = { "content-type": "application/json" };

export class AppServerClient {
  private child?: ChildProcessWithoutNullStreams;
  private nextId = 1;
  private pending = new Map<number, Pending>();

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
    this.child.once("error", (error) => this.fail(error));
    this.child.once("exit", (code) => this.fail(new Error(`Codex App Server exited (${code ?? "signal"})`)));
  }

  async initialize(): Promise<Json> {
    const result = await this.request("initialize", {
      clientInfo: { name: "janus-agent-gateway", version: "0.1.0" },
      capabilities: { experimentalApi: false },
    });
    this.notify("initialized", {});
    return result;
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
    let message: RpcResponse & { method?: string };
    try {
      message = JSON.parse(line) as RpcResponse & { method?: string };
    } catch {
      this.fail(new Error("Codex App Server emitted invalid JSONL"));
      return;
    }
    if (typeof message.id === "number" && message.method) {
      this.child?.stdin.write(`${JSON.stringify({ jsonrpc: "2.0", id: message.id, error: { code: -32601, message: "POC client does not handle server requests" } })}\n`);
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
  if (!response.ok) throw new Error(`Google API request failed (${response.status})`);
  return response.json() as Promise<Json>;
}

export class ManagedAuthStore {
  private digest?: string;

  constructor(private resource: string, private fetcher: typeof fetch = fetch) {
    if (!/^projects\/[^/]+\/secrets\/[^/]+$/.test(resource)) throw new Error("CODEX_AUTH_SECRET is invalid");
  }

  async load(home: string): Promise<void> {
    const body = await googleJson(this.fetcher, `https://secretmanager.googleapis.com/v1/${this.resource}/versions/latest:access`) as { payload?: { data?: string } };
    if (!body.payload?.data) throw new Error("Codex managed auth secret is empty");
    const raw = Buffer.from(body.payload.data, "base64");
    JSON.parse(raw.toString("utf8"));
    await mkdir(home, { recursive: true, mode: 0o700 });
    await writeFile(join(home, "auth.json"), raw, { mode: 0o600 });
    await chmod(join(home, "auth.json"), 0o600);
    this.digest = createHash("sha256").update(raw).digest("hex");
  }

  async persist(home: string): Promise<boolean> {
    const raw = await readFile(join(home, "auth.json"));
    const digest = createHash("sha256").update(raw).digest("hex");
    if (digest === this.digest) return false;
    await googleJson(this.fetcher, `https://secretmanager.googleapis.com/v1/${this.resource}:addVersion`, {
      method: "POST",
      body: JSON.stringify({ payload: { data: raw.toString("base64") } }),
    });
    this.digest = digest;
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

type PocEvent = { eventId: string; seq: number; threadId: string; turnId: string; type: "turn_cancelled"; payload: { probe: "interrupted" } };
type Checkpoint = { checkpointId: string; events: PocEvent[] };

function object(value: Json): { [key: string]: Json } {
  if (!value || Array.isArray(value) || typeof value !== "object") throw new Error("Codex App Server returned an invalid object");
  return value;
}

export async function runPoc(): Promise<Json> {
  const authSecret = process.env.CODEX_AUTH_SECRET;
  const bucket = process.env.AGENT_CHECKPOINT_BUCKET;
  if (!authSecret || !bucket) throw new Error("managed auth and external checkpoint settings are required");

  const root = await mkdtemp(join(process.env.SANDBOX_ROOT || tmpdir(), "turn-"));
  const home = join(root, "codex-home");
  const workspace = join(root, "workspace");
  const auth = new ManagedAuthStore(authSecret);
  const checkpoints = new GcsCheckpointStore(bucket);
  const client = new AppServerClient(process.env.CODEX_BIN || "codex", [], home);
  try {
    await mkdir(workspace, { mode: 0o700 });
    await auth.load(home);
    client.start();
    await client.initialize();
    const account = object(await client.request("account/read", { refreshToken: true }, 30_000));
    if (!account.account) throw new Error("Codex managed auth is unavailable");
    const thread = object(await client.request("thread/start", {
      cwd: workspace,
      sandbox: "workspace-write",
      approvalPolicy: "untrusted",
      ephemeral: true,
    }, 30_000));
    const nativeThread = object(thread.thread ?? null);
    if (typeof nativeThread.id !== "string") throw new Error("Codex thread/start did not return a thread id");
    const started = object(await client.request("turn/start", {
      threadId: nativeThread.id,
      input: [{ type: "text", text: "Reply with the single word OK." }],
    }, 30_000));
    const nativeTurn = object(started.turn ?? null);
    if (typeof nativeTurn.id !== "string") throw new Error("Codex turn/start did not return a turn id");
    await client.request("turn/interrupt", { threadId: nativeThread.id, turnId: nativeTurn.id }, 30_000);
    const checkpointId = randomUUID();
    const checkpoint: Checkpoint = {
      checkpointId,
      events: [{ eventId: randomUUID(), seq: 0, threadId: nativeThread.id, turnId: nativeTurn.id, type: "turn_cancelled", payload: { probe: "interrupted" } }],
    };
    const authRotated = await auth.persist(home);
    await checkpoints.put(checkpointId, checkpoint as unknown as Json);
    return { codexVersion: CODEX_VERSION, checkpointId, cursor: 0, authRotated, sandbox: "workspace-write", cancelled: true, process: "stopped-after-response" };
  } finally {
    await client.stop();
    await rm(root, { recursive: true, force: true });
  }
}

function send(response: ServerResponse, status: number, body: Json): void {
  response.writeHead(status, JSON_HEADERS);
  response.end(JSON.stringify(body));
}

export function makeServer() {
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
        send(response, 200, await runPoc());
      } catch (error) {
        send(response, 503, { error: error instanceof Error ? error.message : "probe_failed" });
      } finally {
        running = false;
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
  makeServer().listen(port, "0.0.0.0", () => console.log(`agent gateway listening on ${port}`));
}
