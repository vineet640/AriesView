#!/usr/bin/env bash
# Start the full AriesView stack locally.
# Prereqs: Docker Desktop running, Ollama installed, `npm install` done in
# services/api-gateway and frontend, Python venv at .venv with deps installed.
set -euo pipefail
cd "$(dirname "$0")/.."

mkdir -p logs

echo "==> Weaviate (Docker)"
docker compose up -d

echo "==> Ollama"
if ! curl -sf http://localhost:11434/api/version > /dev/null; then
  nohup ollama serve > logs/ollama.log 2>&1 &
fi

echo "==> Embedding service :8001"
nohup .venv/bin/uvicorn app:app --app-dir services/embedding --port 8001 > logs/embedding.log 2>&1 &

echo "==> Ingestion service :8002"
nohup .venv/bin/uvicorn app:app --app-dir services/ingestion --port 8002 > logs/ingestion.log 2>&1 &

echo "==> API gateway :3001"
(cd services/api-gateway && nohup npm start > ../../logs/gateway.log 2>&1 &)

echo "==> Frontend :5173"
(cd frontend && nohup npm run dev > ../logs/frontend.log 2>&1 &)

echo
echo "Waiting for services..."
for i in $(seq 1 60); do
  if curl -sf http://localhost:8001/health > /dev/null \
     && curl -sf http://localhost:8002/health > /dev/null \
     && curl -sf http://localhost:3001/health > /dev/null; then
    break
  fi
  sleep 2
done

echo "AriesView is up:"
echo "  Frontend   http://localhost:5173   (login: analyst / demo)"
echo "  Gateway    http://localhost:3001"
echo "  Ingestion  http://localhost:8002"
echo "  Embedding  http://localhost:8001"
echo "  Weaviate   http://localhost:8080"
echo "  Ollama     http://localhost:11434"
