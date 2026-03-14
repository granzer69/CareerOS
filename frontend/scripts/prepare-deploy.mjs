import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const rootDir = path.resolve(__dirname, "..");
const sourceDir = path.join(rootDir, "dist");
const outputDir = path.join(rootDir, "build");
const backendUrl = process.env.BACKEND_URL?.replace(/\/$/, "");

if (!backendUrl) {
  throw new Error(
    "BACKEND_URL is required. Set it to the public Render service URL."
  );
}

if (!/^https:\/\//.test(backendUrl)) {
  throw new Error("BACKEND_URL must use HTTPS for production deployment.");
}

fs.rmSync(outputDir, { recursive: true, force: true });
fs.cpSync(sourceDir, outputDir, { recursive: true });

const assetsDir = path.join(outputDir, "assets");
const javascriptFiles = fs
  .readdirSync(assetsDir)
  .filter((fileName) => fileName.endsWith(".js"));

let replacements = 0;
for (const fileName of javascriptFiles) {
  const filePath = path.join(assetsDir, fileName);
  const source = fs.readFileSync(filePath, "utf8");
  const target = 'fetch("/api/v1/resume/analyze"';
  const replacement = `fetch("${backendUrl}/api/v1/resume/analyze"`;
  const updated = source.replace(target, replacement);
  if (updated !== source) {
    fs.writeFileSync(filePath, updated);
    replacements += 1;
  }
}

if (replacements !== 1) {
  throw new Error(
    `Expected to inject one backend API URL, but updated ${replacements} bundles.`
  );
}

console.log(`Prepared ${outputDir}`);
console.log(`Backend API: ${backendUrl}`);
