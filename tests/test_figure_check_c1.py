"""C1: figure verification (deal_prep.figure_verify through business.figure_check).

Correct figures, including thousands-and-decimal figures such as 1,569.7, are verified, never flagged; deliberately
wrong figures are still caught: wrong values, and right values with the wrong currency, scale, unit, metric, period or
reported/expected meaning. An attribute is compared only when both sides state it. All companies here are invented."""
import pytest

from deal_prep import business

HEADER = ("PUBLIC SOURCE — Example Group: third-quarter 2026 revenue - **Source:** Example Group - **Publication "
          "date:** 2026-10-21")
E1 = 'Excerpts > [E1] "Revenue of EUR 1,569.7 million, up 10.1% year-on-year and up 6.2% organically;"'
E2 = ('Excerpts > [E2] "EBITDA grew by 19 % to DKK 20.2 billion, up from DKK 17.0 billion. Profit for the period was '
      'DKK 2.6 billion, down by DKK 3.9 billion, mainly due to non-cash impairments on our US projects."')
E3 = 'Excerpts > [E3] "The Group\'s 1H27 fuel cost is now expected to be approximately $3.75 billion."'
E4 = 'Excerpts > [E4] "Profit for the period was DKK -0.7 billion in Q3 2026."'
E5 = 'Excerpts > [E5] "Installed capacity increased to 11.8 GW. Net debt totalled DKK 37.7 billion."'
PRICE = "List prices Product: Core | Tier: Business | Unit: per user per month | List price (USD): 34"


def bundle():
    def entry(eid, text, doc):
        return {"evidence_id": eid, "info_origin": "public_source", "provenance_label": "PUBLIC SOURCE · published "
                "2026-10-21", "excerpt": text, "text": text, "document_id": doc, "metadata": {}}
    ev = [entry("D1#0", HEADER, "D1"), entry("D1#1", E1, "D1"), entry("D2#2", E2, "D2"), entry("D3#3", E3, "D3"),
          entry("D2#4", E4, "D2"), entry("D2#5", E5, "D2"),
          {**entry("P#1", PRICE, "P"), "info_origin": "synthetic_record"}]
    return {"internal": {"x": {"evidence": ev}}, "created_at": "2026-11-15T10:00:00+00:00"}


def check(text, ids, kind="fact"):
    draft = {"sections": {"recent_developments": [{"kind": kind, "text": text, "evidence_ids": ids}]}}
    return business.figure_check(draft, bundle(), {})


def problems(r):
    return [(x["figure"], tuple(x.get("attributes", ()))) for k in ("untraced", "mismatched", "calculated_in_fact")
            for x in r[k]]


@pytest.mark.parametrize("text, ids", [
    ("In its third-quarter 2026 release, Example Group reported revenue of EUR 1,569.7 million, up 10.1% "
     "year-on-year and 6.2% organically.", ["D1#1"]),
    ("Example Group reported revenue of EUR 1569.7 million.", ["D1#1"]),          # without the separator
    ("Revenue was EUR 1.5697 billion in Q3 2026.", ["D1#1"]),                      # the same amount at another scale
    ("EBITDA grew by 19% to DKK 20.2 billion; profit for the period was DKK 2.6 billion, down DKK 3.9 billion.",
     ["D2#2"]),
    ("Q3 2026 profit for the period was DKK -0.7 billion.", ["D2#4"]),             # a negative value
    ("Q3 2026 profit for the period was DKK −0.7 billion.", ["D2#4"]),             # Unicode minus
    ("The 1H27 fuel cost is expected to be approximately A$3.75 billion.", ["D3#3"]),
    ("Installed capacity is 11.8 GW and net debt DKK 37.7 billion.", ["D2#5"]),
    ("Core Business is listed at USD 34 per user per month.", ["P#1"]),
])
def test_correct_figures_are_verified_not_flagged(text, ids):
    r = check(text, ids)
    assert problems(r) == [] and r["verified"] >= 1


@pytest.mark.parametrize("text, ids, figure", [
    ("Example Group reported revenue of EUR 1,596.7 million.", ["D1#1"], "1,596.7"),   # transposed digits
    ("Example Group reported revenue of EUR 1,569.8 million.", ["D1#1"], "1,569.8"),
    ("EBITDA grew by 19% to DKK 22.0 billion.", ["D2#2"], "22.0"),
    ("Q3 2026 profit for the period was DKK -0.8 billion.", ["D2#4"], "0.8"),
    ("Revenue rose 11.1% year-on-year.", ["D1#1"], "11.1"),
])
def test_wrong_values_are_still_untraced(text, ids, figure):
    r = check(text, ids)
    assert figure in [x["figure"] for x in r["untraced"]]


def test_a_sign_error_is_caught():
    r = check("Q3 2026 profit for the period was DKK 0.7 billion.", ["D2#4"])
    assert "0.7" in [x["figure"] for x in r["untraced"] + r["mismatched"]]


@pytest.mark.parametrize("text, ids, figure, attribute", [
    ("Example Group reported revenue of USD 1,569.7 million.", ["D1#1"], "1,569.7", "currency"),
    ("Example Group reported revenue of EUR 1,569.7 billion.", ["D1#1"], "1,569.7", "scale"),
    ("Example Group reported profit of EUR 1,569.7 million.", ["D1#1"], "1,569.7", "metric"),
    ("Revenue was up 10.1 percentage points.", ["D1#1"], "10.1", "unit"),
    ("Installed capacity increased to 11.8 MW.", ["D2#5"], "11.8", "unit"),
    ("Q3 2025 profit for the period was DKK -0.7 billion.", ["D2#4"], "0.7", "period"),
    ("In Q3 2025, revenue was EUR 1,569.7 million.", ["D1#1"], "1,569.7", "period"),        # the header dates it
    ("The 1H27 fuel cost was $3.75 billion.", ["D3#3"], "3.75", "reported_or_expected"),    # an expectation as a result
    ("Profit for the period is expected to be DKK 2.6 billion.", ["D2#2"], "2.6", "reported_or_expected"),
])
def test_right_values_with_the_wrong_meaning_are_mismatched(text, ids, figure, attribute):
    r = check(text, ids)
    found = {x["figure"]: x["attributes"] for x in r["mismatched"]}
    assert attribute in found.get(figure, []), r


def test_an_attribute_one_side_does_not_state_is_not_a_problem():
    # no currency, no period, no tense in the briefing: nothing to contradict, so the value alone verifies it
    assert problems(check("Revenue: 1,569.7 million.", ["D1#1"])) == []
    # the evidence states no period for EBITDA, and a comparison precedes 17.0: unverified, not mismatched
    assert problems(check("In 9M 2025, EBITDA was DKK 17.0 billion.", ["D2#2"])) == []


def test_us_projects_is_not_forecasting_language():
    r = check("Profit for the period was DKK 2.6 billion, mainly due to impairments on US projects.", ["D2#2"])
    assert problems(r) == []


def test_profit_and_operating_profit_are_not_told_apart():
    assert problems(check("Operating profit was DKK 2.6 billion.", ["D2#2"])) == []


def test_a_figure_cited_from_the_wrong_passage_is_checked_against_all_evidence():
    # the value is in other evidence: traced (as before C1), and checked against that occurrence's meaning
    assert problems(check("Example Group reported revenue of EUR 1,569.7 million.", ["D2#2"])) == []
    r = check("Example Group reported revenue of USD 1,569.7 million.", ["D2#2"])
    assert [x["attributes"] for x in r["mismatched"]] == [["currency"]]


def test_a_calculation_stated_as_a_fact_is_still_found():
    draft = {"sections": {"our_relationship": [
        {"kind": "fact", "text": "The discount is 10.0%.", "evidence_ids": ["P#1"]},
        {"kind": "inference", "text": "The discount is 10.0%.", "evidence_ids": ["P#1"]}]}}
    r = business.figure_check(draft, bundle(), {"price_positions": [{"discount_pct": 10.0}]})
    assert [x["item"] for x in r["calculated_in_fact"]] == [0] and r["untraced"] == []


def test_an_ambiguous_figure_is_reported_not_silently_normalized():
    b = bundle()
    b["internal"]["x"]["evidence"].append({"evidence_id": "D9#1", "info_origin": "public_source",
                                           "provenance_label": "PUBLIC SOURCE", "excerpt": "an index value of 7,200",
                                           "text": "an index value of 7,200", "document_id": "D9", "metadata": {}})
    draft = {"sections": {"company_overview": [{"kind": "fact", "text": "Its index value is 7200.",
                                                "evidence_ids": ["D9#1"]}]}}
    r = business.figure_check(draft, b, {})
    assert r["untraced"] == [] and [x["figure"] for x in r["ambiguous"]] == ["7200"]
