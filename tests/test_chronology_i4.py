"""Phase 4.5 I4: derived conflicts, chronology, undated history and event dates (offline, simulated evidence)."""
import pytest

from deal_prep import chronology, evidence_profile


def pub(eid, quote, doc=None, verification="primary", url="https://acme.example/about", published="2026-02-15"):
    return {"evidence_id": eid, "document_id": doc or eid.split("#")[0], "info_origin": "public_source",
            "source": "internal:company_profile", "excerpt": f'Excerpts > [E1] "{quote}"', "time_window": None,
            "provenance_label": f"PUBLIC SOURCE · Acme · {url} · published {published} · retrieved 2026-11-02 · "
                                f"verification {verification}"}


def news(eid, text):
    return {"evidence_id": eid, "document_id": None, "info_origin": "public_source", "source": "external_news",
            "excerpt": text, "time_window": "last_30_days",
            "provenance_label": "PUBLIC SOURCE · news.example · https://news.example/a · published "
                                "2026-10-25T09:00:00+00:00 · retrieved 2026-11-09 · window last 30 days"}


DECISION = pub("P-1#2", "In 2022 our board decided to keep all quality certificates in a single digital archive.")
EARLIER = pub("P-1#3", "Since 2020 every quality certificate has been stored in our digital archive.")
LATER = pub("P-1#4", "Since 2023 every quality certificate has been stored in our digital archive.")


def test_a_state_earlier_than_its_decision_is_a_chronological_ambiguity_not_a_contradiction():
    (c,) = chronology.derived_conflicts([DECISION, EARLIER])
    assert c["kind"] == "chronological_ambiguity" and {s["evidence_id"] for s in c["sides"]} == {"P-1#2", "P-1#3"}
    d = chronology.disclosure(c)
    assert d["kind"] == "chronological_ambiguity" and d["evidence_ids"] == ["P-1#2", "P-1#3"]
    assert "Both can be true" in d["text"] and "contradict" not in d["text"].casefold()
    assert '"In 2022 our board decided' in d["text"] and '"Since 2020 every quality certificate' in d["text"]


@pytest.mark.parametrize("state", [LATER, pub("P-1#5", "Since 2022 every quality certificate has been stored in "
                                                       "our digital archive.")])
def test_a_state_from_the_decision_year_or_later_is_compatible_and_not_disclosed(state):
    assert chronology.derived_conflicts([DECISION, state]) == []


def test_unrelated_subjects_are_never_paired():
    other = pub("P-1#6", "Since 2019 every delivery truck has used electric charging.")
    assert chronology.derived_conflicts([DECISION, other]) == []


def test_generic_phrasing_is_recognised_not_only_the_benchmark_sentences():
    decision = pub("Q-1#1", "The board decided in 2021 to move all supplier contracts to one register.")
    state = pub("Q-1#2", "All supplier contracts have been kept in that register since 2019.")
    (c,) = chronology.derived_conflicts([decision, state])
    assert c["kind"] == "chronological_ambiguity" and (c["state_year"], c["decision_year"]) == (2019, 2021)


def test_different_figures_for_the_same_statement_are_a_contradiction():
    a = pub("A-1#1", "At the end of 2025, Acme operated 4 factories.")
    b = pub("B-1#1", "At the end of 2025, Acme operated 5 factories.", verification="single_secondary",
            url="https://index.example/acme", published="unknown")
    (c,) = chronology.derived_conflicts([a, b], "acme.example")
    assert c["kind"] == "unresolved_conflict" and c["sides"][0]["evidence_id"] == "A-1#1"  # official side first
    assert "different figures" in chronology.disclosure(c)["text"]


def test_a_copy_with_the_same_figure_is_not_a_conflict():
    a = pub("A-1#1", "At the end of 2025, Acme operated 4 factories.")
    b = pub("B-1#1", "At the end of 2025, Acme operated 4 factories.", verification="single_secondary",
            url="https://index.example/acme")
    assert chronology.derived_conflicts([a, b], "acme.example") == []


@pytest.mark.parametrize("quote, undated", [
    ("Acme began as a municipal utility.", True),
    ("The company's shares were sold to a group of investors.", True),
    ("The firm was created by the merger of two practices.", True),
    ("Acme was founded in 1998 by two engineers.", False),     # dated
    ("At the end of 2025, Acme operated 4 factories.", False),  # dated, not history
    ("Acme may expand its network.", False),                    # 'may' is not a month, and not a past event
])
def test_undated_history_is_marked_only_when_no_date_is_given(quote, undated):
    assert chronology.undated_history(pub("U-1#4", quote)) is undated


def test_news_event_dates_come_from_the_text_not_the_publication_date():
    e = news("WEB-1", "Acme opened two outpatient clinics in October 2026, the network said.")
    assert chronology.event_dates(e) == ["October 2026"]
    assert chronology.event_dates(news("WEB-2", "Acme connected a new wind farm to the grid.")) == []
    prof = evidence_profile.profile([e])["WEB-1"]
    assert prof["event_dates_in_text"] == ["October 2026"]
    assert prof["date_status"] == "publication_date_provider_estimate"  # still only the provider's estimate


def test_profile_links_the_two_sides_of_an_ambiguity():
    prof = evidence_profile.profile([DECISION, EARLIER])
    assert prof["P-1#2"]["ambiguous_with"] == ["P-1#3"] and prof["P-1#3"]["ambiguous_with"] == ["P-1#2"]


def test_switching_i4_off_restores_the_i31_behaviour(monkeypatch):
    monkeypatch.setattr(chronology, "ENABLED", False)
    assert chronology.derived_conflicts([DECISION, EARLIER]) == []
    prof = evidence_profile.profile([DECISION, EARLIER])["P-1#2"]
    assert set(prof) == {"source_class", "statement_form", "date_status", "contested_with", "restates"}


# --- citation rule (simulated bundle on the development scenario P2) -------------------------------------

def test_a_fact_may_not_drop_one_side_of_a_derived_conflict():
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
    import benchmark_harness as h
    from deal_prep.citations import validate_citations

    dev = h.compile_split("dev")
    scenario = next(sc for c in dev for sc in c["scenarios"] if sc["id"] == "DEV-P2")
    captured = {}

    def keep_bundle(bundle, generate, repair_coverage=False):  # capture the bundle the drafter would see
        captured["bundle"] = bundle
        return {"status": "no_briefing", "draft": None, "model_calls": 0, "error": "captured"}
    from deal_prep import pipeline
    original = pipeline.draft_briefing
    pipeline.draft_briefing = keep_bundle
    try:
        h.run_scenario(scenario, dev, h.RUNS / "pytest" / "i4" / "P2", "news_fixture")
    finally:
        pipeline.draft_briefing = original
    bundle = captured["bundle"]
    from deal_prep.disclosures import required_disclosures
    ids = {d["id"]: d for d in required_disclosures(bundle)}
    chron = next(d for d in ids.values() if d["kind"] == "chronological_ambiguity")
    figures = next(d for d in ids.values() if d["id"].startswith("conflict:derived:figures"))
    one_side = chron["evidence_ids"][:1]

    def draft(evidence_ids, kind="fact"):
        return {"sections": {"company_overview": [{"kind": kind, "text": "x", "evidence_ids": evidence_ids,
                                                   "claim_type": "real_world_fact" if kind == "fact" else None}],
                             **{s: [] for s in ("recent_developments", "our_relationship", "opportunities",
                                                "competitive_positioning", "meeting_recommendations")}},
                "disclosures": [{"id": i, "text": "ack"} for i in ids]
                + [{"id": f"empty_section:{s}", "text": "-"} for s in ("recent_developments", "our_relationship",
                                                                       "opportunities", "competitive_positioning",
                                                                       "meeting_recommendations")]}
    codes = lambda d: [x["code"] for x in validate_citations(d, bundle)["issues"]]  # noqa: E731
    assert "conflict_side_dropped" in codes(draft(one_side))
    assert "conflict_side_dropped" not in codes(draft(chron["evidence_ids"]))
    assert "conflict_side_dropped" not in codes(draft(one_side, kind="inference"))
    assert "conflict_side_dropped" in codes(draft(figures["evidence_ids"][:1]))
    assert "missing_disclosure" in codes({**draft(chron["evidence_ids"]), "disclosures": []})
