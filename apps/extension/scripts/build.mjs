import { cp, mkdir, readFile, rm, writeFile } from "node:fs/promises";
import { createHash } from "node:crypto";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";

const ROOT = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const PUBLIC_DEV_KEY =
  "MIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEAw4uyin7DQyM8sN4svExqHd4Byxp7WPw90cSykteG5wUiKlOx1vgnAIv04V2ASjCfmn/497vb8NWaVaAB4m8mc6aDWtGSxiIYcG5OEJ6JOKh+PX8MfUPQoFZKWjvFzTjS00kk0znky1TjMG9TPc3bbeNaZNjidjpCR2J18Qvk9KPYsbl8u/h4q1IjqwLSAAvDkdxthfihOJsb0h1a9xfuHnk8l2WLwxUA8Y6i4uhV4wEOSKDhiLz5FEa34lVaKGsM3Uv/GPtXNzF7syx+SOY/Cv+pA2KS7zTHFlIvh4gEvQXc4LO9ChKWL+CI3nE74xOgZgy1bxiKzkXj7MKbfjx9KQIDAQAB";

export function parseArgs(argv) {
  const args = new Map();
  for (let i = 0; i < argv.length; i += 1) {
    const token = argv[i];
    if (token === "--dev" || token === "--production") args.set(token.slice(2), true);
    else if (token.startsWith("--") && argv[i + 1] && !argv[i + 1].startsWith("--")) {
      args.set(token.slice(2), argv[i + 1]);
      i += 1;
    } else throw new Error(`Unknown or incomplete argument: ${token}`);
  }
  if (args.has("dev") === args.has("production")) {
    throw new Error("Choose exactly one build mode: --dev or --production");
  }
  return args;
}

export function exactApiOrigin(value, { development = false } = {}) {
  const url = new URL(value);
  if (url.username || url.password || url.search || url.hash || url.pathname !== "/") {
    throw new Error("API endpoint must be an origin without credentials, path, query, or fragment");
  }
  if (development) {
    if (url.protocol !== "http:" || !["127.0.0.1", "localhost", "[::1]"].includes(url.hostname)) {
      throw new Error("Development API origin must use HTTP on loopback");
    }
  } else if (url.protocol !== "https:") {
    throw new Error("Production API origin must use HTTPS");
  }
  return url.origin;
}

export function extensionId(publicKey) {
  const digest = createHash("sha256").update(Buffer.from(publicKey, "base64")).digest();
  return [...digest.subarray(0, 16)].map((byte) =>
    [...(byte.toString(16).padStart(2, "0"))].map((digit) => String.fromCharCode(97 + Number.parseInt(digit, 16))).join(""),
  ).join("");
}

export function createManifest({ apiOrigin, production = false }) {
  return {
    manifest_version: 3,
    name: "Rolevo",
    version: "0.1.0",
    description: "Review and prepare answers for the form you choose.",
    key: PUBLIC_DEV_KEY,
    permissions: ["activeTab", "scripting", "storage", "identity", "sidePanel"],
    host_permissions: [`${apiOrigin}/*`],
    background: { service_worker: "worker.js", type: "module" },
    action: { default_title: "Open Rolevo" },
    side_panel: { default_path: "panel.html" },
    content_security_policy: {
      extension_pages: "script-src 'self'; object-src 'self'; base-uri 'self';",
    },
    ...(production ? {} : { version_name: "0.1.0-dev" }),
  };
}

async function build() {
  const args = parseArgs(process.argv.slice(2));
  const production = args.has("production");
  const origin = exactApiOrigin(
    production ? args.get("api-origin") ?? "" : "http://127.0.0.1:18000",
    { development: !production },
  );
  if (production && !args.get("manifest-key")) {
    throw new Error("Production build requires --manifest-key from the release public key");
  }
  const destination = join(ROOT, "dist", production ? "production" : "development");
  await rm(destination, { recursive: true, force: true });
  await mkdir(destination, { recursive: true });
  for (const file of [
    "worker.js",
    "content.js",
    "extraction.js",
    "filling.js",
    "observation.js",
    "panel.html",
    "panel.css",
    "panel.js",
    "demo.html",
    "demo.js",
  ]) {
    await cp(join(ROOT, "src", file), join(destination, file));
  }
  const manifest = createManifest({ apiOrigin: origin, production });
  if (production) manifest.key = args.get("manifest-key");
  await writeFile(join(destination, "manifest.json"), `${JSON.stringify(manifest, null, 2)}\n`);
  console.log(`Built ${production ? "production" : "development"} extension at ${destination}`);
  if (!production) console.log(`Stable development extension ID: ${extensionId(PUBLIC_DEV_KEY)}`);
}

if (process.argv[1] && import.meta.url === pathToFileURL(resolve(process.argv[1])).href) {
  build().catch((error) => {
    console.error(error.message);
    process.exitCode = 1;
  });
}
