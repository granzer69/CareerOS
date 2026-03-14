import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const rootDir = path.resolve(__dirname, "..");
const outputDir = path.join(rootDir, "build");
const indexPath = path.join(outputDir, "index.html");
const assetsDir = path.join(outputDir, "assets");

if (!fs.existsSync(indexPath) || !fs.existsSync(assetsDir)) {
  throw new Error("Frontend build output is incomplete.");
}

const javascript = fs
  .readdirSync(assetsDir)
  .filter((fileName) => fileName.endsWith(".js"))
  .map((fileName) => fs.readFileSync(path.join(assetsDir, fileName), "utf8"))
  .join("\n");

if (javascript.includes('fetch("/api/v1/resume/analyze"')) {
  throw new Error("Frontend still contains an unresolved relative API URL.");
}

if (!javascript.includes("https://")) {
  throw new Error("Frontend does not contain an injected HTTPS backend URL.");
}

console.log("Frontend deployment build verified.");
