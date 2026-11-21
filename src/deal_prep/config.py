"""Paths and settings. The DMS corpus root is the only directory ever indexed."""
import os
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DMS_CORPUS_DIR = PROJECT_ROOT / "data" / "synthetic" / "dms"
MANIFEST_PATH = DMS_CORPUS_DIR / "manifest.json"
CLASSROOM_DIR = PROJECT_ROOT / "classroom"

CHROMA_DIR = PROJECT_ROOT / os.environ.get("CHROMA_DIR", "chroma_db")
COLLECTION_NAME = "dms_internal_v0"
EMBEDDING_MODEL = os.environ.get("EMBEDDING_MODEL", "sentence-transformers/all-MiniLM-L6-v2")
