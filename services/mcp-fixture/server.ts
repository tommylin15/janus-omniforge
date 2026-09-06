import { createServer, type IncomingMessage, type ServerResponse } from "node:http";
import { McpServer, createMcpHandler } from "@modelcontextprotocol/server";
import { serveStdio } from "@modelcontextprotocol/server/stdio";
import { SSEServerTransport } from "@modelcontextprotocol/server-legacy/sse";
import { z } from "zod";

const port = Number(process.env.PORT || 8080);
const sessions = new Map<string, { server: McpServer; transport: SSEServerTransport }>();

function makeServer(): McpServer {
  const server = new McpServer({ name: "janus-mcp-fixture", version: "0.1.0" });
  server.registerTool("echo", {
    description: "Returns the supplied text.",
    inputSchema: { text: z.string().max(256) },
  }, async ({ text }) => ({ content: [{ type: "text", text }] }));
  server.registerTool("secret_echo", {
    description: "Returns a deliberately fake secret for redaction testing.",
    inputSchema: { label: z.string().max(64).optional() },
  }, async ({ label }) => ({
    content: [{ type: "text", text: "secret_echo completed" }],
    structuredContent: { label: label ?? "fixture", secret: "fixture-secret" },
  }));
  server.registerTool("slow", {
    description: "Waits for a bounded duration.",
    inputSchema: { milliseconds: z.number().int().min(0).max(5_000) },
  }, async ({ milliseconds }) => {
    await new Promise((resolve) => setTimeout(resolve, milliseconds));
    return { content: [{ type: "text", text: `waited:${milliseconds}` }] };
  });
  const timer = setTimeout(() => {
    server.registerTool("dynamic", {
      description: "Appears after the fixture announces a tool-list change.",
      inputSchema: { value: z.string().max(64) },
    }, async ({ value }) => ({ content: [{ type: "text", text: `dynamic:${value}` }] }));
    server.sendToolListChanged();
  }, 2_000);
  timer.unref();
  return server;
}

async function body(request: IncomingMessage): Promise<string> {
  const chunks: Buffer[] = [];
  for await (const chunk of request) chunks.push(Buffer.from(chunk));
  return Buffer.concat(chunks).toString("utf8");
}

async function modern(request: IncomingMessage, response: ServerResponse): Promise<void> {
  const raw = await body(request);
  const webRequest = new Request(`http://${request.headers.host ?? "localhost"}${request.url ?? "/mcp"}`, {
    method: request.method,
    headers: Object.fromEntries(Object.entries(request.headers).flatMap(([key, value]) =>
      value === undefined ? [] : [[key, Array.isArray(value) ? value.join(",") : value]])),
    body: raw || undefined,
  });
  const result = await createMcpHandler(() => makeServer()).fetch(webRequest);
  response.writeHead(result.status, Object.fromEntries(result.headers.entries()));
  response.end(Buffer.from(await result.arrayBuffer()));
}

async function legacySse(request: IncomingMessage, response: ServerResponse): Promise<void> {
  const server = makeServer();
  const transport = new SSEServerTransport("/message", response);
  transport.onclose = () => sessions.delete(transport.sessionId);
  sessions.set(transport.sessionId, { server, transport });
  await server.connect(transport);
}

async function legacyMessage(request: IncomingMessage, response: ServerResponse): Promise<void> {
  const sessionId = new URL(request.url ?? "/message", "http://localhost").searchParams.get("sessionId");
  const session = sessionId ? sessions.get(sessionId) : undefined;
  if (!session) { response.writeHead(404); response.end(); return; }
  await session.transport.handlePostMessage(request, response, JSON.parse(await body(request)));
}

if (process.argv.includes("--stdio")) {
  serveStdio(() => makeServer());
} else {
  createServer(async (request, response) => {
    try {
      if (request.url?.startsWith("/mcp")) await modern(request, response);
      else if (request.method === "GET" && request.url?.startsWith("/sse")) await legacySse(request, response);
      else if (request.method === "POST" && request.url?.startsWith("/message")) await legacyMessage(request, response);
      else { response.writeHead(404); response.end(); }
    } catch (error) {
      if (!response.headersSent) response.writeHead(500, { "content-type": "application/json" });
      response.end(JSON.stringify({ error: error instanceof Error ? error.message : "fixture_error" }));
    }
  }).listen(port, "0.0.0.0");
}
