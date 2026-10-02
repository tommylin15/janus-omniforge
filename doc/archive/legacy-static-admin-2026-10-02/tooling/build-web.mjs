import { cp, mkdir, rm } from "node:fs/promises";

await rm("dist/web", { recursive: true, force: true });
await mkdir("dist/web", { recursive: true });
await cp("apps/web/static", "dist/web", { recursive: true });
console.log("Built static web artifact in dist/web");
