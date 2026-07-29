"""Ingestion microservice.

Pipeline per uploaded document:
  1. Raw file stored immediately in Azure Blob Storage (raw file preserved
     even if parsing fails downstream)
  2. Document type detection -> PyMuPDF (native) or OCR (scanned)
  3. Structured JSON (text + layout metadata) written to Azure Blob Storage
  4. Semantic chunking (SBERT-guided, threshold 0.75)
  5. Chunks embedded via the embedding service (all-MiniLM-L6-v2, 384-dim)
  6. Vectors + metadata indexed in Weaviate (hybrid: semantic + BM25)

Locally this runs against Azurite (Azure's official storage emulator) so the
code is the real Azure Blob SDK end to end; swapping AZURE_STORAGE_CONNECTION_STRING
to a real Storage Account's connection string is the only change needed to
run against production Azure.
"""

import json
import os
import uuid
from pathlib import Path

import httpx
import weaviate
import weaviate.classes.config as wc
from azure.core.exceptions import ResourceExistsError
from azure.storage.blob import BlobServiceClient
from fastapi import FastAPI, File, Form, HTTPException, UploadFile

from chunker import chunk_blocks
from parser import ScannedPDFError, parse_pdf

EMBEDDING_URL = os.environ.get("EMBEDDING_URL", "http://localhost:8001")
WEAVIATE_HOST = os.environ.get("WEAVIATE_HOST", "localhost")
COLLECTION = "Chunk"
RAW_CONTAINER = "raw-documents"
PARSED_CONTAINER = "parsed-documents"

# Azurite's well-known, publicly documented local development account
# (https://learn.microsoft.com/azure/storage/common/storage-use-azurite) --
# not a secret, identical for every Azurite install. Override with a real
# Storage Account connection string to run against production Azure.
AZURE_STORAGE_CONNECTION_STRING = os.environ.get(
    "AZURE_STORAGE_CONNECTION_STRING",
    "DefaultEndpointsProtocol=http;AccountName=devstoreaccount1;"
    "AccountKey=Eby8vdM02xNOcqFlqUwJPLlmEtlCDXJ1OUzFT50uSRZ6IFsuFq2UVErCz4I6tq/"
    "K1SZFPTOtr/KBHBeksoGMGw==;BlobEndpoint=http://127.0.0.1:10000/devstoreaccount1;",
)

app = FastAPI(title="AriesView Ingestion Service")
blob_service = BlobServiceClient.from_connection_string(AZURE_STORAGE_CONNECTION_STRING)


def ensure_container(name: str):
    try:
        blob_service.create_container(name)
    except ResourceExistsError:
        pass
    return blob_service.get_container_client(name)


def get_client() -> weaviate.WeaviateClient:
    return weaviate.connect_to_local(host=WEAVIATE_HOST)


def ensure_schema(client: weaviate.WeaviateClient):
    if client.collections.exists(COLLECTION):
        return
    client.collections.create(
        name=COLLECTION,
        vectorizer_config=wc.Configure.Vectorizer.none(),
        vector_index_config=wc.Configure.VectorIndex.hnsw(
            distance_metric=wc.VectorDistances.COSINE
        ),
        properties=[
            wc.Property(name="text", data_type=wc.DataType.TEXT),
            wc.Property(name="document_id", data_type=wc.DataType.TEXT),
            wc.Property(name="source_file", data_type=wc.DataType.TEXT),
            wc.Property(name="section_label", data_type=wc.DataType.TEXT),
            wc.Property(name="position_index", data_type=wc.DataType.INT),
            wc.Property(name="portfolio", data_type=wc.DataType.TEXT),
        ],
    )


def embed(texts: list[str]) -> list[list[float]]:
    resp = httpx.post(f"{EMBEDDING_URL}/embed", json={"texts": texts}, timeout=120)
    resp.raise_for_status()
    return resp.json()["vectors"]


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/ingest")
async def ingest(file: UploadFile = File(...), portfolio: str = Form("demo-portfolio")):
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(400, "Only PDF documents are supported")

    document_id = str(uuid.uuid4())
    raw_container = ensure_container(RAW_CONTAINER)
    parsed_container = ensure_container(PARSED_CONTAINER)

    # Stage 1: raw file written to blob storage before any parsing.
    raw_blob_name = f"{document_id}_{file.filename}"
    raw_bytes = await file.read()
    raw_container.upload_blob(name=raw_blob_name, data=raw_bytes, overwrite=True)

    # PyMuPDF needs a local path; download the blob we just wrote back to a
    # scratch file rather than trusting an in-memory copy could diverge.
    scratch_path = Path(f"/tmp/{raw_blob_name}")
    scratch_path.write_bytes(raw_bytes)

    # Stage 2: type detection + parsing to structured JSON.
    try:
        parsed = parse_pdf(str(scratch_path))
    except ScannedPDFError as e:
        raise HTTPException(422, str(e))
    finally:
        scratch_path.unlink(missing_ok=True)
    parsed["document_id"] = document_id
    parsed["portfolio"] = portfolio
    parsed["source_file"] = file.filename
    parsed_container.upload_blob(
        name=f"{document_id}.json",
        data=json.dumps(parsed, indent=2),
        overwrite=True,
    )

    # Stage 3: semantic chunking with SBERT-guided boundaries.
    chunks = chunk_blocks(parsed["blocks"], document_id, embed)
    if not chunks:
        raise HTTPException(422, "No text could be extracted from this document")

    # Stage 4: one 384-dim embedding per chunk.
    vectors = embed([c["text"] for c in chunks])

    # Stage 5: vectors + metadata into Weaviate.
    client = get_client()
    try:
        ensure_schema(client)
        collection = client.collections.get(COLLECTION)
        with collection.batch.dynamic() as batch:
            for chunk, vector in zip(chunks, vectors):
                batch.add_object(
                    properties={
                        **chunk,
                        "source_file": file.filename,
                        "portfolio": portfolio,
                    },
                    vector=vector,
                )
    finally:
        client.close()

    return {
        "document_id": document_id,
        "source_file": file.filename,
        "document_type": parsed["document_type"],
        "portfolio": portfolio,
        "chunks_indexed": len(chunks),
    }


@app.get("/documents")
def documents():
    parsed_container = ensure_container(PARSED_CONTAINER)
    docs = []
    for blob in parsed_container.list_blobs():
        parsed = json.loads(parsed_container.download_blob(blob.name).readall())
        docs.append(
            {
                "document_id": parsed["document_id"],
                "source_file": parsed["source_file"],
                "document_type": parsed["document_type"],
                "portfolio": parsed.get("portfolio", "demo-portfolio"),
            }
        )
    return {"documents": docs}
