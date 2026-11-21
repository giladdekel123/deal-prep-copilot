"""Expected-versus-observed retrieval scoring at document and passage level."""


def score(question: dict, results: list[dict]) -> dict:
    expected_doc = question["expected_document_id"]
    passage = question["expected_passage"]

    doc_rank = next((r["rank"] for r in results if r["document_id"] == expected_doc), None)
    passage_rank = next(
        (r["rank"] for r in results
         if r["chunk_id"] == passage["chunk_id"]
         and all(s in r["text"] for s in passage["must_contain"])),
        None)
    return {
        "id": question["id"],
        "question": question["question"],
        "expected_document_id": expected_doc,
        "expected_chunk_id": passage["chunk_id"],
        "document_hit": doc_rank is not None,
        "document_rank": doc_rank,
        "passage_hit": passage_rank is not None,
        "passage_rank": passage_rank,
        "observed": [{"rank": r["rank"], "chunk_id": r["chunk_id"],
                      "distance": round(r["distance"], 4)} for r in results],
    }
