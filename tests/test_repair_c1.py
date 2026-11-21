"""C1: the repair loop never trades away correct information. A correct figure such as EUR 1,569.7 million is not
flagged, so it is never sent back; a repair that drops a verified figure counts that as a loss; a repair that fixes a
genuinely unsupported figure is still accepted; every repair's gains and losses are recorded. Simulated drafts on an
invented company ("Acme Corp"), offline."""
import json
from datetime import date, timedelta

from deal_prep import briefing, contract
from deal_prep.disclosures import required_disclosures

TODAY = date(2026, 11, 15)
CREATED = "2026-11-15T10:00:00+00:00"
PUBLISHED = (TODAY - timedelta(days=10)).isoformat()
LABEL = (f"PUBLIC SOURCE · Acme Corp · https://acme.example/q3 · published {PUBLISHED} · retrieved 2026-11-15 · "
         f"verification primary")
META = {"doc_type": "public_profile", "subject_org_id": "acme", "publication_date": PUBLISHED,
        "approval_status": "approved"}
QUOTES = ["Revenue amounted to EUR 1,569.7 million, up 10.1% year-on-year.", "Net debt totaled EUR 312.4 million."]
EVIDENCE = [{"evidence_id": "ACME-Q3#0", "info_origin": "public_source", "document_id": "ACME-Q3",
             "provenance_label": LABEL, "metadata": dict(META),
             "text": "PUBLIC SOURCE — Acme Corp: interim report, third quarter 2026 - **Publication date:** "
                     f"{PUBLISHED}"}] + \
           [{"evidence_id": f"ACME-Q3#{n}", "info_origin": "public_source", "document_id": "ACME-Q3",
             "provenance_label": LABEL, "metadata": dict(META), "text": f'Excerpts > [E{n}] "{q}"'}
            for n, q in enumerate(QUOTES, 1)]
REVENUE = ("Acme's interim report for the third quarter of 2026, published "
           f"{TODAY.day - 10} November 2026, gives revenue of EUR 1,569.7 million, up 10.1% year-on-year.")
DEBT = "Net debt totaled EUR 312.4 million."


def bundle():
    return {"purpose": "introduction", "created_at": CREATED, "status": "complete", "company_input": "Acme Corp",
            "identity": {"name": "Acme Corp", "org_id": "acme", "domain": "acme.example", "country": None,
                         "confidence": 1.0},
            "internal": {"company_profile": {"sections": ["company_overview"], "evidence": list(EVIDENCE)}},
            "external": {"status": "fallback_30d_found", "evidence": []}, "selection": {},
            "gaps": ["No prior relationship records (proposals, meetings, correspondence) with Acme Corp."]}


def fact(text, ids):
    return {"kind": "fact", "text": text, "evidence_ids": ids, "claim_type": "real_world_fact"}


def rec(text):
    return {"kind": "recommendation", "text": text, "evidence_ids": [], "claim_type": None}


QUESTIONS = [rec("Ask which systems Acme uses today, who would decide on tools of this kind and how, and on what "
                 "timing.")]


def as_json(b, sections):
    d = {"sections": {s: [] for s in briefing.SECTIONS}, "disclosures": []}
    d["sections"].update(sections)
    d["disclosures"] = [{"id": x["id"], "text": x["text"]} for x in required_disclosures(b)]
    d["disclosures"] += [{"id": f"empty_section:{s}", "text": "Nothing supported."}
                         for s, v in d["sections"].items() if not v]
    return json.dumps(d)


class Drafter:
    """A simulated drafter returning the given drafts in turn (the last one repeats)."""

    def __init__(self, *drafts):
        self.drafts, self.messages = drafts, []

    def __call__(self, messages):
        self.messages.append(messages)
        return as_json(bundle(), self.drafts[min(len(self.messages), len(self.drafts)) - 1])


def run(*drafts):
    gen = Drafter(*drafts)
    return briefing.draft_briefing(bundle(), gen, repair_coverage=True), gen


def text_of(out):
    return " ".join(i["text"] for items in out["draft"]["sections"].values() for i in items)


def test_a_correct_thousands_and_decimal_figure_is_not_flagged_or_sent_back():
    """The v2 defect, on an invented company: a first draft that states EUR 1,569.7 million exactly."""
    out, gen = run({"recent_developments": [fact(REVENUE, ["ACME-Q3#0", "ACME-Q3#1"])],
                    "meeting_recommendations": QUESTIONS})
    assert out["status"] == "ok"
    assert out["coverage"]["first_draft_figures"]["untraced"] == []
    assert out["coverage"]["first_draft_figures"]["mismatched"] == []
    assert "1,569.7" in text_of(out)
    assert all("1,569" not in m[-1]["content"] for m in gen.messages[1:])  # never sent back as a figure problem


def test_a_repair_that_drops_a_verified_figure_without_fixing_a_problem_is_rejected_and_recorded():
    complete = {"recent_developments": [fact(REVENUE, ["ACME-Q3#0", "ACME-Q3#1"])],
                "company_overview": [fact(DEBT, ["ACME-Q3#2"])], "meeting_recommendations": QUESTIONS}
    loses_debt = {"recent_developments": [fact(REVENUE, ["ACME-Q3#0", "ACME-Q3#1"])],
                  "meeting_recommendations": QUESTIONS}
    gaps = {**complete, "meeting_recommendations": []}  # the first draft lacks the discovery questions
    out, gen = run(gaps, {**loses_debt, "meeting_recommendations": QUESTIONS})
    repair = out["coverage"]["repair"]
    assert repair["requested"] is True
    assert "312.4" in [f["figure"] for f in repair["lost_figures"]]
    # the repair gains one topic but loses a verified figure: not better, so the first draft is kept
    assert repair["accepted"] is False and out["coverage"]["repaired"] is False
    assert "312.4" in text_of(out)


def test_a_repair_that_removes_an_unsupported_figure_is_accepted():
    invented = fact("Net debt totaled EUR 9.9 million.", ["ACME-Q3#2"])
    first = {"recent_developments": [fact(REVENUE, ["ACME-Q3#0", "ACME-Q3#1"])], "company_overview": [invented],
             "meeting_recommendations": QUESTIONS}
    fixed = {**first, "company_overview": [fact(DEBT, ["ACME-Q3#2"])]}
    out, gen = run(first, fixed)
    assert out["coverage"]["first_draft_figures"]["untraced"][0]["figure"] == "9.9"
    assert out["coverage"]["repair"]["accepted"] is True and out["coverage"]["repaired"] is True
    assert "9.9" not in text_of(out) and "312.4" in text_of(out) and "1,569.7" in text_of(out)
    assert out["coverage"]["repair"]["lost_figures"] == []


def test_a_genuine_problem_is_still_fixed_when_the_repair_also_drops_a_figure_and_the_loss_is_recorded():
    invented = fact("Net debt totaled EUR 9.9 million.", ["ACME-Q3#2"])
    first = {"recent_developments": [fact(REVENUE, ["ACME-Q3#0", "ACME-Q3#1"])],
             "company_overview": [invented, fact("Revenue grew 10.1% year-on-year.", ["ACME-Q3#1"])],
             "meeting_recommendations": QUESTIONS}
    fixed_but_shorter = {**first, "company_overview": []}
    out, _ = run(first, fixed_but_shorter)
    repair = out["coverage"]["repair"]
    assert repair["accepted"] is True  # an unsupported figure outweighs a dropped duplicate
    assert repair["fixed_problems"] == 1
    assert "9.9" not in text_of(out)


def test_the_repair_request_asks_to_restate_exactly_and_to_keep_supported_content():
    invented = fact("Net debt totaled EUR 9.9 million.", ["ACME-Q3#2"])
    first = {"recent_developments": [fact(REVENUE, ["ACME-Q3#0", "ACME-Q3#1"])], "company_overview": [invented],
             "meeting_recommendations": QUESTIONS}
    _, gen = run(first, first)
    request = gen.messages[1][-1]["content"]
    assert "'9.9'" in request and "exactly as the cited evidence gives it" in request
    assert "Keep every figure and statement that its evidence supports" in request


def test_a_mismatched_figure_is_sent_back_with_what_differs():
    wrong_currency = fact(REVENUE.replace("EUR 1,569.7", "USD 1,569.7"), ["ACME-Q3#0", "ACME-Q3#1"])
    first = {"recent_developments": [wrong_currency], "meeting_recommendations": QUESTIONS}
    out, gen = run(first, {"recent_developments": [fact(REVENUE, ["ACME-Q3#0", "ACME-Q3#1"])],
                           "meeting_recommendations": QUESTIONS})
    assert [x["attributes"] for x in out["coverage"]["first_draft_figures"]["mismatched"]] == [["currency"]]
    assert "currency" in gen.messages[1][-1]["content"]
    assert out["coverage"]["repaired"] is True and "EUR 1,569.7" in text_of(out)


def test_figure_problems_weigh_more_than_a_lost_topic_or_figure():
    base = {"counts": {"communicated": 3}, "undated": {}, "eligibility": {}}
    assert contract.score({**base, "figures": {"untraced": [{}], "calculated_in_fact": [], "mismatched": []}}) == 1
    assert contract.score({**base, "figures": {"untraced": [], "calculated_in_fact": [], "mismatched": [{}]}}) == 1
    assert contract.score({**base, "figures": {}}) == 3
