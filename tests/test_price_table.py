"""Product-to-price association must survive chunking: one row, one product, its own price."""

EXPECTED_ROWS = {
    ("Ledgerline Core", "Starter"): ("per user per month", "18", "12 months"),
    ("Ledgerline Core", "Business"): ("per user per month", "34", "12 months"),
    ("Ledgerline Engineering Vault", "Enterprise"): ("per user per month", "52", "24 months"),
    ("Records Retention Add-on", "Add-on"): ("per TB per month", "240", "12 months"),
}


def _parse(chunk_text):
    body = chunk_text.splitlines()[-1]
    return dict(part.split(": ", 1) for part in body.split(" | "))


def test_one_chunk_per_price_row(chunks):
    rows = [c for c in chunks if c["document_id"] == "DMS-PRC-001" and c["chunk_type"] == "table_row"]
    assert len(rows) == len(EXPECTED_ROWS)


def test_each_row_keeps_its_own_price_unit_and_term(chunks):
    rows = [c for c in chunks if c["document_id"] == "DMS-PRC-001" and c["chunk_type"] == "table_row"]
    seen = set()
    for c in rows:
        fields = _parse(c["text"])
        key = (fields["Product"], fields["Tier"])
        assert key in EXPECTED_ROWS, key
        unit, price, term = EXPECTED_ROWS[key]
        assert fields["Unit"] == unit
        assert fields["List price (USD)"] == price
        assert fields["Minimum term"] == term
        seen.add(key)
    assert seen == set(EXPECTED_ROWS)


def test_no_row_contains_another_rows_price(chunks):
    rows = [c for c in chunks if c["document_id"] == "DMS-PRC-001" and c["chunk_type"] == "table_row"]
    for c in rows:
        fields = _parse(c["text"])
        own = fields["List price (USD)"]
        others = {p for (_, p, _) in EXPECTED_ROWS.values()} - {own}
        price_fields = [v for k, v in fields.items() if k == "List price (USD)"]
        assert price_fields == [own]
        assert not any(f"List price (USD): {p}" in c["text"] for p in others)


def test_row_chunks_carry_price_list_authority_metadata(chunks):
    for c in chunks:
        if c["chunk_type"] == "table_row":
            assert c["metadata"]["source_type"] == "price_list"
            assert c["metadata"]["approval_status"] == "approved"
            assert c["metadata"]["effective_from"] == "2026-10-01"
