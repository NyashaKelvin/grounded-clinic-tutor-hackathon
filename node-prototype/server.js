// Tiny zero-dependency server: serves /public and exposes POST /api/ask.
// The Gemini key stays on the server and never reaches the browser.
const http = require("http");
const fs = require("fs");
const path = require("path");

// Minimal .env loader (no dotenv dependency)
try {
  for (const line of fs.readFileSync(fs.existsSync(path.join(__dirname, ".env")) ? path.join(__dirname, ".env") : path.join(__dirname, "..", ".env"), "utf8").split(/\r?\n/)) {
    const m = line.match(/^\s*([A-Z0-9_]+)\s*=\s*(.*?)\s*$/i);
    if (m && !line.trim().startsWith("#") && !(m[1] in process.env))
      process.env[m[1]] = m[2].replace(/^["']|["']$/g, "");
  }
} catch {}

const { askTutor, MODEL } = require("./gemini");

const PORT = process.env.PORT || 3000;
const PUBLIC = path.join(__dirname, "public");
const MAX_SOURCE = 30000;
const MAX_QUESTION = 1000;
const TYPES = { ".html": "text/html; charset=utf-8", ".js": "text/javascript", ".css": "text/css", ".txt": "text/plain; charset=utf-8" };

function send(res, code, obj) {
  res.writeHead(code, { "Content-Type": "application/json" });
  res.end(JSON.stringify(obj));
}

const server = http.createServer(async (req, res) => {
  if (req.method === "POST" && req.url === "/api/ask") {
    let raw = "";
    req.on("data", (c) => {
      raw += c;
      if (raw.length > 200000) req.destroy();
    });
    req.on("end", async () => {
      let payload;
      try { payload = JSON.parse(raw); } catch { return send(res, 400, { error: "Invalid JSON." }); }
      const source = String(payload.source || "").trim();
      const question = String(payload.question || "").trim();
      if (!source) return send(res, 400, { error: "Please paste some source material." });
      if (!question) return send(res, 400, { error: "Please type a question." });
      if (source.length > MAX_SOURCE) return send(res, 400, { error: `Source material is too long (max ${MAX_SOURCE} characters).` });
      if (question.length > MAX_QUESTION) return send(res, 400, { error: `Question is too long (max ${MAX_QUESTION} characters).` });
      try {
        send(res, 200, await askTutor({ source, question }));
      } catch (e) {
        console.error("[ask]", e.code || "", e.message);
        const code = e.code === "NO_KEY" ? 500 : 502;
        send(res, code, { error: e.code === "NO_KEY" ? "Server is missing GEMINI_API_KEY. See README." : e.message });
      }
    });
    return;
  }

  if (req.method === "GET") {
    let rel = decodeURIComponent(req.url.split("?")[0]);
    if (rel === "/") rel = "/index.html";
    // serve the sample material too, so the UI can load it
    const base = rel.startsWith("/sample/") ? path.join(__dirname, "..") : PUBLIC;
    const file = path.normalize(path.join(base, rel));
    if (!file.startsWith(base)) { res.writeHead(403); return res.end(); }
    return fs.readFile(file, (err, data) => {
      if (err) { res.writeHead(404); return res.end("Not found"); }
      res.writeHead(200, { "Content-Type": TYPES[path.extname(file)] || "application/octet-stream" });
      res.end(data);
    });
  }

  res.writeHead(405); res.end();
});

if (require.main === module) {
  server.listen(PORT, () => {
    console.log(`Grounded Clinical Reasoning Tutor -> http://localhost:${PORT}`);
    console.log(`Model: ${MODEL} | API key: ${process.env.GEMINI_API_KEY ? "set" : "MISSING (copy .env.example to .env)"}`);
  });
}
module.exports = server;
