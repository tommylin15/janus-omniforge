import { mkdtemp, rm } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join, resolve } from "node:path";
import { afterEach, describe, expect, it, vi } from "vitest";
import { AppServerClient, GcsCheckpointStore, ManagedAuthStore } from "../services/agent-gateway/server.js";

const homes: string[] = [];
afterEach(async () => Promise.all(homes.splice(0).map((path) => rm(path, { recursive: true, force: true }))));

function response(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), { status, headers: { "content-type": "application/json" } });
}

describe("agent gateway cloud runtime POC", () => {
  it("loads and persists rotated managed auth without logging credentials", async () => {
    const home = await mkdtemp(join(tmpdir(), "janus-auth-test-"));
    homes.push(home);
    const first = Buffer.from('{"tokens":"old"}').toString("base64");
    const fetcher = vi.fn()
      .mockResolvedValueOnce(response({ access_token: "metadata-token" }))
      .mockResolvedValueOnce(response({ payload: { data: first } }))
      .mockResolvedValueOnce(response({ access_token: "metadata-token" }))
      .mockResolvedValueOnce(response({ name: "projects/p/secrets/codex-auth/versions/2" }));
    const auth = new ManagedAuthStore("projects/p/secrets/codex-auth", fetcher as typeof fetch);
    await auth.load(home);
    await import("node:fs/promises").then(({ writeFile }) => writeFile(join(home, "auth.json"), '{"tokens":"new"}'));
    expect(await auth.persist(home)).toBe(true);
    expect(fetcher.mock.calls[3][1].body).not.toContain("new");
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
    const cli = resolve("node_modules/@openai/codex-win32-x64/vendor/x86_64-pc-windows-msvc/bin/codex.exe");
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
