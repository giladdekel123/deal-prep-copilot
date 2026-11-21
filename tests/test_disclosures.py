"""Prompt 04 step 5: gap and conflict disclosure; uncertainty never becomes a confident claim.

Public portfolio version: the NVQ-PUB-005 and NVQ-PUB-007 passages used below are project-written summaries (prefixed
"Summary:"), not quotations of the source pages, so the expected strings differ from the development repository's.
(See THIRD_PARTY_NOTICES.md.) The conflict logic and expected structure are unchanged.

Simulated model output only. Where a case needs specific corpus passages (draft notes, superseded
price list, conflicting statements), they are added as agent-retrieved supplemental evidence.
"""
import copy
import json
from datetime import datetime, timedelta, timezone

import pytest

from deal_prep.briefing import build_messages, draft_briefing
from deal_prep.citations import validate_citations
from deal_prep.disclosures import required_disclosures, unresolved_conflicts
from deal_prep.kb_index import build_kb_index, load_kb_chunks, to_evidence
from deal_prep.orchestrator import gather_research
from deal_prep.provenance import load_registry
from deal_prep.web_research import Budget, SearchConfig, TavilyClient, TransportError

NOW = datetime(2026, 11, 6, 12, 0, tzinfo=timezone.utc)
CHUNKS = {c["chunk_id"]: c for c in load_kb_chunks()}
REGISTRY = load_registry()


class FakeTransport:
    def __init__(self, *responses):
        self.queue = list(responses)

    def __call__(self, url, json, headers, timeout):
        nxt = self.queue.pop(0)
        if isinstance(nxt, Exception):
            raise nxt
        return nxt


class FakeModel:
    def __init__(self, *outputs):
        self.outputs = list(outputs)

    def __call__(self, messages):
        return json.dumps(self.outputs.pop(0))


def news(company):
    when = (NOW - timedelta(hours=6)).strftime("%a, %d %b %Y %H:%M:%S GMT")
    return {"results": [{"url": "https://news.example.com/a", "title": f"{company} wins design contract",
                         "content": "...", "score": 0.9, "published_date": when}]}


@pytest.fixture(scope="module")
def kb(tmp_path_factory):
    d = tmp_path_factory.mktemp("disclosure_kb")
    build_kb_index(chroma_dir=d)
    return d


def research(kb, company, *responses, domain=None):
    config = SearchConfig()
    client = TavilyClient("test-key-not-real", post=FakeTransport(*responses), config=config)
    return gather_research(company, news_client=client, budget=Budget(config), domain=domain, chroma_dir=kb, now=NOW)


@pytest.fixture(scope="module")
def arup(kb):
    return research(kb, "Arup", news("Arup"), domain="arup.com")


@pytest.fixture(scope="module")
def arup_narrow(kb):
    """The bundle as retrieved before I7 (the top passages, not one passage per document): only one side of the
    1977/1979 ambiguity ranks, so the conflict-sources fetch must supply the other. That fetch still matters under
    I7 for any side that ranking or company_context.PROFILE_DOCUMENTS leaves out."""
    from deal_prep import company_context, orchestrator
    real_run_internal = orchestrator._run_internal

    def one_sided(topic, identity, k, chroma_dir):
        # Public portfolio version: with the project-written summaries both sides of the ambiguity now rank in the top
        # results, so the one-sided retrieval this fixture describes is forced here by leaving NVQ-PUB-007 out of the
        # ranked results. The conflict-source fetch that these tests check (by document ID, no ranking) is unchanged.
        results, trace = real_run_internal(topic, identity, k, chroma_dir)
        return [e for e in results if e["document_id"] != "NVQ-PUB-007"], trace

    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(company_context, "ENABLED", False)
        mp.setattr(orchestrator, "_run_internal", one_sided)
        return research(kb, "Arup", news("Arup"), domain="arup.com")


def with_chunks(bundle, *predicates):
    """Copy of the bundle plus the first corpus chunk matching each predicate, as supplemental evidence."""
    b = copy.deepcopy(bundle)
    for pred in predicates:
        cid, c = next((cid, c) for cid, c in CHUNKS.items() if pred(c))
        b.setdefault("supplemental", []).append({**to_evidence(cid, c["text"], c["metadata"], REGISTRY),
                                                 "_tool": "search_internal"})
    return b


def doc_chunk(doc_id, contains=""):
    return lambda c: c["metadata"]["document_id"] == doc_id and contains in c["text"]


def clean(bundle, topic):
    """First approved evidence not in an UNRESOLVED conflict (resolved groups such as C1 are citable)."""
    unresolved = set(unresolved_conflicts(bundle, NOW.date()))
    return next(e["evidence_id"] for e in bundle["internal"][topic]["evidence"]
                if e["metadata"]["conflict_group"] not in unresolved and e["metadata"]["approval_status"] == "approved")


def chunk_id(bundle, doc_id, contains=""):
    return next(e["evidence_id"] for e in bundle["supplemental"]
                if e["document_id"] == doc_id and contains in e["text"])


def fact(text, ids, claim_type):
    return {"kind": "fact", "text": text, "evidence_ids": ids, "claim_type": claim_type}


def base_draft(bundle, **overrides):
    web = bundle["external"]["evidence"][0]["evidence_id"]
    defaults = {  # built lazily, so a bundle without e.g. relationship records can override that section
        "company_overview": lambda: [fact("Arup is owned in trust for its employees.",
                                          [clean(bundle, "company_profile")], "real_world_fact")],
        "recent_developments": lambda: [fact("Arup won a design contract.", [web], "real_world_fact")],
        "our_relationship": lambda: [fact("Synthetic record: negotiation in progress.",
                                          [clean(bundle, "relationship_history")], "relationship")],
        "opportunities": lambda: [{"kind": "inference", "text": "Drawing control may matter.", "evidence_ids": [web]}],
        "competitive_positioning": lambda: [{"kind": "recommendation", "text": "Compare total cost.", "evidence_ids": []}],
        "meeting_recommendations": lambda: [{"kind": "recommendation", "text": "Confirm the user count.",
                                             "evidence_ids": []}],
    }
    sections = {name: overrides[name] if name in overrides else make() for name, make in defaults.items()}
    return {"sections": sections,
            "disclosures": [{"id": d["id"], "text": d["text"]} for d in required_disclosures(bundle)]}


def codes(bundle, d):
    return sorted({x["code"] for x in validate_citations(d, bundle)["issues"]})


# --- what must be disclosed ---------------------------------------------------------

def test_real_public_conflict_is_a_required_disclosure(arup):
    assert unresolved_conflicts(arup, NOW.date()) == {"PUB-ARUP-TRUST-YEAR": ["NVQ-PUB-005", "NVQ-PUB-007"]}
    d = next(x for x in required_disclosures(arup) if x["id"] == "conflict:PUB-ARUP-TRUST-YEAR")
    # Owner reassessment: a 1977 decision and trust ownership "since 1979" can both be true, so this is a
    # chronological ambiguity (still disclosed, still unresolved), not an established contradiction.
    assert d["kind"] == "chronological_ambiguity" and "neither date is treated as established" in d["text"]


def test_conflict_disclosure_explains_the_disagreement_with_traceable_dated_sources(arup):
    # Owner review of the live Arup PDF: the disclosure named NVQ-PUB-005/007, but neither appeared in Sources,
    # and the text claimed "Both are shown with their dates" when no dates were shown.
    from deal_prep.evidence import evidence_index
    d = next(x for x in required_disclosures(arup) if x["id"] == "conflict:PUB-ARUP-TRUST-YEAR")
    for needed in ('NVQ-PUB-005 "Arup: history"', '"Summary: in 1977 the firm took the decision', "transfer its ownership",
                   'NVQ-PUB-007 "Arup: financial statements, year ended 31 March 2024"',
                   '"Summary: the 2024 financial statements say that since 1979 Arup has belonged to trusts', "publication date unknown", "retrieved 2026-11-05",
                   "Chronological ambiguity", "can both be true", "neither date is treated as established"):
        assert needed in d["text"], needed
    assert "shown with their dates" not in d["text"]
    assert '."' + "." not in d["text"]  # no doubled full stop after a verbatim quote
    assert [e.split("#")[0] for e in d["evidence_ids"]] == ["NVQ-PUB-005", "NVQ-PUB-007"]
    assert set(d["evidence_ids"]) <= set(evidence_index(arup))  # traceable: real retrieved evidence


def full_texts(bundle):
    from deal_prep.evidence import kb_evidence
    return {e["evidence_id"]: " ".join(e["text"].split()) for e in kb_evidence(bundle)}


def test_quoted_statements_are_supported_by_their_cited_passages(arup):
    # Owner review: [14] cited a passage of NVQ-PUB-007 that did not contain the quoted 1979 sentence.
    from deal_prep.kb_index import load_manifest
    manifest = {d["document_id"]: d for d in load_manifest()}
    texts = full_texts(arup)
    conflicts = [d for d in required_disclosures(arup) if d["id"].startswith("conflict:")]
    assert conflicts
    for d in conflicts:
        for eid in d["evidence_ids"]:
            statement = manifest[eid.split("#")[0]]["conflict_statement"]
            assert f'"{statement}"' in d["text"], eid  # the claim is quoted...
            assert " ".join(statement.split()) in texts[eid], eid  # ...and its cited passage contains it


def test_conflict_detected_when_only_one_side_was_retrieved(arup, arup_narrow):
    # The narrow profile search retrieves the 1977 passage but no NVQ-PUB-007 passage; the 1979 side must be
    # fetched so the chronological ambiguity is still disclosed (detection must not depend on ranking luck).
    retrieved = {e["document_id"] for e in arup_narrow["internal"]["company_profile"]["evidence"]}
    fetched = {e["document_id"] for e in arup_narrow.get("conflict_sources", [])}
    assert "NVQ-PUB-005" in retrieved and "NVQ-PUB-007" in fetched
    assert any(x["id"] == "conflict:PUB-ARUP-TRUST-YEAR" for x in required_disclosures(arup_narrow))
    # I7: the profile is read across documents, so both sides are retrieved directly, and still disclosed.
    assert {"NVQ-PUB-005", "NVQ-PUB-007"} <= {e["document_id"] for e in arup["internal"]["company_profile"]["evidence"]}
    assert any(x["id"] == "conflict:PUB-ARUP-TRUST-YEAR" for x in required_disclosures(arup))


def test_unrelated_passage_of_a_conflict_document_does_not_trigger_a_disclosure(arup):
    b = with_chunks(arup, doc_chunk("NVQ-PRD-001", "Deployment"))  # PRD-001 passage that is not the SCIM sentence
    assert not any(x["id"] == "conflict:C2" for x in required_disclosures(b))


def test_reference_14_is_the_exact_1979_passage(arup):
    d = next(x for x in required_disclosures(arup) if x["id"] == "conflict:PUB-ARUP-TRUST-YEAR")
    ev_1979 = d["evidence_ids"][1]
    assert ev_1979.startswith("NVQ-PUB-007#")
    assert "Summary: the 2024 financial statements say that since 1979 Arup has belonged to trusts that hold it for its members." in full_texts(arup)[ev_1979]
    assert "Limitations" not in full_texts(arup)[ev_1979].split()[0]  # not the limitations note any more


def test_unretrieved_passage_is_never_quoted(arup_narrow):
    import copy
    b = copy.deepcopy(arup_narrow)
    assert b.get("conflict_sources")  # the exact 1979 passage was fetched for this bundle...
    # ...simulate it being unavailable: NVQ-PUB-007 is present only through a passage without the 1979 sentence.
    other = next(c for cid, c in CHUNKS.items()
                 if c["metadata"]["document_id"] == "NVQ-PUB-007" and "since 1979 Arup has belonged" not in c["text"])
    b["conflict_sources"] = [to_evidence(other["chunk_id"], other["text"], other["metadata"], REGISTRY)]
    d = next(x for x in required_disclosures(b) if x["id"] == "conflict:PUB-ARUP-TRUST-YEAR")
    assert "since 1979 Arup has belonged" not in d["text"]
    assert "not retrieved, so it is not quoted" in d["text"]


def test_true_contradiction_c2_keeps_contradiction_wording(arup):
    b = with_chunks(arup, doc_chunk("NVQ-PRD-001", "SCIM"), doc_chunk("NVQ-POL-002", "SCIM"))
    d = next(x for x in required_disclosures(b) if x["id"] == "conflict:C2")
    assert d["kind"] == "unresolved_conflict" and "contradict each other" in d["text"]
    assert "Chronological ambiguity" not in d["text"]


def test_conflict_disclosure_prefers_the_passage_containing_the_statement(arup):
    from deal_prep.evidence import evidence_index
    b = with_chunks(arup, doc_chunk("NVQ-PUB-005", "Summary: in 1977"), doc_chunk("NVQ-PUB-007", "Summary: the 2024"))
    d = next(x for x in required_disclosures(b) if x["id"] == "conflict:PUB-ARUP-TRUST-YEAR")
    texts = [" ".join(evidence_index(b)[e]["excerpt"].split()) for e in d["evidence_ids"]]
    assert "Summary: in 1977" in texts[0] and "Summary: the 2024" in texts[1]


def test_synthetic_conflict_c2_disclosure_states_both_sides_and_effective_dates(arup):
    b = with_chunks(arup, doc_chunk("NVQ-PRD-001", "SCIM"), doc_chunk("NVQ-POL-002", "SCIM"))
    d = next(x for x in required_disclosures(b) if x["id"] == "conflict:C2")
    assert "SCIM user provisioning is available on the Business and Enterprise tiers." in d["text"]
    assert "SCIM user provisioning is available on the Enterprise tier only." in d["text"]
    assert "effective from 2026-07-10" in d["text"] and "effective from 2026-09-15" in d["text"]
    assert [e.split("#")[0] for e in d["evidence_ids"]] == ["NVQ-POL-002", "NVQ-PRD-001"]


def test_conflict_statements_are_verbatim_source_text():
    from deal_prep.corpus import resolve_document_path
    from deal_prep.kb_extract import extract
    from deal_prep.kb_index import load_manifest
    from deal_prep.provenance import KB_DIR
    docs = [d for d in load_manifest() if d.get("conflict_statement")]
    assert {d["document_id"] for d in docs} == {"NVQ-PUB-005", "NVQ-PUB-007", "NVQ-PRD-001", "NVQ-POL-002"}
    for d in docs:
        if d["info_origin"] == "public_source":
            assert d["conflict_statement"] in [e["text"] for e in d["excerpts"]], d["document_id"]
        full_text, _ = extract(resolve_document_path(d, corpus_dir=KB_DIR))
        assert d["conflict_statement"] in full_text, d["document_id"]


def test_conflicting_approved_statements_c2_are_disclosed(arup):
    b = with_chunks(arup, doc_chunk("NVQ-PRD-001", "SCIM"), doc_chunk("NVQ-POL-002", "SCIM"))
    assert unresolved_conflicts(b, NOW.date())["C2"] == ["NVQ-POL-002", "NVQ-PRD-001"]


def test_resolved_conflict_c1_is_not_a_required_disclosure(arup):
    b = with_chunks(arup, doc_chunk("NVQ-PRC-2025-v1", "Tier: Business"), doc_chunk("NVQ-PRC-2026-v1", "Tier: Business"))
    assert "C1" not in unresolved_conflicts(b, NOW.date())  # the superseded list loses on authority


def test_research_gaps_become_required_disclosures(kb):
    b = research(kb, "Ashtrom Group", news("Ashtrom Group"))
    gaps = [d for d in required_disclosures(b) if d["kind"] == "gap"]
    assert gaps and "No prior relationship records" in gaps[0]["text"]


@pytest.mark.parametrize("company, responses, domain, status", [
    ("Teva Pharmaceutical", [news("Teva Pharmaceutical")], None, "external_with_internal_gap"),
    ("Arup", [TransportError(503)], "arup.com", "partial_internal_only"),
])
def test_incomplete_research_must_be_disclosed(kb, company, responses, domain, status):
    b = research(kb, company, *responses, domain=domain)
    assert b["status"] == status
    assert any(d["id"] == "status" and "Incomplete research" in d["text"] for d in required_disclosures(b))


# --- uncertainty cannot become a confident claim -------------------------------------

def test_valid_draft_with_all_disclosures_passes(arup):
    assert validate_citations(base_draft(arup), arup)["valid"]


def test_missing_required_disclosure_rejected(arup):
    d = base_draft(arup)
    d["disclosures"] = []
    assert codes(arup, d) == ["missing_disclosure"]


def test_one_side_of_an_unresolved_conflict_cannot_be_stated_as_fact(arup):
    side = next(e["evidence_id"] for e in arup["internal"]["company_profile"]["evidence"]
                if e["metadata"]["conflict_group"] == "PUB-ARUP-TRUST-YEAR")
    d = base_draft(arup, company_overview=[fact("Arup became trust-owned in 1977.", [side], "real_world_fact")])
    assert codes(arup, d) == ["unresolved_conflict_as_fact"]


def test_conflict_may_be_described_as_an_inference_when_disclosed(arup):
    side = next(e["evidence_id"] for e in arup["internal"]["company_profile"]["evidence"]
                if e["metadata"]["conflict_group"] == "PUB-ARUP-TRUST-YEAR")
    d = base_draft(arup, company_overview=[
        {"kind": "inference", "text": "Arup's own sources give different years (1977 and 1979) for trust ownership.",
         "evidence_ids": [side]}])
    assert validate_citations(d, arup)["valid"]


def test_c2_conflicting_statement_cannot_be_a_fact(arup):
    b = with_chunks(arup, doc_chunk("NVQ-PRD-001", "SCIM"), doc_chunk("NVQ-POL-002", "SCIM"))
    d = base_draft(b, opportunities=[fact("SCIM is included in Business.", [chunk_id(b, "NVQ-POL-002", "SCIM")],
                                          "vendor_product")])
    assert codes(b, d) == ["unresolved_conflict_as_fact"]


def test_draft_meeting_notes_cannot_support_a_fact(arup):
    b = with_chunks(arup, doc_chunk("NVQ-MTG-002", "encryption"))
    d = base_draft(b, our_relationship=[fact("Arup asked about customer-managed keys.",
                                             [chunk_id(b, "NVQ-MTG-002", "encryption")], "meeting_history")])
    assert codes(b, d) == ["non_authoritative_evidence"]


def test_superseded_price_cannot_support_a_current_price_fact(arup):
    b = with_chunks(arup, doc_chunk("NVQ-PRC-2025-v1", "Tier: Business"), doc_chunk("NVQ-PRC-2026-v1", "Tier: Business"))
    old, new = chunk_id(b, "NVQ-PRC-2025-v1", "Tier: Business"), chunk_id(b, "NVQ-PRC-2026-v1", "Tier: Business")
    assert codes(b, base_draft(b, opportunities=[fact("Core Business costs 30 USD.", [old], "vendor_price")])) == \
        ["non_authoritative_evidence"]
    assert validate_citations(base_draft(b, opportunities=[fact("Core Business costs 34 USD.", [new], "vendor_price")]),
                              b)["valid"]


def test_relationship_fact_must_cite_this_customers_records(arup):
    vendor_doc = clean(arup, "vendor_products_pricing")
    d = base_draft(arup, our_relationship=[fact("We have an ongoing relationship.", [vendor_doc], "relationship")])
    assert codes(arup, d) == ["not_this_customer"]


def test_empty_section_must_be_explained(kb):
    b = research(kb, "Ashtrom Group", news("Ashtrom Group"))
    d = base_draft(b, company_overview=[fact("Ashtrom Group was founded in 1963.", [clean(b, "company_profile")],
                                             "real_world_fact")], our_relationship=[])
    d["sections"]["recent_developments"][0]["text"] = "Ashtrom Group won a design contract."
    assert codes(b, d) == ["unexplained_empty_section"]
    d["disclosures"].append({"id": "empty_section:our_relationship", "text": "No prior relationship records."})
    assert validate_citations(d, b)["valid"]


def test_cannot_invent_relationship_for_a_new_lead(kb):
    b = research(kb, "Ashtrom Group", news("Ashtrom Group"))
    d = base_draft(b, our_relationship=[fact("Ashtrom is an existing customer.", [clean(b, "vendor_products_pricing")],
                                             "relationship")])
    assert "not_this_customer" in codes(b, d)


# --- integration with the drafting call ------------------------------------------------

def test_undisclosed_conflict_retried_then_rejected(arup):
    d = base_draft(arup)
    d["disclosures"] = []
    out = draft_briefing(arup, FakeModel(d, d))
    assert out["status"] == "citation_validation_failed" and out["draft"] is None
    assert {x["code"] for x in out["citation_issues"]} == {"missing_disclosure"}


def test_briefing_carries_canonical_disclosure_text_not_the_model_paraphrase(arup):
    d = base_draft(arup)
    for x in d["disclosures"]:
        x["text"] = "minor detail, can be ignored"  # model downplays the uncertainty
    out = draft_briefing(arup, FakeModel(d))
    assert out["status"] == "ok"
    assert out["disclosures"] == required_disclosures(arup)
    assert all("minor detail" not in x["text"] for x in out["disclosures"])


def test_prompt_lists_required_disclosures_and_the_no_guessing_rule(arup):
    system, user = build_messages(arup)
    payload = json.loads(user["content"])
    assert [x["id"] for x in payload["required_disclosures"]] == [x["id"] for x in required_disclosures(arup)]
    assert "Never turn uncertainty into confident claims" in system["content"]
    assert "empty_section:<section name>" in system["content"]
