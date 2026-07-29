// Self-hosted LLM inference. Ollama serves LLaMA locally, standing in for
// the LLaMA 3.1 8B inference service on the Azure VM — no document content
// leaves the machine.
//
// Default model is llama3.2:3b so generation fits in memory on 8GB
// machines; set OLLAMA_MODEL=llama3.1:8b to match production sizing when
// RAM allows. Uses node:http rather than fetch because undici's 5-minute
// headers timeout can abort slow first-load generations.

const http = require("http");

const OLLAMA_URL = new URL(process.env.OLLAMA_URL || "http://localhost:11434");
const MODEL = process.env.OLLAMA_MODEL || "llama3.2:3b";

function postJSON(path, payload) {
  return new Promise((resolve, reject) => {
    const body = JSON.stringify(payload);
    const req = http.request(
      {
        hostname: OLLAMA_URL.hostname,
        port: OLLAMA_URL.port,
        path,
        method: "POST",
        headers: { "Content-Type": "application/json", "Content-Length": Buffer.byteLength(body) },
      },
      (res) => {
        let data = "";
        res.on("data", (chunk) => (data += chunk));
        res.on("end", () => {
          if (res.statusCode !== 200) {
            return reject(new Error(`LLM inference error: ${res.statusCode} ${data}`));
          }
          try {
            resolve(JSON.parse(data));
          } catch (err) {
            reject(err);
          }
        });
      }
    );
    req.on("error", reject);
    req.end(body);
  });
}

async function generate(system, prompt) {
  const data = await postJSON("/api/generate", {
    model: MODEL,
    system,
    prompt,
    stream: false,
    options: { temperature: 0.1, num_ctx: 8192 },
  });
  return data.response.trim();
}

module.exports = { generate, MODEL };
