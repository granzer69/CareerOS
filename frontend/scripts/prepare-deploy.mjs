import { spawnSync } from "node:child_process";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const rootDir = path.resolve(__dirname, "..");
const sourceDir = path.join(rootDir, "dist");
const outputDir = path.join(rootDir, "build");
const viteBin = path.join(rootDir, "node_modules", ".bin", "vite");
const backendUrl = process.env.BACKEND_URL?.replace(/\/$/, "") || "";

if (backendUrl && !/^https:\/\//.test(backendUrl)) {
  throw new Error("BACKEND_URL must use HTTPS for production deployment.");
}

const result = spawnSync(viteBin, ["build"], {
  cwd: rootDir,
  stdio: "inherit",
  env: {
    ...process.env,
    VITE_BACKEND_URL: backendUrl,
  },
});
if (result.status !== 0) {
  process.exit(result.status ?? 1);
}

if (!backendUrl) {
  console.log(`Built ${sourceDir} with relative /api URLs (local unified mode).`);
  process.exit(0);
}

fs.rmSync(outputDir, { recursive: true, force: true });
fs.cpSync(sourceDir, outputDir, { recursive: true });
console.log(`Prepared ${outputDir}`);
console.log(`Backend API: ${backendUrl}`);
