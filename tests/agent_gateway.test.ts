import { mkdtemp, rm } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join, resolve } from "node:path";
import { afterEach, describe, expect, it, vi } from "vitest";
import { AppServerClient, GcsCheckpointStore, ManagedAuthStore, OwnerAuthRegistry, OwnerSessionRegistry, type Json, type RpcMessage } from "../services/agent-gateway/server.js";
import { CodexBridge } from "../services/agent-gateway/codex_bridge.js";
import { McpHost } from "../services/agent-gateway/mcp_host.js";

const homes: string[] = [];
afterEach(async () => Promise.all(homes.splice(0).map((path) => rm(path, { recursive: true, force: true }))));

function response(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), { status, headers: { "content-type": "application/json" } });
}

describe("agent gateway cloud runtime POC", () => {
  it("maps Codex threads, items, approvals, cancellation, and MCP tools", async () => {
    let handler: (message: RpcMessage) => Promise<Json | undefined> | Json | undefined = () => undefined;
    const responses: Array<[number, unknown]> = [];
    const client = {
      initialize: vi.fn().mockResolvedValue({ userAgent: "codex" }),
      request: vi.fn(async (method: string) => method === "account/read" ? { account: { type: "chatgpt" } }
        : method === "thread/start" ? { thread: { id: "thread-1" } }
        : method === "turn/start" ? { turn: { id: "turn-1" } }
        : {}),
      onMessage: vi.fn((value: typeof handler) => { handler = value; }),
      respond: vi.fn((id: number, result: Json) => responses.push([id, result])),
    };
    const mcp = new McpHost();
    vi.spyOn(mcp, "discover").mockResolvedValue({ tools: [{ name: "quotes__latest", description: "Latest quote", inputSchema: { type: "object" } }] });
    vi.spyOn(mcp, "call").mockResolvedValue({ requestId: "request-1", toolName: "quotes__latest", result: { price: 100 } });
    const bridge = new CodexBridge("00000000-0000-4000-8000-000000000001", "/tmp/janus-turn", client, mcp);

    await bridge.initialize();
    await bridge.logout();
    await bridge.startDeviceLogin();
    await bridge.startThread("gpt-5.6-sol", [{ serverId: "quotes", configRef: "approved", toolGrants: ["quotes__latest"] }]);
    await bridge.startTurn("thread-1", "Get the latest quote.", { interruptOnStart: true });
    await handler({ method: "turn/started", params: { threadId: "thread-1", turn: { id: "turn-1", status: "inProgress" } } });
    await handler({ method: "item/started", params: { threadId: "thread-1", turnId: "turn-1", item: { id: "item-1", type: "agentMessage" } } });
    const toolResult = await handler({ id: 80, method: "item/tool/call", params: { threadId: "thread-1", turnId: "turn-1", itemId: "item-2", tool: "quotes__latest", arguments: {} } });
    await handler({ id: 81, method: "item/commandExecution/requestApproval", params: { threadId: "thread-1", turnId: "turn-1", itemId: "item-3", cwd: "/tmp/janus-turn", command: "pwd" } });
    const approval = bridge.eventsAfter().events.find((event) => event.type === "approval_request")!;
    expect(() => bridge.resolveApproval(String(approval.payload.requestId), "thread-1", "turn-other", String(approval.payload.paramsDigest), "accept")).toThrow("binding");
    bridge.resolveApproval(String(approval.payload.requestId), "thread-1", "turn-1", String(approval.payload.paramsDigest), "accept");
    await handler({ method: "turn/completed", params: { threadId: "thread-1", turn: { id: "turn-1", status: "interrupted" } } });

    expect(client.initialize).toHaveBeenCalledWith(true);
    expect(client.request).toHaveBeenCalledWith("account/login/start", { type: "chatgptDeviceCode" }, 30_000);
    expect(client.request).toHaveBeenCalledWith("account/logout", {}, 30_000);
    expect(client.request).toHaveBeenCalledWith("turn/interrupt", { threadId: "thread-1", turnId: "turn-1" }, 30_000);
    expect(client.request).toHaveBeenCalledWith("thread/start", expect.objectContaining({ dynamicTools: [expect.objectContaining({ name: "quotes__latest" })] }), 30_000);
    expect(mcp.call).toHaveBeenCalledWith(expect.objectContaining({ ownerId: "00000000-0000-4000-8000-000000000001", toolName: "quotes__latest" }));
    expect(toolResult).toEqual(expect.objectContaining({ success: true }));
    expect(responses).toEqual([[81, { decision: "accept" }]]);
    expect(bridge.eventsAfter().events.map((event) => event.type)).toEqual([
      "item_upsert", "tool_request", "tool_result", "approval_request", "approval_resolved", "turn_cancelled",
    ]);
  });

  it("accepts only server-side MCP configs and HTTPS remote endpoints", () => {
    expect(McpHost.configs(JSON.stringify({ approved: { transport: "stdio", command: "/app/bin/mcp" } })).size).toBe(1);
    expect(() => McpHost.configs(JSON.stringify({ bad: { transport: "streamable-http", url: "http://attacker.example/mcp" } }))).toThrow("HTTPS");
    expect(() => McpHost.configs(JSON.stringify({ bad: { transport: "shell", command: "sh -c" } }))).toThrow("transport");
  });

  it("loads and persists rotated managed auth without logging credentials", async () => {
    const home = await mkdtemp(join(tmpdir(), "janus-auth-test-"));
    homes.push(home);
    const first = Buffer.from('{"tokens":"old"}').toString("base64");
    const fetcher = vi.fn()
      .mockResolvedValueOnce(response({ access_token: "metadata-token" }))
      .mockResolvedValueOnce(response({ name: "projects/p/secrets/codex-auth/versions/1", payload: { data: first } }))
      .mockResolvedValueOnce(response({ access_token: "metadata-token" }))
      .mockResolvedValueOnce(response({ name: "projects/p/secrets/codex-auth/versions/2" }))
      .mockResolvedValueOnce(response({ access_token: "metadata-token" }))
      .mockResolvedValueOnce(response({ payload: { data: Buffer.from('{"tokens":"new"}').toString("base64") } }))
      .mockResolvedValueOnce(response({ access_token: "metadata-token" }))
      .mockResolvedValueOnce(response({ versions: [
        { name: "projects/p/secrets/codex-auth/versions/1", state: "ENABLED" },
        { name: "projects/p/secrets/codex-auth/versions/2", state: "ENABLED" },
      ] }))
      .mockResolvedValueOnce(response({ access_token: "metadata-token" }))
      .mockResolvedValueOnce(response({ name: "projects/p/secrets/codex-auth/versions/1", state: "DESTROYED" }));
    const auth = new ManagedAuthStore("projects/p/secrets/codex-auth", fetcher as typeof fetch);
    await auth.load(home);
    await import("node:fs/promises").then(({ writeFile }) => writeFile(join(home, "auth.json"), '{"tokens":"new"}'));
    expect(await auth.persist(home)).toBe(true);
    expect(fetcher.mock.calls[3][1].body).not.toContain("new");
    expect(fetcher.mock.calls.some(([url]) => String(url).endsWith("/versions/1:destroy"))).toBe(true);
  });

  it("maps allowlisted owners without accepting a credential locator from requests", () => {
    const registry = OwnerAuthRegistry.parse(JSON.stringify({
      "00000000-0000-4000-8000-000000000001": "projects/p/secrets/codex-auth-a",
      "00000000-0000-4000-8000-000000000002": "projects/p/secrets/codex-auth-b",
    }));
    expect(registry.resource("00000000-0000-4000-8000-000000000002")).toBe("projects/p/secrets/codex-auth-b");
    expect(() => registry.resource("00000000-0000-4000-8000-000000000003")).toThrow("allowlisted");
  });

  it("treats an already absent owner auth secret as destroyed", async () => {
    const fetcher = vi.fn()
      .mockResolvedValueOnce(response({ access_token: "metadata-token" }))
      .mockResolvedValueOnce(response({}, 404));
    await expect(new ManagedAuthStore("projects/p/secrets/codex-auth", fetcher as typeof fetch).destroy()).resolves.toBeUndefined();
  });

  it("evicts an owner login session before cleanup", async () => {
    const root = await mkdtemp(join(tmpdir(), "janus-login-test-"));
    homes.push(root);
    const ownerId = "00000000-0000-4000-8000-000000000001";
    const client = { request: vi.fn().mockResolvedValue({}), stop: vi.fn().mockResolvedValue(undefined) };
    const timer = setTimeout(() => undefined, 60_000);
    timer.unref();
    const registry = new OwnerSessionRegistry() as OwnerSessionRegistry & { sessions: Map<string, unknown> };
    registry.sessions.set(ownerId, { ownerId, root, home: root, auth: {}, client, timer });
    await expect(registry.evict(ownerId, true)).resolves.toBe(true);
    expect(client.request).toHaveBeenCalledWith("account/logout", {}, 30_000);
    expect(client.stop).toHaveBeenCalled();
    await expect(registry.evict(ownerId, true)).resolves.toBe(false);
  });

  it("round-trips an external checkpoint for cursor reconnect", async () => {
    const fetcher = vi.fn()
      .mockResolvedValueOnce(response({ access_token: "metadata-token" }))
      .mockResolvedValueOnce(response({ name: "object" }))
      .mockResolvedValueOnce(response({ access_token: "metadata-token" }))
      .mockResolvedValueOnce(response({ checkpointId: "id", events: [{ seq: 0 }] }));
    const store = new GcsCheckpointStore("janus-dev-private", fetcher as typeof fetch);
    await store.put("id", { checkpointId: "id", events: [{ seq: 0 }] });
    expect(await store.get("id")).toEqual({ checkpointId: "id", events: [{ seq: 0 }] });
  });

  it("negotiates JSONL with the pinned Codex App Server", async () => {
    const home = await mkdtemp(join(tmpdir(), "janus-codex-test-"));
    homes.push(home);
    const cli = resolve(process.platform === "win32"
      ? "node_modules/@openai/codex-win32-x64/vendor/x86_64-pc-windows-msvc/bin/codex.exe"
      : "node_modules/@openai/codex-linux-x64/vendor/x86_64-unknown-linux-musl/bin/codex");
    const client = new AppServerClient(cli, [], home);
    client.start();
    try {
      const initialized = await client.initialize();
      expect(initialized).toBeTruthy();
      expect(await client.request("account/read", { refreshToken: false })).toHaveProperty("account");
    } finally {
      await client.stop();
    }
  }, 20_000);
});
