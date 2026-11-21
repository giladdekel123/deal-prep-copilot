"""C2.2: the latest material developments. Headline results (profit; revenue, else a moving operating result) with
their direction and stated reason, newer trading updates and guidance changes, and business developments are chosen
from the organization's own dated releases; three is a default, not a quota (essential results are always kept); the
briefing must state each essential figure and its date, also after any repair; reporting periods, currencies and
reported/expected meanings are not mixed (C1's figure check). Invented companies only."""
import json
from datetime import date, timedelta

import pytest

from deal_prep import briefing, company_context as cc, contract
from deal_prep.disclosures import required_disclosures

TODAY = date(2026, 11, 15)


def ago(days):
    return (TODAY - timedelta(days=days)).isoformat()


def st(text, eid="R#1", day=None):
    return {"eid": eid, "doc": eid.split("#")[0], "day": day or ago(10), "text": text}


@pytest.mark.parametrize("text, kind", [
    ("Profit for the period was EUR 2.6 billion, down EUR 3.9 billion, mainly due to impairments on US projects", "result"),
    ("Revenue of EUR 1,569.7 million, up 10.1% year-on-year", "result"),
    ("EBITDA grew by 19 % to EUR 20.2 billion", "result"),
    ("The Group's fuel cost is now expected to be approximately $3.75 billion.", "guidance"),
    ("The Company confirms its full year 2026 guidance.", "guidance"),
    ("Gross investments are expected to amount to EUR 45-50 billion, EUR 5 billion lower than the previous guidance.",
     "guidance"),
    ("The Group continues to experience trading conditions in line with the outlook.", "trading"),
    ("New reporting structure effective July 1st, 2026, comprising four divisions.", "development"),
    ("Net debt totalled EUR 37.7 billion at the end of the period.", "figure"),
    ("International demand remains strong.", ""),
])
def test_statements_are_classified(text, kind):
    assert cc.statement_kind(st(text)) == kind


def test_identity_statements_are_never_developments():
    s = st("Acme is a global leader in valves, with 11.1 GW installed.")
    assert cc.statement_kind(s, [s]) == "identity"


@pytest.mark.parametrize("text, figure", [
    ("For the 2025/26 financial year, the Group recorded a $2.06 billion Underlying Profit Before Tax, down $330 "
     "million", "2.06"),
    ("EBITDA grew by 19 % to EUR 20.2 billion, up from EUR 17.0 billion", "20.2"),
    ("Revenue of EUR 1,569.7 million, up 10.1% year-on-year", "1,569.7"),
    ("The Group has continued to extend hedging and is approximately 85 per cent hedged for FY27.", "85"),
    ("International demand remains strong.", None),
])
def test_the_key_figure_is_the_amount_the_statement_is_about(text, figure):
    assert cc.key_figure(text) == figure


# --- selection ----------------------------------------------------------------------------------------------

def analysis(statements):
    return {"statements": statements, "identity": [], "as_of": TODAY}


def chosen_texts(dev):
    return [s["text"][:20] for s, _ in dev["chosen"]]


def test_headline_profit_and_revenue_are_essential_and_a_duplicate_figure_is_dropped():
    statements = [st("Revenue amounted to EUR 1.2 billion, up 5% year-on-year.", "Q3#1"),
                  st("Net debt totalled EUR 0.3 billion.", "Q3#2"),
                  st("Profit for the period was EUR 140 million, down 12%, mainly due to restructuring costs.", "Q3#3"),
                  st("Profit for the period amounted to EUR 140 million, lower than last year.", "REP#1"),
                  st("Completed the acquisition of Valvex Ltd.", "Q3#4")]
    dev = cc.developments(analysis(statements))
    essential = [s["eid"] for s in dev["essential"]]
    assert essential == ["Q3#3", "Q3#1"]  # profit, then revenue
    assert "REP#1" not in [s["eid"] for s, _ in dev["chosen"]]  # the same figure for the same metric
    assert [s["eid"] for s, _ in dev["chosen"]][2] == "Q3#4"  # a business development fills the default third place


def test_a_newer_trading_update_and_the_latest_full_period_results_are_both_kept():
    statements = [st("For the 2025/26 financial year, the Group recorded a $2.06 billion Underlying Profit Before Tax, "
                     "down $330 million on the previous year.", "AR#1", ago(80)),
                  st("The Group continues to experience trading conditions in line with the outlook.", "TU#1", ago(9)),
                  st("The Group's 1H27 fuel cost is now expected to be approximately $3.75 billion.", "TU#3", ago(9)),
                  st("The Group is approximately 85 per cent hedged for FY27.", "TU#4", ago(9))]
    dev = cc.developments(analysis(statements))
    assert dev["newest_day"] == ago(9) and dev["results_day"] == ago(80)
    assert [s["eid"] for s in dev["essential"]] == ["AR#1", "TU#1", "TU#3"]  # results, the update and its figure


def test_three_is_a_default_and_essential_results_can_exceed_it_but_never_the_maximum():
    statements = [st("Revenue amounted to EUR 1.2 billion, up 5%.", "Q#1"),
                  st("Profit was EUR 140 million, down 12%.", "Q#2")] + \
                 [st(f"Completed the acquisition of Firm {n}.", f"Q#{n + 2}") for n in range(8)]
    dev = cc.developments(analysis(statements))
    assert len(dev["chosen"]) == cc.DEFAULT_DEVELOPMENTS
    many = [st("The Group's revenue amounted to EUR 1.2 billion, up 5%.", "A#1", ago(80)),
            st("Profit was EUR 140 million, down 12%.", "A#2", ago(80)),
            st("Trading is in line with the outlook.", "B#1", ago(5)),
            st("Fuel cost is now expected to be EUR 3.75 billion.", "B#2", ago(5))]
    dev = cc.developments(analysis(many))
    assert len(dev["essential"]) == 4 and len(dev["chosen"]) <= cc.MAX_DEVELOPMENTS


def test_nothing_older_than_the_window_and_nothing_already_required_elsewhere():
    assert cc.developments(analysis([st("Revenue amounted to EUR 1.2 billion.", day=ago(400))])) == {}
    guidance = st("The Company confirms its full year 2026 guidance.", "Q#2")
    dev = cc.developments(analysis([st("Revenue amounted to EUR 1.2 billion.", "Q#1"), guidance]), taken=[guidance])
    assert "Q#2" not in [s["eid"] for s, _ in dev["chosen"]]


# --- through the contract: content-level coverage --------------------------------------------------------------

def doc(doc_id, published, quotes, title="release"):
    label = (f"PUBLIC SOURCE · Acme Corp · https://acme.example/{doc_id.lower()} · published {published} · retrieved "
             f"2026-11-15 · verification primary")
    meta = {"doc_type": "public_profile", "subject_org_id": "acme", "publication_date": published,
            "approval_status": "approved"}
    out = [{"evidence_id": f"{doc_id}#0", "info_origin": "public_source", "document_id": doc_id, "metadata": meta,
            "provenance_label": label,
            "text": f"PUBLIC SOURCE — Acme Corp: {title} - **Publication date:** {published}"}]
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


Q3 = doc("ACME-Q3", ago(10), ["Revenue amounted to EUR 1,569.7 million, up 10.1% year-on-year.",
                              "Profit for the period was EUR 140.2 million, down 12%, mainly due to restructuring.",
                              "Net debt totaled EUR 0.3 billion."], title="interim report, third quarter 2026")
DATE = f"{TODAY.day - 10} November 2026"


def fact(text, ids):
    return {"kind": "fact", "text": text, "evidence_ids": ids, "claim_type": "real_world_fact"}


def topic():
    return {t["id"]: t for t in contract.essential_topics(bundle(Q3))}["company:latest_release"]


def test_the_topic_requires_each_headline_figure_and_the_date():
    t = topic()
    assert t["require_all"] and t["section"] == "recent_developments"
    assert any("1,569.7" in label for label in t["labels"]) and any("140.2" in label for label in t["labels"])
    assert "Never combine figures from different periods or currencies" in t["requirement"]


def test_a_draft_that_keeps_the_release_but_drops_the_headline_result_is_not_counted_as_covering_it():
    cov = contract.coverage
    without_profit = {"sections": {"recent_developments": [fact(
        f"Acme's interim report for the third quarter of 2026, published {DATE}, gives revenue of EUR 1,569.7 million, "
        "up 10.1%.", ["ACME-Q3#0", "ACME-Q3#1"])]}, "disclosures": []}
    full = {"sections": {"recent_developments": [fact(
        f"Acme's interim report for the third quarter of 2026, published {DATE}, gives revenue of EUR 1,569.7 million, "
        "up 10.1%, and profit of EUR 140.2 million, down 12%, mainly due to restructuring.",
        ["ACME-Q3#0", "ACME-Q3#1", "ACME-Q3#2"])]}, "disclosures": []}
    assert cov(without_profit, [topic()])["topics"]["company:latest_release"] == "cited_only"
    assert cov(full, [topic()])["topics"]["company:latest_release"] == "communicated"


def test_essential_results_survive_a_repair():
    b = bundle(Q3)
    questions = [{"kind": "recommendation", "evidence_ids": [], "claim_type": None,
                  "text": "Ask which systems Acme uses today, who decides and how, and on what timing."}]
    full = fact(f"Acme's interim report for the third quarter of 2026, published {DATE}, gives revenue of EUR 1,569.7 "
                "million, up 10.1%, and profit of EUR 140.2 million, down 12%, mainly due to restructuring.",
                ["ACME-Q3#0", "ACME-Q3#1", "ACME-Q3#2"])
    invented = fact("Net debt totaled EUR 9.9 billion.", ["ACME-Q3#3"])

    def as_json(sections):
        d = {"sections": {s: [] for s in briefing.SECTIONS}, "disclosures": []}
        d["sections"].update(sections)
        d["disclosures"] = [{"id": x["id"], "text": x["text"]} for x in required_disclosures(b)]
        d["disclosures"] += [{"id": f"empty_section:{s}", "text": "Nothing supported."}
                             for s, v in d["sections"].items() if not v]
        return json.dumps(d)
    drafts = [{"recent_developments": [full], "company_overview": [invented], "meeting_recommendations": questions},
              {"meeting_recommendations": questions}]  # the repair removes the invented figure AND the results
    calls = []

    def drafter(messages):
        calls.append(messages)
        return as_json(drafts[min(len(calls), 2) - 1])
    out = briefing.draft_briefing(b, drafter, repair_coverage=True)
    assert out["coverage"]["repair"]["accepted"] is False
    assert "company:latest_release" in out["coverage"]["repair"]["reason"]
    assert "1,569.7" in json.dumps(out["draft"])


def test_a_release_without_results_or_updates_still_gives_its_most_material_figures():
    """A company without financial reporting: its newest release (a milestone) is still a development to state."""
    statements = [st("Acme marks 10,000 patients treated across Europe.", "M#1"),
                  st("More than 30,000 patients treated at 226 centers worldwide.", "M#2"),
                  st("Acme is headquartered in Haifa.", "M#3")]
    dev = cc.developments({"statements": statements, "identity": [statements[2]], "as_of": TODAY})
    assert [s["eid"] for s, _ in dev["chosen"]] == ["M#1", "M#2"] and [s["eid"] for s in dev["essential"]] == ["M#1"]


def test_a_historical_statement_without_a_date_is_not_a_dated_development():
    """I4 marks it "date not stated" and never dates it; the latest-developments topic does not date it either."""
    entries = doc("REL", ago(10), ["The Northfield valve plant was commissioned.",
                                   "In October 2026, the Southfield valve plant was commissioned."])
    t = {t["id"]: t for t in contract.essential_topics(bundle(entries))}
    assert "undated:REL#1" in t and "undated:REL#2" not in t
    assert "REL#1" not in t["company:latest_release"]["groups"][0]
    assert "REL#2" in t["company:latest_release"]["groups"][0]
