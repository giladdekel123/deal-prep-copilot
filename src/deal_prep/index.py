"""Offline embedding + local Chroma index.

Offline is enforced here: HF offline flags are set before sentence-transformers is
imported, the model is loaded with local_files_only=True, embeddings are passed to
Chroma explicitly (no Chroma embedding function, so its default ONNX model is never
fetched), and Chroma telemetry is disabled.
"""
import os

os.environ["HF_HUB_OFFLINE"] = "1"
os.environ["TRANSFORMERS_OFFLINE"] = "1"
os.environ["ANONYMIZED_TELEMETRY"] = "False"

from pathlib import Path

import chromadb
from chromadb.config import Settings

from deal_prep import config

_model = None


class EmbeddingModelUnavailable(RuntimeError):
    pass


def get_model(name: str = config.EMBEDDING_MODEL):
    global _model
    if _model is None:
        from sentence_transformers import SentenceTransformer
        try:
            _model = SentenceTransformer(name, device="cpu", local_files_only=True)
        except Exception as e:  # missing from local cache; never download
            raise EmbeddingModelUnavailable(
                f"Embedding model {name!r} is not in the local HuggingFace cache: {e}") from e
    return _model


def embed(texts: list[str]) -> list[list[float]]:
    return get_model().encode(texts, normalize_embeddings=True).tolist()


def _client(chroma_dir: Path):
    return chromadb.PersistentClient(path=str(chroma_dir),
                                     settings=Settings(anonymized_telemetry=False))


def build_index(chunks: list[dict], chroma_dir: Path = config.CHROMA_DIR):
    """Rebuild the DMS collection from scratch."""
    client = _client(chroma_dir)
    if config.COLLECTION_NAME in [c.name for c in client.list_collections()]:
        client.delete_collection(config.COLLECTION_NAME)
    collection = client.create_collection(config.COLLECTION_NAME,
                                          embedding_function=None,
                                          metadata={"hnsw:space": "cosine"})
    collection.add(
        ids=[c["chunk_id"] for c in chunks],
        documents=[c["text"] for c in chunks],
        embeddings=embed([c["text"] for c in chunks]),
        metadatas=[{**c["metadata"], "chunk_id": c["chunk_id"], "section": c["section"],
                    "chunk_type": c["chunk_type"]} for c in chunks],
    )
    return collection


def query(text: str, k: int = 5, chroma_dir: Path = config.CHROMA_DIR) -> list[dict]:
    """Return ranked chunks (rank 1 = best) with text, metadata and cosine distance."""
    collection = _client(chroma_dir).get_collection(config.COLLECTION_NAME, embedding_function=None)
    res = collection.query(query_embeddings=embed([text]), n_results=k)
    return [
        {"rank": i + 1, "chunk_id": cid, "document_id": meta["document_id"],
         "text": doc, "distance": dist, "metadata": meta}
        for i, (cid, doc, meta, dist) in enumerate(zip(
            res["ids"][0], res["documents"][0], res["metadatas"][0], res["distances"][0]))
    ]
