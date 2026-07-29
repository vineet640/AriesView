"""SBERT embedding microservice.

Wraps sentence-transformers all-MiniLM-L6-v2 (384-dim) behind a small HTTP
API. The same service is used at ingestion time (chunk embeddings) and at
query time (query embeddings) so both live in the same vector space.
"""

from fastapi import FastAPI
from pydantic import BaseModel
from sentence_transformers import SentenceTransformer

MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"

app = FastAPI(title="AriesView Embedding Service")
model = SentenceTransformer(MODEL_NAME)


class EmbedRequest(BaseModel):
    texts: list[str]


@app.get("/health")
def health():
    return {"status": "ok", "model": MODEL_NAME, "dimensions": 384}


@app.post("/embed")
def embed(req: EmbedRequest):
    vectors = model.encode(req.texts, normalize_embeddings=True)
    return {"vectors": vectors.tolist(), "model": MODEL_NAME}
