import json
from pathlib import Path

import pytest

from deal_prep.chunking import chunk_corpus
from deal_prep.corpus import load_documents, load_manifest

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture(scope="session")
def manifest():
    return load_manifest()


@pytest.fixture(scope="session")
def chunks():
    return chunk_corpus(load_documents())


@pytest.fixture(scope="session")
def expectations():
    return json.loads((FIXTURES / "retrieval_expectations.json").read_text(encoding="utf-8"))
