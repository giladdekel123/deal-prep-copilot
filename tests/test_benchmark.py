"""Phase 4.5 I0-a: benchmark harness and scorer.

- The scorer is checked against hand-built records whose correct result is known in advance.
- The benchmark is isolated: held-out split refused, indexes outside runs/benchmark_v1 refused, protected local
  data unchanged, no connections, and production safety rules unchanged outside the benchmark process.
- Every benchmark source is labelled fictional; no benchmark name or domain appears in production code.
"""
import copy
import json
import shutil
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import benchmark_harness as h  # noqa: E402
import benchmark_score as s  # noqa: E402
import benchmark_spec as spec  # noqa: E402

DEV = ROOT / "eval" / "benchmark_v1" / "dev"


# --- scorer against hand-built examples ------------------------------------------------------------

PRODUCTS, COMPETITORS = ["Nivarque Core", "Engineering Vault"], ["Rivalco"]
EXPECTED = {
    "must_reach_drafter": [["P#1"], ["NEWS:fresh"]], "must_not_reach_drafter": ["NEWS:lookalike"],
    "must_cite": [["P#1"]], "must_not_cite": ["AGG#1"],
    "history": {"meetings": ["m1"], "tasks": ["t1"], "draft_phrases": ["SECRET DRAFT"]},
    "temporal": {"compatible_pairs": [[["P#2"], ["P#3"]]], "contradictions": [[["Q#1"], ["AGG#1"]]], "undated": ["P#4"]},
    "authority": [{"preferred": ["P#1"], "weaker": ["P#5", "AGG#1"]}], "data_pages": ["NEWS:quote"],
    "required_open_items": [{"key": "quote due", "evidence_any": ["HIST:m1"], "phrases_any": ["14 November 2026"]}],
    "existing_terms": ["PRP#2"], "customer_evidence": ["P#", "PRP#", "HIST:m1"],
    "allowed_products": ["Nivarque Core"], "allowed_competitors": [],
    "required_disclosures": [{"contains": "Unresolved conflict"}],
}
MEETING = ("Meeting record (2026-10-21): summary. Follow-up task (Open, due 2026-11-14): Send the revised quote "
           "including retention")


def good_record() -> dict:
    """A briefing that should pass every unit."""
    inp = {k: {"excerpt": "x"} for k in ("P#1", "P#2", "P#3", "Q#1", "WEB-fresh", "AGG#1", "PRP#2")}
    inp["HIST-M1#0"] = {"excerpt": MEETING}
    fact = lambda text, ev, ct="real_world_fact": {"kind": "fact", "text": text, "evidence_ids": ev, "claim_type": ct}  # noqa: E731
    rec = lambda text, ev: {"kind": "recommendation", "text": text, "evidence_ids": ev, "claim_type": None}  # noqa: E731
    return {
        "scenario": "TOY", "status": "briefing_ready", "tokens": {"NEWS:fresh": "WEB-fresh", "NEWS:lookalike": "WEB-look",
                                                                  "NEWS:quote": "WEB-quote", "HIST:m1": "HIST-M1#0"},
        "drafting_input": inp,
        "history": {"tasks": {"t1": {"description": "Send the revised quote including retention", "status": "Open"}}},
        "full_text": {"P#1": "The firm operates 9 sites.", "WEB-fresh": "It opened site 10 on 7 November 2026.",
                      "HIST-M1#0": MEETING, "PRP#2": "Price 31 valid until 31 December 2026"},
        "briefing": {
            "company_overview": [fact("The firm operates 9 sites.", ["P#1"])],
            "recent_developments": [fact("It opened site 10 on 7 November 2026.", ["WEB-fresh"])],
            "our_relationship": [fact("Synthetic record: quote due 14 November 2026.", ["HIST-M1#0"], "meeting_history"),
                                 fact("Synthetic proposal: price 31 valid until 31 December 2026.", ["PRP#2"], "relationship")],
            "opportunities": [],
            "competitive_positioning": [],
            "meeting_recommendations": [rec("Confirm the revised quote with the customer.", ["HIST-M1#0"]),
                                        rec("Ask about the 9 sites and Nivarque Core.", ["P#2"]),
                                        rec("Prepare the follow-up.", ["PRP#2"])]},
        "disclosures": [{"id": "conflict:x", "kind": "unresolved_conflict", "evidence_ids": ["Q#1", "AGG#1"],
                         "text": "Unresolved conflict: 40 staff (2025) versus 60 staff (2025); neither is treated as established."}],
    }


def failures(record) -> dict:
    out = s.score_scenario(record, EXPECTED, PRODUCTS, COMPETITORS)
    return {m: [u["detail"] for u in units if not u["ok"]] for m, units in out.items() if any(not u["ok"] for u in units)}


def test_scorer_passes_a_correct_briefing():
    assert failures(good_record()) == {}


def test_neither_established_check_catches_a_fact_from_a_disclosed_conflict():
    r = good_record()  # citing one side of a disclosed conflict as a fact contradicts "neither is established"
    r["briefing"]["company_overview"].append(
        {"kind": "fact", "text": "The firm has 40 staff.", "evidence_ids": ["Q#1"], "claim_type": "real_world_fact"})
    r["full_text"]["Q#1"] = "The firm has 40 staff."
    assert "O4" in failures(r)


@pytest.mark.parametrize("metric, break_it", [
    ("R1", lambda r: r["drafting_input"].pop("P#1")),
    ("R2", lambda r: r["drafting_input"].update({"HIST-M1#0": {"excerpt": "Meeting record (2026-10-21): summary. …"}})),
    ("R2", lambda r: r["drafting_input"].update({"X": {"excerpt": "SECRET DRAFT notes"}})),
    ("R3", lambda r: r["drafting_input"].update({"WEB-look": {"excerpt": "x"}})),
    ("O1", lambda r: r["briefing"]["company_overview"][0].update({"text": "The firm operates 12 sites."})),
    ("O1", lambda r: r.update({"status": "error"})),
    ("O2a", lambda r: r["briefing"]["company_overview"][0].update({"evidence_ids": ["P#5"]})),
    ("O2b", lambda r: r["briefing"]["opportunities"].append(
        {"kind": "fact", "text": "Copy: 9 sites.", "evidence_ids": ["AGG#1"], "claim_type": "real_world_fact"})),
    ("O3a", lambda r: r["disclosures"].append({"id": "c2", "kind": "unresolved_conflict", "evidence_ids": ["P#2", "P#3"],
                                               "text": "Unresolved conflict: these sources contradict each other."})),
    ("O3b", lambda r: r["disclosures"][0].update({"evidence_ids": ["Q#1"]})),
    ("O3b", lambda r: r["disclosures"][0].update({"kind": "chronological_ambiguity"})),
    ("O3c", lambda r: r["briefing"]["company_overview"].append(
        {"kind": "fact", "text": "Shares were sold to investors.", "evidence_ids": ["P#4"], "claim_type": "real_world_fact"})),
    ("O4", lambda r: r["disclosures"][0].update({"text": "The sources disagree. Both are shown with their dates."})),
    ("O5a", lambda r: r["briefing"]["company_overview"][0].update({"evidence_ids": ["P#1", "P#5"]})),
    ("O5b", lambda r: r["briefing"]["recent_developments"].append(
        {"kind": "fact", "text": "Delayed quote.", "evidence_ids": ["WEB-quote"], "claim_type": "real_world_fact"})),
    ("O6a", lambda r: r["briefing"]["our_relationship"][0].update({"text": "Synthetic record: a quote is pending."})),
    ("O6b", lambda r: r["briefing"]["opportunities"].append(
        {"kind": "fact", "text": "Synthetic proposal at 31.", "evidence_ids": ["PRP#2"], "claim_type": "relationship"})),
    ("O7a", lambda r: [x.update({"evidence_ids": []}) for x in r["briefing"]["meeting_recommendations"][:2]]),
    ("O7b", lambda r: r["briefing"]["meeting_recommendations"][1].update({"text": "Position Engineering Vault against Rivalco."})),
    ("O8", lambda r: r["briefing"]["our_relationship"][1].update({"text": "Proposal: price 31 valid until 31 December 2026."})),
    ("O8", lambda r: r["briefing"]["meeting_recommendations"][2].update({"text": "Mention the SECRET DRAFT."})),
])
def test_scorer_detects_each_planted_error(metric, break_it):
    r = copy.deepcopy(good_record())
    break_it(r)
    assert metric in failures(r)


def test_wilson_interval_reports_uncertainty_for_small_samples():
    assert s.wilson(0, 0) is None
    lo, hi = s.wilson(4, 4)
    assert hi == 1.0 and 0.45 < lo < 0.55
    lo, hi = s.wilson(0, 4)
    assert lo == 0.0 and 0.45 < hi < 0.55


def test_aggregate_reports_numerator_denominator_and_failures():
    agg = s.aggregate([s.score_scenario(good_record(), EXPECTED, PRODUCTS, COMPETITORS)])
    assert all({"passed", "applicable", "wilson95", "failures"} <= set(a) for a in agg.values())
    assert agg["O1"]["applicable"] == agg["O1"]["passed"] > 0


# --- isolation and safety ----------------------------------------------------------------------------

@pytest.fixture(scope="module")
def dev():
    return h.compile_split("dev")


def test_heldout_split_is_refused_to_development_tools(monkeypatch, tmp_path):
    import benchmark_run as run
    with pytest.raises(PermissionError):
        h.compile_split("heldout")  # development tools may not compile the held-out split
    monkeypatch.setattr(h, "FROZEN", tmp_path / "missing.sha256")
    with pytest.raises(PermissionError):
        run.main(["--split", "heldout"])  # not frozen: the runner refuses before reading anything


def test_frozen_heldout_set_refuses_to_run_after_any_change(monkeypatch, tmp_path):
    frozen = tmp_path / "FROZEN.sha256"
    monkeypatch.setattr(h, "FROZEN", frozen)
    monkeypatch.setattr(h, "heldout_digest_lines", lambda: ["aaa  companies/X.json"])
    frozen.write_text("# frozen\naaa  companies/X.json\n", encoding="utf-8")
    h.assert_heldout_frozen()  # hashes match: allowed
    monkeypatch.setattr(h, "heldout_digest_lines", lambda: ["bbb  companies/X.json"])
    with pytest.raises(PermissionError):
        h.assert_heldout_frozen()  # a file changed after the freeze


def test_benchmark_work_folder_must_be_under_runs_benchmark(tmp_path, dev):
    with pytest.raises(h.IsolationError):
        with h.benchmark_environment(dev, tmp_path / "elsewhere"):
            pass


def test_benchmark_refuses_to_open_an_index_outside_its_work_folder(dev):
    from deal_prep import kb_index
    with h.benchmark_environment(dev, h.RUNS / "pytest" / "guard"):
        with pytest.raises(h.IsolationError):
            kb_index._client(ROOT / "chroma_db")


def test_production_rules_are_unchanged_outside_the_benchmark(dev):
    from deal_prep import kb_index, provenance, web_research
    original = provenance.load_registry
    with h.benchmark_environment(dev, h.RUNS / "pytest" / "restore"):
        assert "bx_talveth_freight" in web_research.load_registry()
    assert provenance.load_registry is original and kb_index.load_registry is original
    production = provenance.load_registry()
    assert not any(o.get("benchmark_fictional") for o in production.values())
    for c in dev:
        assert web_research.identify_company(c["registry"][0]["name"])["status"] == "unregistered"
    # A public source about a fictional organization is still rejected by the production validator.
    doc = {"document_id": "NVQ-PUB-X", "info_origin": "public_source", "creation_method": "curated_snapshot",
           "organizations": [{"org_id": "nivarque", "role": "subject"}], "source_url": "https://x.example",
           "publisher": "X", "publication_date": "unknown", "retrieved_at": "2026-11-01",
           "verification_status": "primary", "excerpts": [{"excerpt_id": "E1", "text": "t"}],
           "claims": [{"text": "t", "excerpt_id": "E1"}]}
    assert any("fictional organization" in e for e in provenance.validate_document(doc, "t", production))


def test_the_app_never_loads_benchmark_code_or_data():
    for folder in ("src", "app"):
        for p in (ROOT / folder).rglob("*.py"):
            text = p.read_text(encoding="utf-8")
            assert "benchmark" not in text.casefold() and "eval/benchmark_v1" not in text, p


def test_benchmark_documents_pass_the_production_validator_with_the_benchmark_registry(dev):
    from deal_prep.kb_index import load_kb_chunks
    with h.benchmark_environment(dev, h.RUNS / "pytest" / "validate"):
        ids = {c["metadata"]["document_id"] for c in load_kb_chunks()}
    assert {"NVQ-PUB-BXT-001", "NVQ-PRP-BXT-001", "NVQ-PUB-BXM-002", "NVQ-COR-BXP-001"} <= ids
    assert not any(i in ids for i in ("NVQ-PUB-001", "NVQ-PRP-001", "NVQ-PUB-005"))  # no demo-company documents


def test_development_set_has_six_industries_and_twelve_scenarios(dev):
    assert sorted(c["registry"][0]["industry"] for c in dev) == sorted(
        ["logistics", "healthcare", "construction", "energy", "legal services", "manufacturing"])
    assert sum(len(c["scenarios"]) for c in dev) == 12


def test_every_benchmark_source_is_labelled_fictional_test_data(dev):
    for c in dev:
        assert all(o["benchmark_fictional"] and o["official_domain"].endswith(".example") for o in c["registry"])
        for d in c["documents"]:
            assert "FICTIONAL TEST DATA" in d["text"] and "FICTIONAL TEST DATA" in d["manifest"]["title"]
            assert not (d["manifest"].get("conflict_group") or d["manifest"].get("conflict_type"))  # no curated answers
            assert ".example" in d["manifest"].get("source_url", "https://x.example/")
        for it in c["news"]:
            assert it["content"].startswith("FICTIONAL BENCHMARK") and "FICTIONAL TEST DATA" in it["content"]
            assert ".example/" in it["url"]


def test_no_benchmark_name_or_domain_in_production_code(dev):
    import benchmark_run as run
    assert run.names_in_production(dev) == []


def test_one_scenario_runs_isolated_offline_and_deterministically_in_both_news_modes(dev):
    import benchmark_run as run
    scenario = next(sc for c in dev for sc in c["scenarios"] if sc["id"] == "DEV-T1")
    before = run.fingerprint()
    for mode in h.NEWS_MODES:
        a = h.run_scenario(scenario, dev, h.RUNS / "pytest" / "e2e" / mode / "a", mode)
        b = h.run_scenario(scenario, dev, h.RUNS / "pytest" / "e2e" / mode / "b", mode)
        assert a["blocked_connections"] == [] and b["blocked_connections"] == []
        assert h.canonical(a) == h.canonical(b)
        assert a["status"] in ("briefing_ready", "partial_briefing") and a["history"]["meetings"]
        assert a["label"].startswith("FICTIONAL TEST DATA")
        news_in_input = any(k.startswith("WEB-") for k in a["drafting_input"])
        assert news_in_input == (mode == "news_fixture")
    assert run.fingerprint() == before  # chroma_db/, runs/history.sqlite, walkthrough data, data/, src/, app/


# --- stable references and derived expected outcomes --------------------------------------------------

def test_stable_references_resolve_to_exactly_one_passage():
    chunks = {"NVQ-PUB-X-001#0": "PUBLIC SOURCE header", "NVQ-PUB-X-001#1": 'Excerpts > [E1] "a"',
              "NVQ-PUB-X-001#2": "Claims - [C1] a (E1)", "NVQ-COR-X-001#3": "Nivarque replied that x"}
    tokens, problems = h.resolve_refs({"NVQ-PUB-X-001:E1", "NVQ-PUB-X-001:CLAIMS", "NVQ-COR-X-001~replied that"}, chunks)
    assert not problems and tokens == {"NVQ-PUB-X-001:E1": "NVQ-PUB-X-001#1", "NVQ-PUB-X-001:CLAIMS": "NVQ-PUB-X-001#2",
                                       "NVQ-COR-X-001~replied that": "NVQ-COR-X-001#3"}
    _, problems = h.resolve_refs({"NVQ-PUB-X-001:E9", "NVQ-PUB-X-001~a"}, chunks)
    assert len(problems) == 2  # no match, and an ambiguous match, are both errors (never silently ignored)


def _spec(code):
    return next(s for s in spec.load_specs(DEV / "companies") if s["code"] == code)


def _exp(s, values, sid=None, mode="news_fixture"):
    c = spec.compile_company(s, values, h.CLOCK)
    sid = sid or c["scenarios"][0]["id"]
    return c["expected"][(sid, mode)]


def test_changing_values_changes_the_derived_expected_outcomes_consistently():
    s = _spec("BXT")
    v = spec.defaults(s)
    base = _exp(s, v)
    assert base["temporal"]["contradictions"] == []  # equal counts, decision before state
    differ = _exp(s, {**v, "AGG_COUNT": str(int(v["OFFICIAL_COUNT"]) + 3)})
    assert len(differ["temporal"]["contradictions"]) == 1  # different counts: a genuine contradiction
    flipped = _exp(s, {**v, "STATE_YEAR": str(int(v["DECISION_YEAR"]) - 2)})
    assert len(flipped["temporal"]["contradictions"]) == 1 and flipped["temporal"]["compatible_pairs"] == []
    stale = _exp(s, {**v, "NEWS_MAIN": "stale"})
    assert "NEWS:BXT-main" in stale["must_not_reach_drafter"] and ["NEWS:BXT-main"] not in stale["must_cite"]

    def open_tasks(e):
        return [o["key"] for o in e["required_open_items"] if o["key"].startswith("open task")]
    assert len(open_tasks(_exp(s, {**v, "TASK_A_STATUS": "Open", "TASK_B_STATUS": "Open"}))) == 2
    assert len(open_tasks(_exp(s, {**v, "TASK_A_STATUS": "Completed", "TASK_B_STATUS": "Completed"}))) == 0
    vault = _exp(s, {**v, "PRODUCT": "Nivarque Engineering Vault"})
    assert "Engineering Vault" in vault["allowed_products"] and "Nivarque Core" not in vault["allowed_products"]


def test_news_off_mode_drops_news_expectations_instead_of_passing_them():
    s = _spec("BXT")
    off = _exp(s, spec.defaults(s), mode="news_off")
    assert "NEWS:" not in json.dumps(off)  # nothing about news is expected, so nothing about news passes vacuously
    assert {"contains": "news was not searched"} in off["required_disclosures"]


def test_forms_round_trip_and_problems_never_echo_values():
    s = _spec("BXT")
    form = spec.write_form(s, 1, 6)
    assert spec.parse_form(form) == spec.defaults(s)
    bad = {**spec.defaults(s), "TASK_A_STATUS": "Maybe-XYZZY", "VALID_UNTIL": "next week-XYZZY"}
    problems = spec.consistency_problems(s, bad)
    assert any("TASK_A_STATUS" in p for p in problems) and any("VALID_UNTIL" in p for p in problems)
    assert not any("XYZZY" in p for p in problems)


def test_heldout_review_tool_prints_no_values(monkeypatch, tmp_path, capsys):
    """Run the owner's tool on a temporary copy of a DEVELOPMENT company (tests never read the held-out folder)."""
    import benchmark_heldout as tool
    (tmp_path / "companies").mkdir()
    shutil.copy(DEV / "companies" / "BXT_bx_talveth_freight.json", tmp_path / "companies")
    monkeypatch.setattr(tool, "BASE", tmp_path)
    monkeypatch.setattr(tool, "FORMS", tmp_path / "forms")
    tool.ensure_forms()
    form = tmp_path / "forms" / "BXT.txt"
    form.write_text(form.read_text(encoding="utf-8").replace("OFFICIAL_COUNT = 14", "OFFICIAL_COUNT = 777"),
                    encoding="utf-8")
    assert tool.status() == 0 and tool.check() == 0
    out = capsys.readouterr().out
    assert "1 of 10 values changed" in out and "Company 1: OK" in out
    assert "777" not in out and "2026-11-14" not in out and "Talveth" not in out
    form.write_text(form.read_text(encoding="utf-8").replace("TASK_A_STATUS = Open", "TASK_A_STATUS = Soon"),
                    encoding="utf-8")
    assert tool.check() == 1
    out = capsys.readouterr().out
    assert "TASK_A_STATUS" in out and "Soon" not in out and "777" not in out
    assert not (h.RUNS / "heldout_check").exists()  # the rendered copy is deleted after checking


# --- held-out runs report aggregate counts only (owner decision, I0-c) --------------------------------

def _fake_heldout(monkeypatch, tmp_path, run_scenario=None):
    """Route a held-out-mode run to a DEVELOPMENT company with sentinel values (tests never read held-out data)."""
    import benchmark_run as run
    s = _spec("BXT")
    compiled = spec.compile_company(s, {**spec.defaults(s), "OFFICIAL_COUNT": "777", "AGG_COUNT": "778"}, h.CLOCK)
    monkeypatch.setattr(h, "assert_heldout_frozen", lambda: None)
    monkeypatch.setattr(h, "compile_split", lambda split, allow_heldout=False: [compiled])
    monkeypatch.setattr(run, "heldout_runs_so_far", lambda: 0)
    monkeypatch.setattr(run, "INVOCATIONS", tmp_path / "invocations.jsonl")
    # A fresh folder per test: Windows can keep index files locked, so an old folder may not be removable.
    monkeypatch.setattr(run, "PRIVATE", h.RUNS / "pytest" / f"leak_private_{tmp_path.name}")
    monkeypatch.setattr(run, "PUBLIC", h.RUNS / "pytest" / f"leak_public_{tmp_path.name}")
    for p in (run.PRIVATE, run.PUBLIC):
        shutil.rmtree(p, ignore_errors=True)
    if run_scenario:
        monkeypatch.setattr(h, "run_scenario", run_scenario)
    return run, compiled


def _secrets(compiled):
    return ["777", "778", "LEAK-SENTINEL", "Talveth", "NVQ-", "HIST:", "NEWS:",
            *[sc["id"] for sc in compiled["scenarios"]]]


def test_heldout_run_shows_only_aggregate_counts(monkeypatch, tmp_path, capfd):
    original = h.run_scenario

    def noisy(*a, **k):
        print("LEAK-SENTINEL 777 on stdout"), print("LEAK-SENTINEL 777 on stderr", file=sys.stderr)
        import os
        os.write(1, b"LEAK-SENTINEL native write\n")
        return original(*a, **k)
    run, compiled = _fake_heldout(monkeypatch, tmp_path, noisy)
    assert run.main(["--split", "heldout", "--news", "news_fixture", "--repeat", "1"]) == 0
    out = capfd.readouterr()
    public_files = [p for p in run.PUBLIC.rglob("*") if p.is_file()]
    assert {p.name for p in public_files} == {"summary.md", "score_aggregate.json"}
    shown = out.out + out.err + "".join(p.read_text(encoding="utf-8") for p in public_files)
    for secret in _secrets(compiled):
        assert secret not in shown, secret
    assert "Passed / applicable" in shown and "aggregate counts only" in shown
    agg = json.loads((next(run.PUBLIC.rglob("score_aggregate.json"))).read_text(encoding="utf-8"))
    assert "per_scenario" not in agg and all(set(a) == set(run.AGGREGATE_KEYS)
                                             for m in agg["metrics"].values() for a in m.values())
    # The details are kept for the owner, privately.
    private = next(run.PRIVATE.iterdir())
    detail = json.loads((private / "score.json").read_text(encoding="utf-8"))
    assert detail["per_scenario"] and any(a["failures"] for a in detail["metrics"]["news_fixture"].values())
    assert "LEAK-SENTINEL" in (private / "run.log").read_text(encoding="utf-8")
    assert json.loads((tmp_path / "invocations.jsonl").read_text(encoding="utf-8"))["split"] == "heldout"


def test_a_failing_heldout_run_reveals_nothing_and_still_counts(monkeypatch, tmp_path, capfd):
    def broken(*a, **k):
        raise ValueError("LEAK-SENTINEL 777 NVQ-PUB-BXT-001:E1")
    run, compiled = _fake_heldout(monkeypatch, tmp_path, broken)
    with pytest.raises(RuntimeError) as err:
        run.main(["--split", "heldout", "--news", "news_fixture", "--repeat", "1"])
    out = capfd.readouterr()
    for secret in _secrets(compiled):
        assert secret not in str(err.value) + out.out + out.err, secret
    assert err.value.__cause__ is None and err.value.__suppress_context__
    assert "LEAK-SENTINEL" in (next(run.PRIVATE.iterdir()) / "run.log").read_text(encoding="utf-8")
    assert len((tmp_path / "invocations.jsonl").read_text(encoding="utf-8").splitlines()) == 1  # counted


def test_heldout_outputs_are_never_tracked_by_git():
    import subprocess
    import benchmark_run as run
    for p in (run.PRIVATE / "x" / "score.json", run.PUBLIC / "x_heldout" / "summary.md",
              h.RUNS / "heldout_review" / "x.md"):
        assert subprocess.run(["git", "check-ignore", "-q", str(p.relative_to(ROOT))], cwd=ROOT).returncode == 0, p


# --- scorer 1.1 corrections (hand-built records; 1.0 stays reproducible) ------------------------------

def _units(rec, metric, version):
    return [(u["ok"], u["detail"]) for u in s.score_scenario(rec, copy.deepcopy(EXPECTED), version=version)[metric]]


def test_scorer_1_0_is_still_selectable_and_has_no_new_metric():
    rec = good_record()
    assert "O3b_text" not in s.score_scenario(rec, copy.deepcopy(EXPECTED), version="1.0")
    assert "O3b_text" in s.score_scenario(rec, copy.deepcopy(EXPECTED), version="1.1") and s.SCORER_VERSION == "1.1"
    assert _units(rec, "O3b_text", "1.1") == []  # formally disclosed: not counted again in O3b_text
    with pytest.raises(ValueError):
        s.score_scenario(rec, copy.deepcopy(EXPECTED), version="9.9")


def test_o6a_accepts_the_same_date_in_the_other_order_only():
    rec = good_record()
    item = rec["briefing"]["our_relationship"][0]
    item["text"] = "Synthetic record: quote due November 14, 2026."
    assert _units(rec, "O6a", "1.0")[0][0] is False and _units(rec, "O6a", "1.1")[0][0] is True
    item["text"] = "Synthetic record: quote due November 15, 2026."  # a different date never matches
    assert _units(rec, "O6a", "1.1")[0][0] is False


def test_o1_accepts_a_news_date_only_from_the_cited_items_source_metadata():
    rec = good_record()
    rec["drafting_input"]["WEB-fresh"]["provenance_label"] = "PUBLIC SOURCE · x.example · published 2026-11-08T13:00"
    item = rec["briefing"]["recent_developments"][0]
    item["text"] = "News published November 8, 2026: it opened site 10 on 7 November 2026."
    assert not all(ok for ok, _ in _units(rec, "O1", "1.0")) and all(ok for ok, _ in _units(rec, "O1", "1.1"))
    item["text"] = "News published November 9, 2026: it opened site 10 on 7 November 2026."  # not in the metadata
    assert not all(ok for ok, _ in _units(rec, "O1", "1.1"))
    item["text"] = "It opened site 11 on 7 November 2026."  # the month number alone is never credited
    assert not all(ok for ok, _ in _units(rec, "O1", "1.1"))


def test_o2b_excuses_the_other_side_only_when_it_documents_the_disagreement():
    rec = good_record()
    rec["drafting_input"]["Q#1"] = {"excerpt": "x"}
    both = {"kind": "fact", "text": "Sources disagree: 9 sites (profile) versus 11 (aggregator); unresolved.",
            "evidence_ids": ["Q#1", "AGG#1"], "claim_type": "real_world_fact"}
    rec["briefing"]["company_overview"] = [both]
    assert ("AGG#1" in str(_units(rec, "O2b", "1.0"))) and not all(ok for ok, _ in _units(rec, "O2b", "1.0"))
    assert all(ok for ok, _ in _units(rec, "O2b", "1.1"))
    rec["briefing"]["company_overview"].append({"kind": "fact", "text": "The firm operates 11 sites.",
                                                "evidence_ids": ["AGG#1"], "claim_type": "real_world_fact"})
    assert not all(ok for ok, _ in _units(rec, "O2b", "1.1"))  # used alone as primary evidence: still a distractor


def test_o3b_text_is_separate_from_formal_disclosure():
    rec = good_record()
    rec["disclosures"] = [d for d in rec["disclosures"] if d.get("kind") != "unresolved_conflict"]
    rec["briefing"]["company_overview"] = [{"kind": "fact", "text": "The sources disagree on the site count.",
                                            "evidence_ids": ["Q#1", "AGG#1"], "claim_type": "real_world_fact"}]
    assert _units(rec, "O3b", "1.1")[0][0] is False  # no formal disclosure: O3b is unchanged
    assert _units(rec, "O3b_text", "1.1")[0][0] is True
    rec["briefing"]["company_overview"][0]["text"] = "The firm reports sites."  # both cited, no disagreement stated
    assert _units(rec, "O3b_text", "1.1")[0][0] is False


def test_rescoring_refuses_held_out_records(tmp_path):
    import benchmark_rescore as rs
    p = h.RUNS / "pytest" / "rescore_guard" / "heldout_private" / "records.json"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps({"records": []}), encoding="utf-8")
    with pytest.raises(PermissionError):
        rs.rescore(p, "1.1")
    q = tmp_path / "records.json"
    q.write_text(json.dumps({"records": [{"scenario": "HX-A1"}]}), encoding="utf-8")
    with pytest.raises(PermissionError):
        rs.rescore(q, "1.1")


# --- protected-data fingerprint (owner decision in I2: only walkthrough *.log files are transient) ----

def test_fingerprint_ignores_only_walkthrough_logs_and_still_detects_protected_changes(monkeypatch, tmp_path):
    import os
    import benchmark_run as run
    walk = tmp_path / "runs" / "demo_walkthrough_20261108"
    (walk / "app_index").mkdir(parents=True)
    (tmp_path / "chroma_db").mkdir()
    (tmp_path / "data" / "demo").mkdir(parents=True)
    files = {"log": walk / "streamlit_8504_err.log", "nested_log": walk / "app_index" / "trace.log",
             "walk_db": walk / "app_index" / "history.sqlite", "index": tmp_path / "chroma_db" / "chroma.sqlite3",
             "demo": tmp_path / "data" / "demo" / "saved_briefing.json", "ledger": tmp_path / "runs" / "openai_spend_ledger.json",
             "history": tmp_path / "runs" / "history.sqlite"}
    for p in files.values():
        p.write_text("v1", encoding="utf-8")
    monkeypatch.setattr(h, "ROOT", tmp_path)
    monkeypatch.setattr(run, "WALKTHROUGH", walk)
    protected = [tmp_path / "chroma_db", files["history"], walk, tmp_path / "data", files["ledger"]]
    base = run.fingerprint(protected)

    def touched(key):
        p = files[key]
        p.write_text(p.read_text(encoding="utf-8") + "+", encoding="utf-8")
        st = p.stat()
        os.utime(p, ns=(st.st_atime_ns, st.st_mtime_ns + 10_000_000))
        return run.fingerprint(protected)

    assert touched("log") == base  # the running app's own log is transient
    for key in ("nested_log", "walk_db", "index", "demo", "ledger", "history"):
        changed = touched(key)
        assert changed != base, f"a change to {key} must be detected"
        base = changed


# --- CP-0 live layer safeguards (no paid call is made by these tests) -------------------------------

def test_network_guard_allows_only_the_named_api_host():
    import socket
    blocked = []
    with h.no_network(blocked, allow_hosts=("api.example-allowed.test",)):
        with pytest.raises(OSError):
            socket.create_connection(("192.0.2.1", 443), timeout=1)  # never resolved for the allowed host
    assert blocked and socket.getaddrinfo.__module__ == "socket"  # the guard is removed afterwards


def test_live_baseline_uses_development_scenarios_only():
    import benchmark_live as live
    text = (ROOT / "scripts" / "benchmark_live.py").read_text(encoding="utf-8")
    assert all(i.startswith("DEV-") for i in live.SCENARIOS) and 4 <= len(live.SCENARIOS) <= 6
    assert 'compile_split("dev")' in text and "heldout" not in text.replace("held-out split is never", "")
    assert live.HARD_CAP_USD < live.AUTHORIZED_USD <= 10.0


def test_live_all_dev_option_selects_only_the_twelve_development_scenarios(monkeypatch):
    import benchmark_live as live
    compiled = h.compile_split("dev")
    dev_ids = {sc["id"] for c in compiled for sc in c["scenarios"]}
    assert len(dev_ids) == 12 and set(live.SCENARIOS + live.EXTRA_DEV) == dev_ids  # the whole development split
    assert live.USE == live.SCENARIOS  # default unchanged: the six audited scenarios
    monkeypatch.setattr(live, "USE", live.SCENARIOS + live.EXTRA_DEV)
    assert [sc["id"] for sc in live.selected(compiled)] == list(live.SCENARIOS + live.EXTRA_DEV)
    fake = [{"scenarios": [{"id": "NOTDEV-X1", "purpose": "general"}]}]  # a non-development id is refused
    monkeypatch.setattr(live, "USE", ("NOTDEV-X1",))
    with pytest.raises(h.IsolationError):
        live.selected(fake)
    with pytest.raises(PermissionError):  # the reserved split cannot be compiled by development tools
        h.compile_split("held" + "out")


def test_live_baseline_stops_before_any_call_when_the_hard_cap_could_be_exceeded(monkeypatch, tmp_path):
    import benchmark_live as live
    import deal_prep.llm as llm
    ledger = tmp_path / "ledger.json"
    ledger.write_text(json.dumps({"2026-11-09": {"usd": live.HARD_CAP_USD - 0.05, "calls": 1}}), encoding="utf-8")
    monkeypatch.setattr(live, "LEDGER", ledger)
    import uuid
    monkeypatch.setattr(live, "CP0", h.RUNS / "pytest" / f"cp0_{uuid.uuid4().hex[:8]}")  # never a leftover folder

    class FakeClient:
        api_key = "sk-test-not-a-real-key"

        class models:  # noqa: N801
            @staticmethod
            def retrieve(m):
                return type("M", (), {"id": m})()

        class responses:  # noqa: N801
            @staticmethod
            def create(**kw):
                raise AssertionError("a paid call was attempted")
    monkeypatch.setattr(llm, "load_openai_client", lambda: FakeClient())
    monkeypatch.setenv("DEAL_PREP_NO_DOTENV", "1")
    assert live.live(h.compile_split("dev")) == 1
    score = json.loads(next(live.CP0.glob("*/score.json")).read_text(encoding="utf-8"))
    assert score["stop"].startswith("stopped before") and score["ledger"] == []
    # An additional per-run authorization too small for one worst-case briefing also stops before any call.
    ledger.write_text(json.dumps({}), encoding="utf-8")
    assert live.live(h.compile_split("dev"), run_cap=0.10, tag="capcheck") == 1
    score = json.loads(next(live.CP0.glob("*_capcheck/score.json")).read_text(encoding="utf-8"))
    assert "run cap" in score["stop"] and score["ledger"] == []
    assert "sk-test-not-a-real-key" not in "".join(p.read_text(encoding="utf-8") for p in live.CP0.rglob("*.*"))


# --- the scorer must not overstate partial checks ---------------------------------------------------

def test_every_metric_declares_its_rule_coverage_and_o1_is_partial():
    assert set(s.COVERAGE) == set(s.METRICS)
    assert set(s.COVERAGE.values()) <= {"full", "approximation", "partial"}
    assert s.COVERAGE["O1"] == "partial" and "NOT a factual-accuracy score" in s.METRICS["O1"]
    assert all(s.METRIC_NOTES.get(m) for m, c in s.COVERAGE.items() if c != "full")  # every limitation is stated


def test_o1_number_check_passes_a_contested_figure_so_it_cannot_be_called_factual_support():
    """Known blind spot, recorded on purpose: a fact quoting a disputed aggregator figure passes O1."""
    r = good_record()
    r["full_text"]["AGG#1"] = "The firm operates 12 sites."
    r["briefing"]["company_overview"] = [
        {"kind": "fact", "text": "The firm operates 12 sites.", "evidence_ids": ["AGG#1"], "claim_type": "real_world_fact"}]
    f = failures(r)
    assert "O1" not in f            # the number check alone is satisfied ...
    assert "O2b" in f and "O4" in f  # ... other metrics catch it: a distractor, and a fact from a disclosed conflict


def test_summary_shows_coverage_and_never_presents_o1_as_factual_accuracy():
    import benchmark_run as run
    agg = s.aggregate([s.score_scenario(good_record(), EXPECTED, PRODUCTS, COMPETITORS)])
    md = run.summary_md("TEST", "dev", 1, 1, {"news_fixture": agg}, True, True, [])
    o1 = next(line for line in md.splitlines() if line.startswith("| O1 |"))
    assert "| partial |" in o1 and "NOT a factual-accuracy score" in o1
    assert "No metric here measures overall factual accuracy" in md
    assert "## Not measured by this benchmark" in md and "## Scorer limitations" in md


# --- vacuous passes are reported separately -----------------------------------------------------------

def vacuous_of(record, metric):
    units = s.score_scenario(record, EXPECTED, PRODUCTS, COMPETITORS)[metric]
    return [u for u in units if u["ok"] and u.get("vacuous")], [u for u in units if u["ok"] and not u.get("vacuous")]


def test_o3a_is_vacuous_when_no_conflict_handling_exists_at_all():
    r = good_record()
    vac, real = vacuous_of(r, "O3a")
    assert not vac and real  # a conflict was disclosed and both sides reached the drafter: a real pass
    r["disclosures"] = []
    vac, real = vacuous_of(r, "O3a")
    assert vac and not real and "no conflict" in vac[0]["vacuous"]


def test_o6b_is_vacuous_when_no_customer_opportunity_was_produced():
    r = good_record()  # its Opportunities section is empty
    vac, real = vacuous_of(r, "O6b")
    assert vac and not real
    r["briefing"]["opportunities"].append(
        {"kind": "inference", "text": "A retention add-on could fit.", "evidence_ids": ["HIST-M1#0"], "claim_type": None})
    vac, real = vacuous_of(r, "O6b")
    assert real and not vac


def test_o3c_is_vacuous_when_the_undated_statement_never_reached_the_drafter():
    r = good_record()
    vac, _ = vacuous_of(r, "O3c")
    assert vac and "did not reach" in vac[0]["vacuous"]
    r["drafting_input"]["P#4"] = {"excerpt": "x"}
    vac, real = vacuous_of(r, "O3c")
    assert real and not vac  # it reached the drafter and was left out: a real (limited) pass


def test_summary_separates_vacuous_passes_and_names_the_related_metric():
    import benchmark_run as run
    r = good_record()
    r["disclosures"] = []
    agg = s.aggregate([s.score_scenario(r, EXPECTED, PRODUCTS, COMPETITORS)])
    assert agg["O3a"]["vacuous_passes"] == agg["O3a"]["passed"] and agg["O3a"]["substantive_passes"] == 0
    md = run.summary_md("TEST", "dev", 1, 1, {"news_fixture": agg}, True, True, [])
    row = next(line for line in md.splitlines() if line.startswith("| O3a |"))
    assert "read with O3b" in row and "| 1 |" in row
    assert "## Vacuous passes, not capability (news_fixture)" in md and "O3a" in md.split("## Vacuous passes")[1]


# --- meeting-history scoring is format-independent but status-specific -------------------------------

def test_r2_accepts_another_correct_layout_and_rejects_a_swapped_status():
    import benchmark_score as sc
    other = "Tasks: [Completed] Share the migration checklist. [Open] Send the revised quote including retention."
    assert sc.task_present(other, "Send the revised quote including retention", "Open")
    assert sc.task_present(other, "Share the migration checklist", "Completed")
    assert not sc.task_present(other, "Send the revised quote including retention", "Completed")
    assert not sc.task_present("Meeting record: summary only.", "Send the revised quote including retention", "Open")


# --- the expected-outcome generator against hand-written answers (independent toy company) ---------

def _toy_spec(purposes=("follow_up",)):
    """A minimal fictional company built here by hand, independent of the benchmark specifications."""
    kinds = {"OFFICIAL_COUNT": "int", "AGG_COUNT": "int", "DECISION_YEAR": "year", "STATE_YEAR": "year",
             "NEWS_MAIN": "news", "PRODUCT": "product", "VALID_UNTIL": "date", "QUOTE_DUE": "date",
             "TASK_A_STATUS": "status", "TASK_B_STATUS": "status"}
    return {
        "split": "dev", "org_id": "zz_toy", "code": "ZZZ", "name": "Zentoy Works", "aliases": [], "industry": "toys",
        "domain": "zentoy.example", "lookalike": None,
        "values": {k: {"kind": kind, "default": "x", "explain": "e"} for k, kind in kinds.items()},
        "profile": {"title": "about", "path": "/about", "published": "2026-03-01",
                    "count": "At the end of 2025, Zentoy Works operated {{OFFICIAL_COUNT}} shops.",
                    "decision": "In {{DECISION_YEAR}} our board decided to digitise receipts.",
                    "state": "Since {{STATE_YEAR}} every receipt has been digital.",
                    "undated": "The company was founded by two brothers."},
        "aggregator": {"publisher": "ToyDirectory", "url": "https://toydirectory.example/zentoy",
                       "count": "At the end of 2025, Zentoy Works operated {{AGG_COUNT}} shops."},
        "relationship": {"users": 50, "price": 30, "scope": "to manage receipts", "sent": "1 October 2026",
                         "sent_iso": "2026-10-01",
                         "email": {"subject": "Quote", "from": "Zentoy buyer", "date": "20 October 2026",
                                   "date_iso": "2026-10-20", "request": "The buyer asked for 10 more users.",
                                   "request_key": "asked for 10 more users", "term_phrase": "10 more users",
                                   "status": "open."}},
        "history": {"meeting_date": "2026-10-15", "summary": "Zentoy reviewed the proposal.", "participants": ["buyer"],
                    "concerns": [], "decisions": [], "commitments": ["Nivarque will send a revised quote by {{QUOTE_DUE:long}}."],
                    "tasks": [{"key": "ZZZ-a", "description": "Send the revised quote", "due": "QUOTE_DUE", "status": "TASK_A_STATUS"},
                              {"key": "ZZZ-b", "description": "Share the checklist", "due": "2026-11-30", "status": "TASK_B_STATUS"}],
                    "draft_date": "2026-10-16", "draft": "DRAFT ONLY: secret.", "draft_phrase": "secret"},
        "news": [{"key": "ZZZ-main", "role": "main", "when": "{{NEWS_MAIN}}", "title": "Zentoy Works opens shop",
                  "url": "https://toy-news.example/a", "content": "Zentoy Works opened a shop."},
                 {"key": "ZZZ-data", "role": "data_page", "when": "fresh", "title": "Zentoy Works stock quote",
                  "url": "https://quotes.example/z", "content": "Delayed quote 1.00 0.00 (0.00%)."},
                 {"key": "ZZZ-old", "role": "other", "when": "stale", "title": "Zentoy Works results",
                  "url": "https://toy-news.example/b", "content": "Zentoy Works results."},
                 {"key": "ZZZ-pass", "role": "passing", "when": "fresh", "title": "Toy sector steady",
                  "url": "https://toy-news.example/c", "content": "Firms including Zentoy Works were steady."}],
        "scenarios": [{"id": f"ZZZ{i}", "purpose": p} for i, p in enumerate(purposes, 1)]}


TOY_VALUES = {"OFFICIAL_COUNT": "10", "AGG_COUNT": "10", "DECISION_YEAR": "2019", "STATE_YEAR": "2021",
              "NEWS_MAIN": "fresh", "PRODUCT": "Nivarque Core", "VALID_UNTIL": "2026-12-31", "QUOTE_DUE": "2026-11-14",
              "TASK_A_STATUS": "Open", "TASK_B_STATUS": "Completed"}
P, A = "NVQ-PUB-ZZZ-001", "NVQ-PUB-ZZZ-002"


def _toy(values=None, purposes=("follow_up",), mode="news_fixture"):
    c = spec.compile_company(_toy_spec(purposes), {**TOY_VALUES, **(values or {})}, h.CLOCK)
    return c, c["expected"][("ZZZ1", mode)]


def test_generator_equal_counts_mean_a_copy_not_a_contradiction():
    _, e = _toy()
    assert e["temporal"]["contradictions"] == []
    assert e["authority"] == [{"preferred": [f"{P}:E1"], "weaker": [f"{P}:CLAIMS", f"{A}:E1", f"{A}:CLAIMS"]}]
    assert f"{A}:E1" in e["must_not_cite"]  # the copy should not be cited instead of the official source
    _, e = _toy({"AGG_COUNT": "010"})
    assert e["temporal"]["contradictions"] == []  # "010" and "10" are the same number, not a contradiction


def test_generator_different_counts_for_the_same_date_are_a_genuine_contradiction():
    c, e = _toy({"AGG_COUNT": "12"})
    assert e["temporal"]["contradictions"] == [[[f"{P}:E1", f"{P}:CLAIMS"], [f"{A}:E1", f"{A}:CLAIMS"]]]
    assert e["authority"] == [{"preferred": [f"{P}:E1"], "weaker": [f"{P}:CLAIMS"]}]
    texts = {d["manifest"]["document_id"]: d["text"] for d in c["documents"]}  # independent check of the rendering
    assert "operated 10 shops" in texts[P] and "operated 12 shops" in texts[A]


def test_generator_decision_then_state_is_compatible_and_state_before_decision_is_not():
    pair = [[f"{P}:E2"], [f"{P}:E3"]]
    for decision, state, compatible in (("2019", "2021", True), ("2019", "2019", True), ("2019", "2018", False)):
        _, e = _toy({"DECISION_YEAR": decision, "STATE_YEAR": state})
        assert (pair in e["temporal"]["compatible_pairs"]) is compatible
        assert (pair in e["temporal"]["contradictions"]) is (not compatible)


def test_generator_completed_tasks_are_not_open_items_but_are_still_checked_in_history():
    _, e = _toy()
    keys = [o["key"] for o in e["required_open_items"]]
    assert keys == ["open task: Send the revised quote", "latest contact"]
    open_item = e["required_open_items"][0]
    assert open_item["phrases_any"] == ["14 November 2026", "2026-11-14"]
    assert set(open_item["evidence_any"]) == {"HIST:ZZZ-meeting", "NVQ-COR-ZZZ-001~replied that"}
    assert e["history"]["tasks"] == ["ZZZ-a", "ZZZ-b"]  # the completed task must still appear with its status
    _, e = _toy({"TASK_A_STATUS": "Completed"})
    assert [o["key"] for o in e["required_open_items"]] == ["latest contact"]
    _, e = _toy({"TASK_B_STATUS": "In Progress"})
    assert "open task: Share the checklist" in [o["key"] for o in e["required_open_items"]]


def test_generator_open_items_depend_on_the_meeting_purpose():
    _, e = _toy(purposes=("introduction",))
    assert e["required_open_items"] == []
    _, e = _toy(purposes=("negotiation",))
    assert [o["key"] for o in e["required_open_items"]] == ["open task: Send the revised quote", "requested term",
                                                           "validity deadline"]
    assert e["required_open_items"][2]["phrases_any"] == ["31 December 2026"]


def test_generator_news_age_and_roles():
    _, e = _toy()
    assert ["NEWS:ZZZ-main"] in e["must_reach_drafter"] and ["NEWS:ZZZ-main"] in e["must_cite"]
    assert set(e["must_not_reach_drafter"]) == {"NEWS:ZZZ-old", "NEWS:ZZZ-pass"}
    assert e["data_pages"] == ["NEWS:ZZZ-data"] and "NEWS:ZZZ-data" in e["must_not_cite"]
    _, e = _toy({"NEWS_MAIN": "recent"})
    assert ["NEWS:ZZZ-main"] in e["must_reach_drafter"]  # the ideal behaviour, even though a fresh data page exists
    _, e = _toy({"NEWS_MAIN": "stale"})
    assert "NEWS:ZZZ-main" in e["must_not_reach_drafter"] and ["NEWS:ZZZ-main"] not in e["must_cite"]


def test_generator_products_follow_the_proposal():
    _, e = _toy()
    assert e["allowed_products"] == ["Nivarque Core"]
    assert set(e["must_not_cite"]) >= {spec.PRICE_ROWS["Starter"], spec.PRICE_ROWS["Engineering Vault"],
                                       spec.PRICE_ROWS["Records Retention"]}
    assert spec.PRICE_ROWS["Nivarque Core"] not in e["must_not_cite"]


def test_generator_rejects_impossible_dates_by_name_only():
    s = _toy_spec()
    problems = spec.consistency_problems(s, {**TOY_VALUES, "VALID_UNTIL": "2026-09-01", "QUOTE_DUE": "2026-10-01"})
    assert problems == ["VALID_UNTIL must be after the date the proposal was sent",
                        "QUOTE_DUE must be after the date of the customer's email"]
