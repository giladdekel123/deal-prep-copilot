"""Heading/paragraph chunking with one chunk per Markdown table row.

Each table row chunk repeats the column headers ("Product: X | Price: Y ...") so a
product stays associated with its own price, unit and terms after retrieval.
"""

BANNER_PREFIX = "> SYNTHETIC"


def _split_row(line: str) -> list[str]:
    return [cell.strip() for cell in line.strip().strip("|").split("|")]


def _is_separator(line: str) -> bool:
    return set(line.replace("|", "").strip()) <= set("-: ")


def _blocks(text: str):
    """Yield (section, kind, payload) where kind is 'paragraph' (str) or 'table' (list of lines)."""
    section = ""
    para, table = [], []

    def flush():
        nonlocal para, table
        if para:
            yield section, "paragraph", " ".join(para)
        if table:
            yield section, "table", table
        para, table = [], []

    for raw in text.splitlines():
        line = raw.strip()
        if line.startswith("|"):
            if para:
                yield from flush()
            table.append(line)
            continue
        if table:
            yield from flush()
        if line.startswith("#"):
            yield from flush()
            section = line.lstrip("#").strip()
        elif not line:
            yield from flush()
        else:
            para.append(line)
    yield from flush()


def _metadata(doc: dict) -> dict:
    # Chroma metadata values must be scalars; represent unknown dates as "".
    return {k: ("" if v is None else v) for k, v in doc.items()}


def chunk_document(doc: dict, text: str) -> list[dict]:
    chunks = []

    def add(section, chunk_type, body):
        chunks.append({
            "chunk_id": f"{doc['document_id']}#{len(chunks)}",
            "document_id": doc["document_id"],
            "section": section,
            "chunk_type": chunk_type,
            "text": f"{section}\n{body}" if section else body,
            "metadata": _metadata(doc),
        })

    for section, kind, payload in _blocks(text):
        if kind == "paragraph":
            if not payload.startswith(BANNER_PREFIX):
                add(section, "paragraph", payload)
            continue
        header = _split_row(payload[0])
        for line in payload[1:]:
            if _is_separator(line):
                continue
            cells = _split_row(line)
            add(section, "table_row", " | ".join(f"{h}: {c}" for h, c in zip(header, cells)))
    return chunks


def chunk_corpus(documents: list[tuple[dict, str]]) -> list[dict]:
    return [c for doc, text in documents for c in chunk_document(doc, text)]
