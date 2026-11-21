"""C2.3: company identity. A self-description is a sentence whose subject is the organization, followed by what it is
or does; incidental wording ("... and we are cooperating with them") never makes one. Identity facts (where it is
based, where it is listed, its scale) complement it, and nothing is invented when the evidence is insufficient. The
reader never sees internal contract wording in a company gap. Invented companies only."""
import json
from datetime import date, timedelta

import pytest

from deal_prep import briefing, company_context as cc, contract
from deal_prep.disclosures import required_disclosures

FORMS = cc.subject_forms({"identity": {"name": "Acme Corp"}})
TODAY = date(2026, 11, 15)


@pytest.mark.parametrize("sentence", [
    "Acme Corp is a global supplier of industrial valves.",
    "Acme is a world leader in laboratory testing, inspection and certification services.",
    "Acme is one of the largest valve makers in Europe.",
    "Acme, a global innovator in flow control, today announced its results.",
    "Founded in 1887, we work together with customers and partners.",
    "One of the world's leading valve groups, we operate across select markets.",
    "The Group provides inspection and certification services in 140 countries.",
    "We are a family-owned engineering company.",
    "Acme Corp operates 40 plants worldwide.",
])
def test_self_descriptions_of_the_organization_are_recognized(sentence):
    assert cc.self_description(sentence, FORMS)


@pytest.mark.parametrize("sentence", [
    "SafeWork NSW is conducting a separate investigation and we are cooperating with them.",
    "We are cooperating with the regulator on the investigation.",
    "Acme's shares are listed on Nasdaq Copenhagen.",
    "Analysts say Acme is a leader in valves.",
    "Borealis Holdings is a global investor that will acquire Acme Corp.",
    "Acme, in a joint venture with Beta, has signed a contract.",
    "The project is a joint venture with the city.",
    "Revenue amounted to EUR 1.2 billion.",
    "Acme Provides Update on Merger Agreement",  # a headline
])
def test_incidental_wording_is_not_a_self_description(sentence):
    assert not cc.self_description(sentence, FORMS)


def test_a_name_in_any_alphabet_is_recognized_as_the_subject():
    forms = cc.subject_forms({"identity": {"name": "Ørsted"}})
    assert cc.self_description("Ørsted is a global leader in developing offshore wind farms.", forms)
    assert not cc.self_description("With the commissioning of the two projects, Ørsted's capacity increased.", forms)


def st(text, day="2026-11-05", eid="X#1"):
    return {"eid": eid, "doc": eid.split("#")[0], "day": day, "text": text}


def test_identity_facts_where_based_where_listed_and_scale():
    facts = cc.identity_facts([st("Headquartered in Denmark, Acme employs approximately 7,200 people.", eid="A#1"),
                               st("Acme's shares are listed on Nasdaq Copenhagen.", eid="A#2"),
                               st("Created in 1828, Acme's 82,000 employees deliver services in 140 countries.",
                                  eid="A#3")], [])
    # seat (A#1), listing (A#2), scale: A#1 also states one but is already chosen, so the next statement (A#3)
    assert [f["eid"] for f in facts] == ["A#1", "A#2", "A#3"]


def test_a_listing_rule_reference_establishes_a_listing_and_a_forward_statement_is_not_a_fact():
    assert cc._LISTING.search("In accordance with ASX Listing Rule 3.13.2")
    assert cc.identity_facts([st("Acme will employ 5,000 people by 2030.")], []) == []


# --- through the contract ----------------------------------------------------------------------------------------

def ago(days):
    return (TODAY - timedelta(days=days)).isoformat()


def doc(doc_id, published, quotes):
    label = (f"PUBLIC SOURCE · Acme Corp · https://acme.example/{doc_id.lower()} · published {published} · retrieved "
             f"2026-11-15 · verification primary")
    meta = {"doc_type": "public_profile", "subject_org_id": "acme", "publication_date": published,
            "approval_status": "approved"}
    out = [{"evidence_id": f"{doc_id}#0", "info_origin": "public_source", "document_id": doc_id, "metadata": meta,
            "provenance_label": label, "text": f"PUBLIC SOURCE — Acme Corp: release - **Publication date:** {published}"}]
    return out + [{"evidence_id": f"{doc_id}#{n}", "info_origin": "public_source", "document_id": doc_id,
                   "metadata": meta, "provenance_label": label, "text": f'Excerpts > [E{n}] "{q}"'}
                  for n, q in enumerate(quotes, 1)]


def bundle(entries, purpose="introduction"):
    return {"purpose": purpose, "created_at": "2026-11-15T10:00:00+00:00", "status": "complete",
            "company_input": "Acme Corp",
            "identity": {"name": "Acme Corp", "org_id": "acme", "domain": "acme.example", "confidence": 1.0},
            "internal": {"company_profile": {"sections": ["company_overview"], "evidence": list(entries)}},
            "external": {"status": "fallback_30d_found", "evidence": []}, "selection": {},
            "gaps": ["No prior relationship records (proposals, meetings, correspondence) with Acme Corp."]}


def identity_topic(entries):
    return {t["id"]: t for t in contract.essential_topics(bundle(entries))}.get("company:identity")


def test_an_incidental_we_are_does_not_become_the_identity_and_nothing_is_invented():
    entries = doc("AR", ago(80), ["SafeWork NSW is conducting a separate investigation and we are cooperating with "
                                  "them.", "Revenue amounted to EUR 1.2 billion."])
    assert identity_topic(entries) is None  # no self-description, no identity fact: no identity requirement
    assert "no passage in which the organization describes itself" in cc.coverage_gaps(bundle(entries))


def test_identity_facts_alone_give_a_limited_identity_requirement():
    entries = doc("AR", ago(80), ["I want to thank our 32,000 people, who carried 56 million customers.",
                                  "In accordance with ASX Listing Rule 3.13.2"])
    t = identity_topic(entries)
    assert t and set(t["groups"][0]) == {"AR#1", "AR#2"}
    assert "do not describe its business beyond them" in t["requirement"]


def test_a_self_description_comes_first_with_its_facts():
    entries = doc("Q3", ago(10), ["Acme Corp is a world leader in industrial valves.",
                                  "Headquartered in Denmark, Acme employs approximately 7,200 people."])
    t = identity_topic(entries)
    assert t["groups"][0][0] == "Q3#1" or "Q3#1" in t["groups"][0]
    assert "in its own words" in t["requirement"] and "where it is based" in t["requirement"]


# --- the reader never sees internal contract wording in a company gap -------------------------------------------

def test_a_company_gap_is_shown_in_plain_words_and_the_drafters_words_are_kept():
    entries = doc("AR", ago(80), ["I want to thank our 32,000 people, who carried 56 million customers."])
    b = bundle(entries)

    def drafter(messages):
        d = {"sections": {s: [] for s in briefing.SECTIONS}, "disclosures": []}
        d["sections"]["meeting_recommendations"] = [{"kind": "recommendation", "evidence_ids": [], "claim_type": None,
                                                     "text": "Ask which systems Acme uses today, who decides and how, "
                                                             "and on what timing."}]
        d["disclosures"] = [{"id": x["id"], "text": x["text"]} for x in required_disclosures(b)]
        d["disclosures"] += [{"id": f"empty_section:{s}", "text": "Nothing supported."}
                             for s, v in d["sections"].items() if not v]
        d["disclosures"].append({"id": "topic_gap:company:identity",
                                 "text": "The designated evidence describes an investigation, not who Acme is."})
        return json.dumps(d)
    out = briefing.draft_briefing(b, drafter)
    gap = next(d for d in out["disclosures"] if d["id"] == "topic_gap:company:identity")
    assert gap["text"] == briefing.COMPANY_GAP_TEXT["company:identity"]
    assert "designated" not in gap["text"] and "designated" in gap["model_text"]


def test_a_headcount_sentence_is_a_scale_fact_not_a_self_description():
    assert not cc.self_description("Headquartered in Denmark, Acme employs approximately 7,200 people.", FORMS)
    assert cc.identity_facts([st("Headquartered in Denmark, Acme employs approximately 7,200 people.")], [])


def test_a_self_description_that_repeats_a_chosen_one_gives_way_to_one_that_adds_information():
    entries = doc("Q3", ago(10), ["Acme Corp is a global leader in developing and operating valve plants."]) + \
        doc("ABOUT", "unknown", ["Acme Corp is the global leader in developing and operating valve plants.",
                                 "In addition to valves, we own and operate pumps, meters and control software."])
    ids = identity_topic(entries)["groups"][0]
    assert "Q3#1" in ids and "ABOUT#2" in ids and "ABOUT#1" not in ids


def test_a_word_of_the_name_is_never_read_as_a_description_verb():
    """Found by the meeting-contract replay: "<first word> Build Group operated ..." read as "<name> builds", and, with
    the registry alias "<two words>", "<two words> Works was bought ..." read as "<name> works"."""
    forms = cc.subject_forms({"identity": {"name": "Halden Build Group"}})
    assert not cc.self_description("At the end of 2025, Halden Build Group operated 38 active building sites.", forms)
    assert cc.self_description("Halden Build Group builds hospitals and schools.", forms)
    forms = cc.subject_forms({"identity": {"name": "Orrin Precision Works", "aliases": ["Orrin Precision"]}})
    assert not cc.self_description("Orrin Precision Works was bought by its management team.", forms)
    assert cc.self_description("Orrin Precision Works supplies machined parts to carmakers.", forms)


def aggregator(doc_id, quotes):
    label = ("PUBLIC SOURCE · CompanyFacts Directory · https://companyfacts.example/acme · published unknown · "
             "retrieved 2026-11-15 · verification single_secondary")
    meta = {"doc_type": "public_profile", "subject_org_id": "acme", "publication_date": "unknown",
            "approval_status": "approved"}
    return [{"evidence_id": f"{doc_id}#{n}", "info_origin": "public_source", "document_id": doc_id, "metadata": meta,
             "provenance_label": label, "text": f'Excerpts > [E{n}] "{q}"'} for n, q in enumerate(quotes, 1)]


def test_a_figure_another_source_contradicts_is_not_an_identity_fact():
    """The contested topic gives both sides, unresolved; the identity topic never states one of them as a fact."""
    own = doc("AB", ago(80), ["At the end of 2025, Acme Corp operated 40 active sites."])
    assert set(identity_topic(own)["groups"][0]) == {"AB#1"}
    same = own + aggregator("AGG", ["At the end of 2025, Acme Corp operated 40 active sites."])
    assert set(identity_topic(same)["groups"][0]) == {"AB#1"}  # a restatement confirms it
    other = own + aggregator("AGG", ["At the end of 2025, Acme Corp operated 42 active sites."])
    assert identity_topic(other) is None
    assert [t for t in contract.essential_topics(bundle(other)) if t["id"].startswith("contested:")]
