#!/usr/bin/env bash
# Stop the AriesView stack.
cd "$(dirname "$0")/.."
pkill -f "uvicorn app:app --app-dir services/embedding" 2>/dev/null || true
pkill -f "uvicorn app:app --app-dir services/ingestion" 2>/dev/null || true
pkill -f "ariesview-api-gateway" 2>/dev/null || true
pkill -f "node src/server.js" 2>/dev/null || true
pkill -f "vite" 2>/dev/null || true
docker compose down
echo "Stopped. (Ollama left running; 'pkill ollama' to stop it too.)"
