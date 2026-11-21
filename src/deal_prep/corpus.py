"""Load the synthetic DMS manifest and extract document text.

Supported formats at this stage: .md, .txt.
PDF, DOCX and XLSX are NOT implemented until Prompt 02 and raise UnsupportedFormatError.
"""
import json
from pathlib import Path

from deal_prep import config

SUPPORTED_FORMATS = {"md", "txt"}
UNIMPLEMENTED_FORMATS = {"pdf", "docx", "xlsx"}

REQUIRED_FIELDS = (
    "document_id", "title", "file_path", "file_type", "source_type", "source_label",
    "issued_at", "effective_from", "effective_to", "approval_status", "version",
)


class UnsupportedFormatError(ValueError):
    pass


class CorpusPathError(ValueError):
    pass


def load_manifest(manifest_path: Path = config.MANIFEST_PATH) -> list[dict]:
    with open(manifest_path, encoding="utf-8") as f:
        return json.load(f)["documents"]


def resolve_document_path(doc: dict, corpus_dir: Path = config.DMS_CORPUS_DIR) -> Path:
    """Resolve a manifest file_path, refusing anything outside the DMS corpus root."""
    root = corpus_dir.resolve()
    path = (root / doc["file_path"]).resolve()
    if not path.is_relative_to(root):
        raise CorpusPathError(f"{doc['document_id']}: {doc['file_path']} is outside {root}")
    return path


def extract_text(path: Path) -> str:
    file_type = path.suffix.lower().lstrip(".")
    if file_type in UNIMPLEMENTED_FORMATS:
        raise UnsupportedFormatError(f".{file_type} extraction is not implemented until Prompt 02")
    if file_type not in SUPPORTED_FORMATS:
        raise UnsupportedFormatError(f".{file_type} is not a supported format")
    return path.read_text(encoding="utf-8")


def load_documents(manifest_path: Path = config.MANIFEST_PATH,
                   corpus_dir: Path = config.DMS_CORPUS_DIR) -> list[tuple[dict, str]]:
    """Return (metadata, text) pairs for every manifest entry."""
    return [(doc, extract_text(resolve_document_path(doc, corpus_dir)))
            for doc in load_manifest(manifest_path)]
