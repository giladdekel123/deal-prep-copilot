"""Document- and passage-level retrieval against pre-written expectations (offline)."""
import pytest

from deal_prep.evaluation import score
from deal_prep.index import EmbeddingModelUnavailable, build_index, query


@pytest.fixture(scope="module")
def index_dir(tmp_path_factory, chunks):
    d = tmp_path_factory.mktemp("chroma")
    try:
        build_index(chunks, chroma_dir=d)
    except EmbeddingModelUnavailable as e:
        pytest.skip(f"cached embedding model unavailable: {e}")
    return d


@pytest.fixture(scope="module")
def scored(index_dir, expectations):
    k = expectations["k"]
    return {q["id"]: score(q, query(q["question"], k=k, chroma_dir=index_dir))
            for q in expectations["questions"]}


@pytest.mark.parametrize("qid", ["Q1", "Q2", "Q3", "Q4"])
def test_document_level_hit(scored, qid):
    r = scored[qid]
    assert r["document_hit"], f"{qid}: expected {r['expected_document_id']} not in top-k {r['observed']}"


@pytest.mark.parametrize("qid", ["Q1", "Q2", "Q3", "Q4"])
def test_passage_level_hit(scored, qid):
    r = scored[qid]
    assert r["passage_hit"], f"{qid}: expected passage {r['expected_chunk_id']} not in top-k {r['observed']}"


def test_query_returns_metadata(index_dir):
    res = query("price list", k=1, chroma_dir=index_dir)
    meta = res[0]["metadata"]
    assert meta["source_label"] == "synthetic"
    assert meta["chunk_id"] == res[0]["chunk_id"]
