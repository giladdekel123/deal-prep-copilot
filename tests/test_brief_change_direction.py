"""Final compact-brief correction (owner-approved 2026-11-18): the compact company:brief (follow-up, negotiation and
product-demonstration meetings) requires a change among its developments to be stated with its direction and the
reason the source gives, exactly as the full development topic does; the direction is explicit when the evidence
supports it, and no reason is ever supplied that the source does not give. The coverage markers are unchanged, the
other topics are unchanged, and the ban on inferring the customer's budget, needs or stance stays. Invented companies
only; no company, metric or scenario is named in the rule."""
import json

import pytest

from deal_prep import company_context as cc, contract
from deal_prep.briefing import build_messages
from test_company_essentials_by_purpose_c2 import ABOUT, Q3, bundle, doc, ago

SENTENCE = "For a change, state its direction and the reason the source gives"
PURPOSES = ["follow_up", "negotiation", "product_demo"]

GROWTH = doc("ACME-Q3", ago(10), ["Revenue amounted to EUR 1,569.7 million, up 10.1% year-on-year, driven by higher "
                                  "volumes.", "Order intake was stable."], title="interim report, third quarter 2026")
NO_REASON = doc("ACME-Q3", ago(10), ["Profit for the period was EUR 140.2 million, down 12%."],
                title="interim report, third quarter 2026")
STATIC = doc("ACME-Q3", ago(10), ["Revenue amounted to EUR 900.0 million."], title="interim report, third quarter 2026")


def brief(entries, purpose):
    return {t["id"]: t for t in contract.essential_topics(bundle(entries, purpose))}["company:brief"]


@pytest.mark.parametrize("purpose", PURPOSES)
def test_the_requirement_reaches_the_drafting_input(purpose):
    b = bundle(ABOUT + Q3, purpose)
    topics = contract.essential_topics(b)
    assert SENTENCE in {t["id"]: t for t in topics}["company:brief"]["requirement"]
    sent = json.loads(build_messages(b, topics)[1]["content"])  # what the drafter receives
    mine = {t["id"]: t for t in sent["meeting_contract"]["essential_topics"]}["company:brief"]
    assert SENTENCE in mine["requirement"]


@pytest.mark.parametrize("purpose", PURPOSES)
@pytest.mark.parametrize("entries", [ABOUT + Q3, ABOUT + GROWTH], ids=["profit-decline", "growth"])
def test_decline_and_growth_get_the_same_generic_instruction(purpose, entries):
    req = brief(entries, purpose)["requirement"]
    assert SENTENCE in req
    for word in ("profit", "revenue", "decline", "EBITDA", "Acme", "impairment"):  # nothing specific is written in
        assert word.lower() not in req.split(SENTENCE)[1].split("Keep it brief")[0].lower()


@pytest.mark.parametrize("purpose", PURPOSES)
def test_no_reason_is_required_or_invented_when_the_source_gives_none(purpose):
    t = brief(ABOUT + NO_REASON, purpose)
    req = t["requirement"]
    assert "make the direction explicit when the evidence supports it" in req
    assert "never supply a reason the source does not give" in req
    assert "mainly due to" not in req and "restructuring" not in req  # the source's wording is not baked in
    assert not any("reason" in m or "due" in m for m in t["markers"])  # no marker demands a reason


@pytest.mark.parametrize("purpose", PURPOSES)
def test_the_coverage_markers_are_unchanged(purpose):
    t = brief(ABOUT + Q3, purpose)
    assert len(t["markers"]) == 3 and t["require_all"]
    assert t["labels"][0] == "who it is" and t["labels"][2] == "the development's date"
    assert t["labels"][1].startswith("its most material recent development (")
    ok = {"sections": {"company_overview": [{"kind": "fact", "claim_type": "real_world_fact", "evidence_ids": ["ACME-Q3#2"],
                                             "text": "Acme Corp is a global supplier of industrial valves; its interim "
                                                     "report for the third quarter reported profit of EUR 140.2 million."}]}}
    assert contract.coverage(ok, [t])["topics"]["company:brief"] == "communicated"  # the figure still suffices


@pytest.mark.parametrize("purpose", PURPOSES)
def test_the_sentence_is_part_of_every_compact_brief_even_without_a_dated_development(purpose):
    req = brief(ABOUT, purpose)["requirement"]  # identity only: the rule is still the brief's, nothing else is added
    assert SENTENCE in req and "recent development" not in req


@pytest.mark.parametrize("purpose", PURPOSES)
def test_it_stays_concise_and_keeps_the_priorities(purpose):
    req = brief(ABOUT + Q3, purpose)["requirement"]
    assert "In one or two items" in req and "Keep it brief" in req and "come first" in req
    assert len(req) < 760


def test_the_ban_on_inferring_budget_needs_or_stance_remains():
    neg = brief(ABOUT + Q3, "negotiation")["requirement"]
    for words in ("budget", "cost pressure", "commercial priorities", "negotiating stance", "never infer"):
        assert words in neg
    for purpose in ("follow_up", "product_demo"):
        assert "Never infer Acme Corp's budget or priorities from its public results." in brief(ABOUT + Q3,
                                                                                                purpose)["requirement"]


@pytest.mark.parametrize("purpose", ["introduction", "general"])
def test_the_full_development_topic_and_other_company_topics_are_unchanged(purpose):
    b = bundle(ABOUT + Q3, purpose)
    topics = {t["id"]: t for t in contract.essential_topics(b)}
    assert "company:brief" not in topics
    assert topics["company:latest_release"]["requirement"].count("for a change, its direction and the reason the source "
                                                                 "gives") == 1
    assert all(SENTENCE not in t["requirement"] for t in topics.values())


@pytest.mark.parametrize("purpose", PURPOSES)
def test_every_other_topic_is_identical_with_or_without_the_sentence(purpose, monkeypatch):
    b = bundle(ABOUT + Q3, purpose)
    after = contract.essential_topics(b)
    monkeypatch.setattr(cc, "BRIEF_CHANGE", "")
    before = contract.essential_topics(b)
    assert [t["id"] for t in after] == [t["id"] for t in before]
    for a, o in zip(after, before):
        if a["id"] == "company:brief":
            assert a["requirement"].replace(" " + SENTENCE, "").startswith(o["requirement"][:60])
            assert {k: v for k, v in a.items() if k != "requirement"} == {k: v for k, v in o.items() if k != "requirement"}
        else:
            assert a == o
