import {
  Client,
  SSEClientTransport,
  StreamableHTTPClientTransport,
  fromJsonSchema,
  type Tool,
  type JsonSchemaType,
  type Transport,
} from "@modelcontextprotocol/client";
import { StdioClientTransport, getDefaultEnvironment } from "@modelcontextprotocol/client/stdio";
import { mkdir, mkdtemp, rm } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";

type Json = null | boolean | number | string | Json[] | { [key: string]: Json };
type TransportName = "stdio" | "streamable-http" | "sse";
type ServerConfig = {
  transport: TransportName;
  command?: string;
  args?: string[];
  env?: Record<string, string>;
  url?: string;
  audience?: string;
  authTokenEnv?: string;
  timeoutMs?: number;
};
type Session = {
  client: Client;
  configRef: string;
  ownerId: string;
  serverId: string;
  tools: Map<string, Tool>;
  lastUsed: number;
  root?: string;
};

const MAX_SESSIONS = 16;
const MAX_TOOLS = 128;
const MAX_OUTPUT_BYTES = 65_536;
const ID = /^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$/;
const ENV = /^[A-Z_][A-Z0-9_]{0,127}$/;

function record(value: unknown, message: string): Record<string, unknown> {
  if (!value || Array.isArray(value) || typeof value !== "object") throw new Error(message);
  return value as Record<string, unknown>;
}

function text(value: unknown, name: string, pattern = ID): string {
  if (typeof value !== "string" || !pattern.test(value)) throw new Error(`${name} is invalid`);
  return value;
}

function stringArray(value: unknown, name: string, limit: number): string[] {
  if (!Array.isArray(value) || value.length > limit || value.some((item) => typeof item !== "string")) {
    throw new Error(`${name} is invalid`);
  }
  return [...new Set(value as string[])];
}

function namespace(serverId: string, toolName: string): string {
  return `${serverId}__${toolName}`;
}

function parseConfigs(raw: string): Map<string, ServerConfig> {
  const source = record(JSON.parse(raw), "MCP_SERVER_CONFIGS must be an object");
  const result = new Map<string, ServerConfig>();
  for (const [configRef, rawConfig] of Object.entries(source)) {
    text(configRef, "config reference");
    const value = record(rawConfig, `MCP config ${configRef} is invalid`);
    const transport = value.transport;
    if (!(["stdio", "streamable-http", "sse"] as unknown[]).includes(transport)) {
      throw new Error(`MCP config ${configRef} transport is invalid`);
    }
    const timeoutMs = value.timeoutMs === undefined ? 30_000 : Number(value.timeoutMs);
    if (!Number.isInteger(timeoutMs) || timeoutMs < 100 || timeoutMs > 60_000) {
      throw new Error(`MCP config ${configRef} timeout is invalid`);
    }
    const config: ServerConfig = { transport: transport as TransportName, timeoutMs };
    if (transport === "stdio") {
      config.command = text(value.command, `MCP config ${configRef} command`, /^[/A-Za-z0-9_.-]{1,512}$/);
      config.args = stringArray(value.args ?? [], `MCP config ${configRef} args`, 32);
      const env = value.env === undefined ? {} : record(value.env, `MCP config ${configRef} env is invalid`);
      config.env = {};
      for (const [target, sourceName] of Object.entries(env)) {
        text(target, "stdio environment name", ENV);
        config.env[target] = text(sourceName, "stdio environment reference", ENV);
      }
    } else {
      const url = new URL(String(value.url));
      if (url.protocol !== "https:") throw new Error(`MCP config ${configRef} URL must use HTTPS`);
      config.url = url.toString();
      if (value.audience !== undefined) config.audience = new URL(String(value.audience)).toString();
      if (value.authTokenEnv !== undefined) config.authTokenEnv = text(value.authTokenEnv, "auth token reference", ENV);
      if (config.audience && config.authTokenEnv) throw new Error(`MCP config ${configRef} has multiple auth methods`);
    }
    result.set(configRef, config);
  }
  return result;
}

async function googleIdentityToken(audience: string, fetcher: typeof fetch): Promise<string> {
  const url = "http://metadata.google.internal/computeMetadata/v1/instance/service-accounts/default/identity";
  const response = await fetcher(`${url}?audience=${encodeURIComponent(audience)}&format=full`, {
    headers: { "Metadata-Flavor": "Google" },
  });
  if (!response.ok) throw new Error(`MCP service identity token unavailable (${response.status})`);
  const token = await response.text();
  if (!token) throw new Error("MCP service identity token is empty");
  return token;
}

function redact(value: unknown, secrets: string[]): Json {
  if (Array.isArray(value)) return value.map((item) => redact(item, secrets));
  if (value && typeof value === "object") {
    return Object.fromEntries(Object.entries(value).map(([key, item]) => [key,
      /secret|token|password|credential|authorization/i.test(key) ? "[redacted]" : redact(item, secrets)]));
  }
  if (typeof value === "string") {
    return secrets.reduce((safe, secret) => secret ? safe.replaceAll(secret, "[redacted]") : safe, value);
  }
  if (value === null || typeof value === "boolean" || typeof value === "number") return value;
  return String(value);
}

export class McpHost {
  private sessions = new Map<string, Session>();
  private activeCalls = new Map<string, AbortController>();

  constructor(
    private configs = parseConfigs(process.env.MCP_SERVER_CONFIGS || "{}"),
    private environment: NodeJS.ProcessEnv = process.env,
    private fetcher: typeof fetch = fetch,
  ) {}

  static configs(raw: string): Map<string, ServerConfig> { return parseConfigs(raw); }

  async discover(input: unknown): Promise<Json> {
    const request = record(input, "MCP discovery request is invalid");
    const ownerId = text(request.ownerId, "owner id", /^[0-9a-f-]{36}$/i);
    const serverId = text(request.serverId, "server id");
    const configRef = text(request.configRef, "config reference");
    const grants = stringArray(request.toolGrants ?? [], "tool grants", MAX_TOOLS);
    const session = await this.session(ownerId, serverId, configRef);
    const tools = [...session.tools.entries()]
      .filter(([name]) => grants.length === 0 || grants.includes(name))
      .map(([name, tool]) => ({ name, description: tool.description?.slice(0, 2_000), inputSchema: tool.inputSchema }));
    return {
      serverId,
      configRef,
      transport: this.config(configRef).transport,
      protocolEra: session.client.getProtocolEra() ?? null,
      server: (session.client.getServerVersion() ?? null) as unknown as Json,
      capabilities: (session.client.getServerCapabilities() ?? {}) as unknown as Json,
      tools: tools as unknown as Json,
    };
  }

  async call(input: unknown): Promise<Json> {
    const request = record(input, "MCP tool request is invalid");
    const ownerId = text(request.ownerId, "owner id", /^[0-9a-f-]{36}$/i);
    const serverId = text(request.serverId, "server id");
    const configRef = text(request.configRef, "config reference");
    const requestId = text(request.requestId, "request id", /^[A-Za-z0-9-]{8,128}$/);
    const toolName = text(request.toolName, "tool name", /^[A-Za-z0-9._:-]{1,192}$/);
    const grants = stringArray(request.toolGrants, "tool grants", MAX_TOOLS);
    if (!toolName.startsWith(`${serverId}__`) || !grants.includes(toolName)) throw new Error("MCP tool is not granted");
    const session = await this.session(ownerId, serverId, configRef);
    const tool = session.tools.get(toolName);
    if (!tool) throw new Error("MCP tool is unavailable");
    const args = request.arguments === undefined ? {} : record(request.arguments, "MCP tool arguments are invalid");
    const validated = await fromJsonSchema(tool.inputSchema as unknown as JsonSchemaType)["~standard"].validate(args);
    if (validated.issues) throw new Error("MCP tool arguments do not match the discovered schema");
    const callKey = `${ownerId}:${requestId}`;
    if (this.activeCalls.has(callKey)) throw new Error("MCP request is already active");
    const controller = new AbortController();
    this.activeCalls.set(callKey, controller);
    try {
      const config = this.config(configRef);
      const result = await session.client.callTool(
        { name: tool.name, arguments: validated.value as Record<string, unknown> },
        { signal: controller.signal, timeout: config.timeoutMs, maxTotalTimeout: config.timeoutMs, toolDefinition: tool },
      );
      const safe = redact(result, this.secrets(config));
      if (Buffer.byteLength(JSON.stringify(safe)) > MAX_OUTPUT_BYTES) throw new Error("MCP tool output exceeds the host limit");
      return { requestId, toolName, result: safe };
    } finally {
      this.activeCalls.delete(callKey);
    }
  }

  cancel(input: unknown): Json {
    const request = record(input, "MCP cancel request is invalid");
    const ownerId = text(request.ownerId, "owner id", /^[0-9a-f-]{36}$/i);
    const requestId = text(request.requestId, "request id", /^[A-Za-z0-9-]{8,128}$/);
    const controller = this.activeCalls.get(`${ownerId}:${requestId}`);
    if (!controller) throw new Error("MCP request is not active");
    controller.abort();
    return { requestId, cancelled: true };
  }

  async disconnect(input: unknown): Promise<Json> {
    const request = record(input, "MCP disconnect request is invalid");
    const ownerId = text(request.ownerId, "owner id", /^[0-9a-f-]{36}$/i);
    const serverId = text(request.serverId, "server id");
    const key = `${ownerId}:${serverId}`;
    const session = this.sessions.get(key);
    if (session) await this.close(key, session);
    return { serverId, disconnected: true };
  }

  async closeAll(): Promise<void> {
    await Promise.all([...this.sessions.entries()].map(([key, session]) => this.close(key, session)));
  }

  private config(configRef: string): ServerConfig {
    const config = this.configs.get(configRef);
    if (!config) throw new Error("MCP config reference is not allowlisted");
    return config;
  }

  private async session(ownerId: string, serverId: string, configRef: string): Promise<Session> {
    const key = `${ownerId}:${serverId}`;
    const current = this.sessions.get(key);
    if (current?.configRef === configRef) { current.lastUsed = Date.now(); return current; }
    if (current) await this.close(key, current);
    while (this.sessions.size >= MAX_SESSIONS) {
      const oldest = [...this.sessions.entries()].sort((left, right) => left[1].lastUsed - right[1].lastUsed)[0];
      await this.close(oldest[0], oldest[1]);
    }
    const config = this.config(configRef);
    const { transport, root } = await this.transport(config);
    let session: Session | undefined;
    const client = new Client({ name: "janus-mcp-host", version: "0.1.0" }, {
      enforceStrictCapabilities: true,
      inputRequired: { autoFulfill: false },
      listMaxPages: 16,
      versionNegotiation: { mode: "auto", probe: { timeoutMs: 5_000, maxRetries: 0 } },
      listChanged: { tools: { debounceMs: 100, onChanged: (error, tools) => {
        if (!error && session) session.tools = this.toolMap(serverId, tools as Tool[]);
      } } },
    });
    try {
      await client.connect(transport, { timeout: config.timeoutMs });
      session = { client, configRef, ownerId, serverId,
        tools: this.toolMap(serverId, (await client.listTools()).tools), lastUsed: Date.now(), root };
      this.sessions.set(key, session);
      return session;
    } catch (error) {
      await client.close().catch(() => undefined);
      if (root) await rm(root, { recursive: true, force: true });
      throw error;
    }
  }

  private toolMap(serverId: string, tools: Tool[]): Map<string, Tool> {
    if (tools.length > MAX_TOOLS) throw new Error("MCP server exposes too many tools");
    const result = new Map<string, Tool>();
    for (const tool of tools) {
      const name = namespace(serverId, tool.name);
      if (result.has(name)) throw new Error("MCP server exposes duplicate tool names");
      result.set(name, tool);
    }
    return result;
  }

  private async transport(config: ServerConfig): Promise<{ transport: Transport; root?: string }> {
    if (config.transport === "stdio") {
      const root = await mkdtemp(join(this.environment.SANDBOX_ROOT || tmpdir(), "mcp-"));
      await mkdir(root, { recursive: true, mode: 0o700 });
      const explicit = Object.fromEntries(Object.entries(config.env ?? {}).map(([target, source]) => {
        const value = this.environment[source];
        if (!value) throw new Error(`MCP credential reference ${source} is unavailable`);
        return [target, value];
      }));
      return { root, transport: new StdioClientTransport({ command: config.command!, args: config.args,
        cwd: root, env: { ...getDefaultEnvironment(), ...explicit }, stderr: "ignore", maxBufferSize: 1_048_576 }) };
    }
    const authProvider = config.audience ? { token: () => googleIdentityToken(config.audience!, this.fetcher) }
      : config.authTokenEnv ? { token: async () => {
        const token = this.environment[config.authTokenEnv!];
        if (!token) throw new Error("MCP bearer credential is unavailable");
        return token;
      } } : undefined;
    const url = new URL(config.url!);
    return { transport: config.transport === "sse"
      ? new SSEClientTransport(url, { authProvider, fetch: this.fetcher })
      : new StreamableHTTPClientTransport(url, { authProvider, fetch: this.fetcher, onInsufficientScope: "throw" }) };
  }

  private secrets(config: ServerConfig): string[] {
    return [...Object.values(config.env ?? {}), config.authTokenEnv]
      .filter((name): name is string => Boolean(name)).map((name) => this.environment[name] || "").filter(Boolean);
  }

  private async close(key: string, session: Session): Promise<void> {
    this.sessions.delete(key);
    await session.client.close().catch(() => undefined);
    if (session.root) await rm(session.root, { recursive: true, force: true });
  }
}
