"""I7.1 (owner-approved 2026-11-16): compatibility findings reach the drafter, and conflict claims the evidence does not
support cannot reach the final briefing. General rules on simulated evidence ("Acme Corp", fictional, offline).

Groups: compatible quantities (bounds, approximations, periods, dates) across wording and within one document; what is
not comparable (unit, metric, scope, organization, currency); genuine contradictions still contested; the profile the
model receives; the output safeguard (established, compatible, unverified and possible-difference claims); the retry
and the last resort; what is not a conflict claim; preservation of evidence and disclosures; the prompt; I7.1 off."""
import json
from datetime import date, timedelta

import pytest

from deal_prep import briefing, conflict_guard as g, evidence_profile as ep
from deal_prep.citations import validate_citations
from deal_prep.disclosures import required_disclosures
from deal_prep.evidence import evidence_index, model_evidence

DOMAIN = "acme.example"
TODAY = date(2026, 11, 15)
CREATED = "2026-11-15T10:00:00+00:00"


def ago(days):
    return (TODAY - timedelta(days=days)).isoformat()


def doc(doc_id, published, quotes, url=None, verification="primary"):
    url = url or f"https://{DOMAIN}/{doc_id.lower()}"
    lab = (f"PUBLIC SOURCE · Acme Corp · {url} · published {published} · retrieved 2026-11-15 · "
           f"verification {verification}")
    meta = {"doc_type": "public_profile", "subject_org_id": "acme", "publication_date": published}
    return [{"evidence_id": f"{doc_id}#{n}", "info_origin": "public_source", "document_id": doc_id,
             "provenance_label": lab, "metadata": dict(meta), "text": f'Excerpts > [E{n}] "{q}"'}
            for n, q in enumerate(quotes, 1)]


def bundle(entries, purpose="general"):
    return {"purpose": purpose, "created_at": CREATED, "status": "complete", "company_input": "Acme Corp",
            "identity": {"name": "Acme Corp", "org_id": "acme", "domain": DOMAIN, "country": None, "confidence": 1.0},
            "internal": {"company_profile": {"sections": ["company_overview"], "evidence": list(entries)},
                         "relationship_history": {"sections": ["our_relationship"], "evidence": [
                             {"evidence_id": "REC-1#1", "info_origin": "synthetic_record", "document_id": "REC-1",
                              "provenance_label": "SYNTHETIC — not a real business fact", "text": "Meeting record",
                              "metadata": {"customer_org_id": "acme", "approval_status": "approved"}}]}},
            "external": {"status": "found_48h", "evidence": []}, "selection": {}, "gaps": []}


def rel(entries):
    return g.relations(list(evidence_index(bundle(entries)).values()), DOMAIN)


def basis(r, a, b, kind="compatible_with"):
    return r.get(a, {}).get(kind, {}).get(b)


def q(sentence):
    return g.quantities(sentence)


def item(kind, text, ids, claim=None):
    return {"kind": kind, "text": text, "evidence_ids": ids,
            "claim_type": claim or ("real_world_fact" if kind == "fact" else None)}


def valid_draft(b, **sections):
    d = {"sections": {s: [] for s in briefing.SECTIONS}, "disclosures": []}
    d["sections"].update(sections)
    d["sections"].setdefault("our_relationship", [])
    if not d["sections"]["our_relationship"]:
        d["sections"]["our_relationship"] = [item("fact", "Synthetic demonstration record: a meeting took place.",
                                                  ["REC-1#1"], "relationship")]
    d["disclosures"] = [{"id": x["id"], "text": x["text"]} for x in required_disclosures(b)]
    d["disclosures"] += [{"id": f"empty_section:{s}", "text": "Nothing supported."} for s, v in d["sections"].items()
                         if not v]
    return d


def guard_codes(b, d):
    return [x["code"] for x in validate_citations(d, b)["issues"] if x["code"] in g.GUARD_CODES]


# The defect's shape, as general simulated evidence: one release gives an exact count in its body and a lower bound
# ("X+") in its boilerplate, worded differently.
RELEASE = doc("ACME-REL", ago(60), ["more than 30,000 customers served at 226 service centres worldwide",
                                    "To date, more than 30,000 customers have been served with Acme's systems at 214+ "
                                    "service centers worldwide."])


# --- 1. compatible quantities -----------------------------------------------------------------------------------------

def test_a_value_that_satisfies_a_lower_bound_is_compatible_across_wording_and_within_one_document():
    r = rel(RELEASE)
    assert "226 satisfies the lower bound 214+" in basis(r, "ACME-REL#1", "ACME-REL#2")
    assert basis(r, "ACME-REL#2", "ACME-REL#1") and not r["ACME-REL#1"]["differs_from"]


def cls(one, other, period="none", days="same"):
    a, b = q(one)[0], q(other)[0]
    res = g.classify(a, b, period, days)
    return res[0] if res else None


@pytest.mark.parametrize("bound,value,expected", [  # bounds are logical: their result does not depend on dates
    ("at least 200 stores", "215 stores", "compatible"), ("200+ stores", "200 stores", "compatible"),
    ("more than 200 stores", "200 stores", "differs"), ("over 200 stores", "180 stores", "differs"),
    ("up to 50 stores", "48 stores", "compatible"), ("fewer than 50 stores", "50 stores", "differs"),
    ("more than 200 stores", "more than 150 stores", "compatible"), ("at least 40 stores", "up to 60 stores",
                                                                      "compatible"),
    ("at least 70 stores", "up to 60 stores", "differs")])
def test_bounds_are_logical(bound, value, expected):
    assert cls(f"Acme operates {bound}.", f"Acme operates {value}.") == expected


@pytest.mark.parametrize("approx,value,expected", [  # an inferred tolerance is heuristic: at best "uncertain"
    ("about 4,250 employees", "4,600 employees", "differs"),  # written to the nearest 50: ±25
    ("about 4,250 employees", "4,260 employees", "uncertain"),
    ("about 4,000 employees", "4,350 employees", "uncertain"),  # written to the nearest 1,000: ±500, capped at 10%
    ("about 4,000 employees", "5,000 employees", "differs"),
    ("nearly 4,000 employees", "4,100 employees", "differs"),  # "nearly X" lies just under X
    ("nearly 4,000 employees", "3,900 employees", "uncertain"),
    ("almost 500 employees", "540 employees", "differs"),
    ("just over 500 employees", "480 employees", "differs"),  # "just over X" lies just over X
    ("just over 500 employees", "520 employees", "uncertain"),
    ("approximately 4.2 billion units", "4.5 billion units", "differs"),  # ±0.05 billion
    ("approximately 4.2 billion units", "4.23 billion units", "uncertain"),
    ("about 30,000 employees", "33,400 employees", "differs"),  # the 10% cap
    ("about 4,000 employees", "about 4,300 employees", "uncertain")])  # two approximations: their intervals overlap
def test_approximations_are_precision_and_qualifier_aware_and_never_logical(approx, value, expected):
    assert cls(f"Acme has {approx}.", f"Acme has {value}.") == expected


@pytest.mark.parametrize("one,other,expected", [  # rates: absolute points at the precision written
    ("Revenue grew roughly 12 percent.", "Revenue grew 13 percent.", "differs"),
    ("Revenue grew about 2 percent.", "Revenue grew 2.2 percent.", "uncertain"),
    ("Revenue grew 12 percent.", "Revenue grew 13 percent.", "differs")])
def test_percentages_compare_in_points(one, other, expected):
    assert cls(one, other) == expected


def test_percent_and_percentage_points_are_not_compared():
    assert cls("The margin rose 2 percentage points.", "The margin rose 3 percent.") is None


def test_dates_never_prove_compatibility_and_the_same_stated_period_is_judged_on_its_values():
    plants_4, plants_5 = "At the end of 2025, Acme operated 4 plants.", "Acme had 5 plants at the end of 2025."
    assert cls(plants_4, plants_5, "same", "different") == "differs"  # whatever the publication dates
    assert cls(plants_4, plants_5, "same", "same") == "differs"
    assert cls("At the end of 2025, Acme operated more than 3 plants.", plants_5, "same", "different") == "compatible"
    assert cls(plants_4, plants_5, "different", "same") == "compatible"  # explicitly different periods
    assert cls(plants_4, plants_5, "ambiguous", "different") == "uncertain"  # a period on one side only
    assert cls("Acme operates 4 plants.", "Acme has 5 plants.", "none", "different") == "uncertain"
    assert cls("Acme operates 4 plants.", "Acme has 5 plants.", "none", "same") == "differs"
    assert cls("Acme operates 4 plants.", "Acme has 5 plants.", "none", "unknown") == "differs"
    assert [g.period_relation(*p) for p in ((["2025"], ["2025"]), (["2024"], ["2025"]), ([], []), (["2025"], []),
                                            (["2024", "2025"], ["2025"]))] == \
        ["same", "different", "none", "ambiguous", "ambiguous"]


def test_a_later_forecast_for_the_same_period_is_a_presumed_update_but_two_forecasts_of_one_day_differ():
    august = "Full year 2026 guidance: adjusted EBIT of USD 700 million."
    october = "Acme now expects adjusted EBIT of USD 1.4 billion for the full year 2026."
    assert cls(august, october, "same", "different") == "uncertain"  # an update: neither proven nor a contradiction
    assert cls(august, october, "same", "same") == "differs"  # different guidance published the same day
    actual = "Acme reported adjusted EBIT of USD 900 million for the full year 2026."
    assert cls(actual, "Acme reported adjusted EBIT of USD 950 million for the full year 2026.", "same", "different") \
        == "differs"  # reported figures for one period are not updated by later dates


def test_identical_approximate_figures_are_the_same_figure():
    assert cls("The contract is worth about SEK 8.9 billion.", "The contract is worth about SEK 8.9 billion.") is None


def test_differently_worded_statements_of_the_same_period_are_compared_across_publication_dates():
    official = doc("ACME-P", ago(270), ["At the end of 2025, Acme operated 4 plants."])
    directory = doc("DIR-P", ago(165), ["Acme had 5 plants at the end of 2025."], url="https://directory.example/acme",
                    verification="single_secondary")
    r = rel(official + directory)
    assert "the same stated period" in basis(r, "ACME-P#1", "DIR-P#1", "differs_from")
    assert basis(r, "ACME-P#1", "DIR-P#1") is None and basis(r, "ACME-P#1", "DIR-P#1", "uncertain_with") is None


def test_different_publication_dates_without_periods_are_uncertain_but_the_same_or_an_unknown_day_differs():
    a = doc("ACME-A", ago(200), ["Acme operates 180 stores."])
    b = doc("ACME-B", ago(10), ["Acme runs 210 stores across its network."])
    same = doc("ACME-C", ago(10), ["Acme now has 205 stores."])  # other wording: the frame rule cannot compare
    undated = doc("DIR-D", "unknown", ["Acme operates 190 stores."], url="https://directory.example/acme",
                  verification="single_secondary")
    r = rel(a + b + same + undated)
    assert "presumption" in basis(r, "ACME-A#1", "ACME-B#1", "uncertain_with")
    assert basis(r, "ACME-A#1", "ACME-B#1") is None  # never logically compatible on dates alone
    assert basis(r, "ACME-B#1", "ACME-C#1", "differs_from")  # the same day, different values: to be verified
    assert basis(r, "ACME-B#1", "DIR-D#1", "differs_from")  # an undated page is never assumed to be another moment
    assert basis(r, "ACME-A#1", "DIR-D#1") is None  # same wording, dated vs undated: contested by figure_relations
    entries = list(evidence_index(bundle(a + undated)).values())
    assert ep.profile(entries, DOMAIN, as_of=TODAY)["ACME-A#1"]["contested_with"] == ["DIR-D#1"]
    years = doc("ACME-Y", ago(30), ["In 2024 Acme operated 160 stores and in 2025 it operated 175 stores."])
    assert not rel(years)  # one statement: no pair; the stated years are periods, not quantities
    assert [x["value"] for x in q("Founded in 1887, Acme opened 12 stores on 8 September 2026.")] == [12.0]


# --- 2. what is not comparable --------------------------------------------------------------------------------------

@pytest.mark.parametrize("one,other", [
    ("Acme operates 4 plants.", "Acme operates 9 offices."),  # different things counted
    ("Acme operates 62 service centers in the EMEA region.", "Acme operates 226 service centers worldwide."),  # scope
    ("At the end of 2025, Acme operated 4 plants.", "At the end of 2025, Acme Labs operated 9 plants."),  # organization
    ("Revenue increased 12 percent.", "Operating income increased 52 percent."),  # a measurement of another metric
    ("Carried volume was 922 thousand TEUs.", "Total capacity was 707 thousand TEUs."),
    ("The fund holds EUR 5 million.", "The fund holds USD 7 million.")])  # currency
def test_different_things_scopes_organizations_metrics_or_currencies_are_not_compared(one, other):
    assert not rel(doc("ACME-1", ago(10), [one]) + doc("ACME-2", ago(10), [other]))


# --- 3. genuine contradictions ----------------------------------------------------------------------------------------

def test_a_genuine_contradiction_is_still_contested_and_never_called_compatible():
    official = doc("ACME-P", ago(30), ["At the end of 2025, Acme operated 4 plants."])
    directory = doc("DIR-P", ago(20), ["At the end of 2025, Acme operated 5 plants."],
                    url="https://directory.example/acme", verification="single_secondary")
    entries = list(evidence_index(bundle(official + directory)).values())
    prof = ep.profile(entries, DOMAIN, as_of=TODAY)
    assert prof["ACME-P#1"]["contested_with"] == ["DIR-P#1"]
    assert prof["ACME-P#1"]["compatible_with"] == prof["ACME-P#1"]["uncertain_with"] == \
        prof["ACME-P#1"]["differs_from"] == []


def test_identically_worded_updates_found_by_the_older_detector_stay_uncertain_not_logical():
    q2 = doc("ACME-Q2", ago(120), ["Revenue amounted to EUR 1.1 billion (1.0)."])
    q3 = doc("ACME-Q3", ago(10), ["Revenue amounted to EUR 1.2 billion (1.1)."])
    r = rel(q2 + q3)
    assert "presumption" in basis(r, "ACME-Q2#1", "ACME-Q3#1", "uncertain_with")  # figure_relations: dates
    y24 = doc("ACME-Y24", ago(300), ["In 2024 Acme revenue was EUR 5 million."])
    y25 = doc("ACME-Y25", ago(30), ["In 2025 Acme revenue was EUR 6 million."])
    assert "different reporting periods" in basis(rel(y24 + y25), "ACME-Y24#1", "ACME-Y25#1")  # logical


# --- 4. what the model receives -----------------------------------------------------------------------------------

def test_the_model_receives_the_compatibility_and_its_basis():
    prof = {e["evidence_id"]: e["profile"] for e in model_evidence(bundle(RELEASE))}
    [x] = prof["ACME-REL#1"]["compatible_with"]
    assert x["evidence_id"] == "ACME-REL#2" and "satisfies the lower bound" in x["basis"]
    rules = briefing.system_rules()
    assert "profile.compatible_with lists statements that logically fit together" in rules
    assert "profile.uncertain_with lists statements the code cannot judge" in rules
    assert "call them neither conflicting nor consistent" in rules
    assert "\"more than X\" or \"X+\"" in rules and "never as an established conflict" in rules
    assert "When two statements about the same subject do not fit together" not in rules


# --- 5. the output safeguard ------------------------------------------------------------------------------------------

def test_a_compatible_pair_called_unresolved_fails_validation():
    b = bundle(RELEASE)
    d = valid_draft(b, company_overview=[item("inference", "The release gives 226 service centres in one passage and "
                                                           "214+ in another; their relationship is unresolved.",
                                              ["ACME-REL#1", "ACME-REL#2"])])
    assert guard_codes(b, d) == ["unsupported_conflict"]
    d["sections"]["company_overview"][0]["text"] = ("The release gives 226 service centres worldwide; its boilerplate "
                                                    "says 214+.")
    assert guard_codes(b, d) == []  # both figures may be stated: only the false conflict is refused


def test_an_established_conflict_may_be_reported():
    official = doc("ACME-P", ago(30), ["At the end of 2025, Acme operated 4 plants."])
    directory = doc("DIR-P", ago(20), ["At the end of 2025, Acme operated 5 plants."],
                    url="https://directory.example/acme", verification="single_secondary")
    b = bundle(official + directory)
    d = valid_draft(b, company_overview=[item("fact", "Acme says it operated 4 plants at the end of 2025; a directory "
                                                      "says 5. The figure is unresolved.", ["ACME-P#1", "DIR-P#1"])])
    assert guard_codes(b, d) == []


def test_a_disagreement_no_check_establishes_may_only_be_stated_as_to_be_verified():
    one = doc("ACME-1", ago(10), ["Acme employs 3,200 people."])
    other = doc("DIR-1", ago(10), ["Acme has 4,100 staff members."], url="https://directory.example/acme",
                verification="single_secondary")  # the detector does not compare these (different wording)
    b = bundle(one + other)
    fact = item("fact", "The sources conflict on headcount: 3,200 people or 4,100 staff.", ["ACME-1#1", "DIR-1#1"])
    assert guard_codes(b, valid_draft(b, company_overview=[fact])) == ["unverified_conflict"]
    doubt = item("inference", "The sources may give inconsistent headcounts (3,200 people; 4,100 staff members); "
                              "verify which is current.", ["ACME-1#1", "DIR-1#1"])
    assert guard_codes(b, valid_draft(b, company_overview=[doubt])) == []  # a missed conflict can still be disclosed


def test_a_possible_difference_found_by_the_code_is_disclosed_as_uncertainty_not_as_established():
    a = doc("ACME-B", ago(10), ["Acme runs 210 stores across its network."])
    c = doc("ACME-C", ago(10), ["Acme now has 205 stores."])  # other wording: only the quantity check compares them
    b = bundle(a + c)
    assert basis(rel(a + c), "ACME-B#1", "ACME-C#1", "differs_from")
    same_words = doc("ACME-D", ago(10), ["Acme runs 205 stores across its network."])
    prof = ep.profile(list(evidence_index(bundle(a + same_words)).values()), DOMAIN, as_of=TODAY)
    assert prof["ACME-B#1"]["contested_with"] == ["ACME-D#1"]  # identical wording, same day: a genuine contradiction
    est = item("fact", "Acme's two releases conflict: 210 or 205 stores.", ["ACME-B#1", "ACME-C#1"])
    assert guard_codes(b, valid_draft(b, company_overview=[est])) == ["unverified_conflict"]
    doubt = item("inference", "Two releases of the same day give 210 and 205 stores; this discrepancy should be "
                              "checked.", ["ACME-B#1", "ACME-C#1"])
    assert guard_codes(b, valid_draft(b, company_overview=[doubt])) == []


def test_questions_records_and_single_sources_are_not_conflict_claims():
    b = bundle(RELEASE)
    question = item("recommendation", "Ask whether the 226 and 214+ figures are inconsistent or simply of different "
                                      "dates.", ["ACME-REL#1", "ACME-REL#2"])
    task = item("fact", "Synthetic demonstration record: one task is unresolved.", ["REC-1#1"], "relationship")
    single = item("inference", "The release's boilerplate figure is unresolved.", ["ACME-REL#2"])
    d = valid_draft(b, meeting_recommendations=[question], our_relationship=[task], company_overview=[single])
    assert guard_codes(b, d) == []


# --- 6. the retry and the last resort -----------------------------------------------------------------------------

FALSE = "The release gives 226 service centres in one passage and 214+ in another; their relationship is unresolved."
FIXED = "The release gives 226 service centres worldwide; its boilerplate says 214+."


class Drafter:
    """Simulated drafter: returns the given overview texts in turn, acknowledging every required disclosure."""

    def __init__(self, *texts, kind="inference", ids=("ACME-REL#1", "ACME-REL#2")):
        self.texts, self.kind, self.ids, self.calls = list(texts), kind, list(ids), 0

    def __call__(self, messages):
        self.calls += 1
        payload = json.loads(messages[1]["content"])
        text = self.texts[min(self.calls, len(self.texts)) - 1]
        sections = {s: [] for s in briefing.SECTIONS}
        sections["company_overview"] = [item(self.kind, text, self.ids),
                                        item("fact", "Acme served more than 30,000 customers.", self.ids[:1])]
        sections["our_relationship"] = [item("fact", "Synthetic demonstration record: a meeting took place.",
                                             ["REC-1#1"], "relationship")]
        disclosures = [{"id": x["id"], "text": x["text"]} for x in payload["required_disclosures"]]
        disclosures += [{"id": f"empty_section:{s}", "text": "Nothing supported."} for s, v in sections.items()
                        if not v]
        return json.dumps({"sections": sections, "disclosures": disclosures})


def test_the_retry_corrects_a_false_conflict():
    gen = Drafter(FALSE, FIXED)
    out = briefing.draft_briefing(bundle(RELEASE), gen)
    assert out["status"] == "ok" and gen.calls == 2 and out["retried"]
    assert out["draft"]["sections"]["company_overview"][0]["text"] == FIXED
    assert [x["code"] for x in out["conflict_guard"]["issues_seen"]] == ["unsupported_conflict"]
    assert out["conflict_guard"]["actions"] == []


def test_the_last_resort_removes_a_persisting_false_conflict_and_keeps_everything_else():
    b = bundle(RELEASE)
    before = json.dumps(evidence_index(b), sort_keys=True)
    out = briefing.draft_briefing(b, Drafter(FALSE, FALSE))
    texts = [i["text"] for i in out["draft"]["sections"]["company_overview"]]
    assert out["status"] == "ok" and FALSE not in texts and "Acme served more than 30,000 customers." in texts
    [action] = out["conflict_guard"]["actions"]
    assert action["action"] == "removed" and action["text"] == FALSE
    assert out["disclosures"] == required_disclosures(b)  # disclosures and evidence are untouched
    assert json.dumps(evidence_index(b), sort_keys=True) == before


STORES = doc("ACME-A", ago(200), ["Acme operates 180 stores."]) + \
    doc("ACME-B", ago(10), ["Acme runs 210 stores across its network."])  # no period, different dates: uncertain
HEADCOUNT = doc("ACME-H", ago(10), ["Acme has about 4,000 employees.", "Acme employs 4,300 employees."])  # heuristic


@pytest.mark.parametrize("entries,ids", [(STORES, ["ACME-A#1", "ACME-B#1"]), (HEADCOUNT, ["ACME-H#1", "ACME-H#2"])])
def test_a_conflict_claim_resting_on_dates_or_an_approximation_is_verified_never_refused(entries, ids):
    b = bundle(entries)
    firm = item("fact", "The sources conflict on this figure.", ids)
    issues = [x for x in validate_citations(valid_draft(b, company_overview=[firm]), b)["issues"]
              if x["code"] in g.GUARD_CODES]
    assert [x["code"] for x in issues] == ["unverified_conflict"] and "the code found" in issues[0]["message"]
    doubt = item("inference", "The figures may be inconsistent; verify which applies.", ids)
    assert guard_codes(b, valid_draft(b, company_overview=[doubt])) == []  # an uncertainty disclosure is kept


@pytest.mark.parametrize("entries,ids", [(STORES, ["ACME-A#1", "ACME-B#1"]), (HEADCOUNT, ["ACME-H#1", "ACME-H#2"])])
def test_the_last_resort_marks_but_never_removes_a_claim_resting_on_dates_or_an_approximation(entries, ids):
    claim = "The sources conflict on this figure."
    out = briefing.draft_briefing(bundle(entries), Drafter(claim, claim, kind="fact", ids=ids))
    first = out["draft"]["sections"]["company_overview"][0]
    assert out["status"] == "ok" and first["text"].endswith(g.VERIFY_NOTE)
    assert [a["action"] for a in out["conflict_guard"]["actions"]] == ["marked_for_verification"]


def test_money_needs_the_same_metric_currency_and_scale():
    assert cls("Revenue was about USD 2 billion.", "Revenue was USD 2.19 billion.") == "uncertain"
    assert cls("Revenue was about USD 2 billion.", "Revenue was USD 2.5 billion.") == "differs"
    assert cls("Revenue was USD 2 billion.", "Revenue was EUR 2 billion.") is None
    assert cls("Revenue was USD 2 billion.", "Operating profit was USD 2.5 billion.") is None


def test_the_last_resort_marks_a_persisting_unverified_conflict_for_verification():
    one = doc("ACME-REL", ago(10), ["Acme employs 3,200 people.", "Acme has 4,100 staff members."])
    claim = "The two passages conflict on headcount."
    out = briefing.draft_briefing(bundle(one), Drafter(claim, claim, kind="fact"))
    first = out["draft"]["sections"]["company_overview"][0]
    assert out["status"] == "ok" and first["kind"] == "inference" and first["text"].endswith(g.VERIFY_NOTE)
    assert out["conflict_guard"]["actions"][0]["action"] == "marked_for_verification"


def test_other_validation_failures_still_fail_and_are_never_neutralized():
    b = bundle(RELEASE)
    d = valid_draft(b, company_overview=[item("inference", FALSE, ["ACME-REL#1", "ACME-REL#2"]),
                                         item("fact", "An invented fact.", ["NOT-A-SOURCE#1"])])
    codes = {x["code"] for x in validate_citations(d, b)["issues"]}
    assert {"unsupported_conflict", "nonexistent_citation"} <= codes  # the briefing would fail, as before


# --- 7. I7.1 off ------------------------------------------------------------------------------------------------------

def test_with_i71_off_nothing_changes(monkeypatch):
    monkeypatch.setattr(g, "ENABLED", False)
    b = bundle(RELEASE)
    d = valid_draft(b, company_overview=[item("inference", FALSE, ["ACME-REL#1", "ACME-REL#2"])])
    assert validate_citations(d, b)["valid"]
    assert "compatible_with" not in json.dumps(model_evidence(b))
    assert "When two statements about the same subject do not fit together" in briefing.system_rules()
