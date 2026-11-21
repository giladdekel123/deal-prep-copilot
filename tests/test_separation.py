"""The DMS pipeline must never read or index the classroom NexaStream corpus."""
from deal_prep import config
from deal_prep.corpus import resolve_document_path

NEXASTREAM_TOKENS = ["NexaStream", "CloudNova", "QuantaLake", "InsightForge", "Data Sphere",
                     "DataSphere", "Apex Financial", "Lumos Retail", "MeridianHealth", "Vantage Logistics"]


def test_corpus_root_is_not_inside_classroom():
    assert not config.DMS_CORPUS_DIR.resolve().is_relative_to(config.CLASSROOM_DIR.resolve())


def test_no_indexed_file_under_classroom(manifest):
    for doc in manifest:
        path = resolve_document_path(doc)
        assert path.is_relative_to(config.DMS_CORPUS_DIR.resolve())
        assert not path.is_relative_to(config.CLASSROOM_DIR.resolve())


def test_no_nexastream_content_in_chunks(chunks):
    for c in chunks:
        for token in NEXASTREAM_TOKENS:
            assert token.lower() not in c["text"].lower(), (c["chunk_id"], token)


def test_collection_name_is_dms_specific():
    assert config.COLLECTION_NAME.startswith("dms_")
