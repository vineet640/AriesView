// AriesView API gateway.
//
// Query path: validate JWT -> embed query (SBERT) -> Weaviate hybrid search
// (top-5) -> dedup filter -> prompt assembly -> LLaMA generation -> respond.
// Uploads are proxied to the ingestion service after auth.

const express = require("express");
const cors = require("cors");
const multer = require("multer");

const { login, requireAuth } = require("./auth");
const { retrieve, TOP_K } = require("./retrieval");
const { dedupeChunks } = require("./dedup");
const { assemblePrompt } = require("./prompt");
const { generate, MODEL } = require("./llm");

const INGESTION_URL = process.env.INGESTION_URL || "http://localhost:8002";
const PORT = process.env.PORT || 3001;

const app = express();
app.use(cors());
app.use(express.json());
const upload = multer({ storage: multer.memoryStorage() });

app.get("/health", (_req, res) => res.json({ status: "ok", model: MODEL }));

app.post("/auth/login", (req, res) => {
  const { username, password } = req.body || {};
  const session = login(username, password);
  if (!session) return res.status(401).json({ error: "Invalid credentials" });
  res.json(session);
});

app.post("/query", requireAuth, async (req, res) => {
  const { query } = req.body || {};
  if (!query || !query.trim()) return res.status(400).json({ error: "Missing query" });
  try {
    const start = Date.now();
    const candidates = await retrieve(query, req.user.portfolios);
    const chunks = dedupeChunks(candidates).slice(0, TOP_K);
    if (chunks.length === 0) {
      return res.json({
        answer:
          "No relevant document content was found for this query. Upload documents to this portfolio first.",
        sources: [],
        latency_ms: Date.now() - start,
      });
    }
    const { system, prompt } = assemblePrompt(chunks, query);
    const answer = await generate(system, prompt);
    res.json({
      answer,
      sources: chunks.map((c, i) => ({
        ref: i + 1,
        source_file: c.source_file,
        section_label: c.section_label,
        score: c.score,
      })),
      latency_ms: Date.now() - start,
    });
  } catch (err) {
    console.error(err);
    res.status(502).json({ error: err.message });
  }
});

app.post("/upload", requireAuth, upload.single("file"), async (req, res) => {
  if (!req.file) return res.status(400).json({ error: "Missing file" });
  try {
    const form = new FormData();
    form.append("file", new Blob([req.file.buffer], { type: "application/pdf" }), req.file.originalname);
    form.append("portfolio", req.body.portfolio || req.user.portfolios[0] || "demo-portfolio");
    const resp = await fetch(`${INGESTION_URL}/ingest`, { method: "POST", body: form });
    const data = await resp.json();
    res.status(resp.status).json(data);
  } catch (err) {
    console.error(err);
    res.status(502).json({ error: err.message });
  }
});

app.get("/documents", requireAuth, async (_req, res) => {
  try {
    const resp = await fetch(`${INGESTION_URL}/documents`);
    res.status(resp.status).json(await resp.json());
  } catch (err) {
    res.status(502).json({ error: err.message });
  }
});

if (require.main === module) {
  app.listen(PORT, () => console.log(`API gateway listening on :${PORT} (LLM: ${MODEL})`));
}

module.exports = app;
