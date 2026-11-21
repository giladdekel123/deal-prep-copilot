"""Production corrections of 15 November 2026, found by the real-company offline check (general rules, simulated
evidence, offline):
  1. a contested figure between a web result (no document ID) and a document no longer crashes the meeting contract
     or collapses conflicts in the chronology layer;
  2. contested-figure detection considers the reporting period and publication context: different periods,
     reports of the same template published on different days, updated forward-looking statements, bounds and
     source metadata are not contradictions, while genuine contradictions between comparable claims still are."""
from deal_prep import chronology, contract, evidence_profile as ep

DOMAIN = "acme.example"


def label(published, url="https://acme.example/report", verification="primary"):
    return (f"PUBLIC SOURCE · Acme · {url} · published {published} · retrieved 2026-11-15 · "
            f"verification {verification}")


def pub(eid, quote, published="2026-07-17", url="https://acme.example/report", verification="primary"):
    return {"evidence_id": eid, "document_id": eid.split("#")[0], "info_origin": "public_source",
            "source": "internal:company_profile", "excerpt": f'Excerpts > [E1] "{quote}"', "time_window": None,
            "provenance_label": label(published, url, verification)}


def news(eid, text, published="2026-11-05T06:30:00+00:00", url="https://news.example/acme"):
    return {"evidence_id": eid, "document_id": None, "info_origin": "public_source", "source": "external_news",
            "excerpt": text, "time_window": "last_30_days",
            "provenance_label": f"PUBLIC SOURCE · news.example · {url} · published {published} · retrieved "
                                f"2026-11-15 · window last 30 days"}


def header(eid, published):
    return {"evidence_id": eid, "document_id": eid.split("#")[0], "info_origin": "public_source",
            "source": "internal:company_profile", "time_window": None, "provenance_label": label(published),
            "excerpt": f"PUBLIC SOURCE — Acme: release - **Subject organization:** Acme (real organization) - "
                       f"**Publication date:** {published} (dateline (E2)) - **Retrieved:** 2026-11-15"}


def contested(entries):
    return {k: v["contested_with"] for k, v in ep.profile(entries, DOMAIN).items() if v["contested_with"]}


# --- false conflicts: not contradictions ---------------------------------------------------------------

def test_the_same_report_template_published_on_different_days_is_not_a_conflict():
    q2 = pub("Q2#1", "Revenue amounted to SEK 44.6 billion (44.6); revenue increased 1 percent.", "2026-07-17")
    q3 = pub("Q3#1", "Revenue amounted to SEK 49.4 billion (43.7); revenue increased 12 percent.", "2026-11-05")
    q3_news = news("WEB-q3", "Revenue amounted to SEK 49.4 billion (43.7); revenue increased 12 percent.")
    assert contested([q2, q3, q3_news]) == {}
    assert ep.profile([q2, q3, q3_news], DOMAIN)["WEB-q3"]["restates"] == ["Q3#1"]  # a copy is still a copy


def test_explicitly_different_reporting_periods_are_not_a_conflict():
    a = pub("A#1", "In 2024 Acme revenue was EUR 5 million.", "2026-03-01")
    b = pub("B#1", "In 2025 Acme revenue was EUR 6 million.", "2026-03-01")
    c = pub("C#1", "Net receivables totaled SEK 11.6 billion (Jun 30, 2026: 8.7).", "2026-03-01")
    d = pub("D#1", "Net receivables totaled SEK 8.7 billion (Mar 31, 2026: 9.5).", "2026-03-01")
    assert contested([a, b, c, d]) == {}


def test_updated_guidance_is_not_a_conflict():
    august = pub("G1#1", "Acme now expects adjusted EBITDA for the full year 2026 of between $2.0 billion and "
                         "$2.4 billion.", "2026-08-19")
    october = pub("G2#1", "Acme now expects adjusted EBITDA for the full year 2026 of between $2.7 billion and "
                          "$3.0 billion.", "2026-10-06")
    assert contested([august, october]) == {}


def test_source_metadata_is_not_a_company_statement():
    assert contested([header("H1#0", "2026-06-01"), header("H2#0", "2026-10-06")]) == {}


def test_bounds_in_the_same_direction_are_not_a_conflict():
    a = pub("A#1", "Acme has more than 25,000 employees.", "2026-03-01")
    b = pub("B#1", "Acme has more than 27,000 employees.", "2026-03-01")
    c = pub("C#1", "Acme operates 214+ centres worldwide.", "2026-03-01")
    d = pub("D#1", "Acme operates 226+ centres worldwide.", "2026-03-01")
    assert contested([a, b, c, d]) == {}


def test_statements_about_different_named_organizations_are_not_compared():
    a = pub("A#1", "At the end of 2025, Acme operated 4 plants.", "2026-03-01")
    b = pub("B#1", "At the end of 2025, Acme Labs operated 9 plants.", "2026-03-01")
    assert contested([a, b]) == {}


# --- genuine conflicts: still detected -----------------------------------------------------------------

def test_the_same_explicit_period_with_different_figures_is_a_conflict_across_publication_days():
    official = pub("P#1", "At the end of 2025, Acme operated 4 plants.", "2026-02-15")
    directory = pub("D#1", "At the end of 2025, Acme operated 5 plants.", "2026-06-01",
                    url="https://index.example/acme", verification="single_secondary")
    assert contested([official, directory]) == {"P#1": ["D#1"], "D#1": ["P#1"]}


def test_different_figures_published_on_the_same_day_are_a_conflict():
    a = pub("A#1", "Acme employs 3,200 people.", "2026-03-01")
    b = pub("B#1", "Acme employs 4,100 people.", "2026-03-01", url="https://index.example/acme",
            verification="single_secondary")
    assert contested([a, b]) == {"A#1": ["B#1"], "B#1": ["A#1"]}


def test_an_undated_source_is_not_assumed_to_describe_a_different_moment():
    a = pub("A#1", "Acme employs 3,200 people.", "2026-03-01")
    b = pub("B#1", "Acme employs 4,100 people.", "unknown", url="https://index.example/acme",
            verification="single_secondary")
    assert contested([a, b]) == {"A#1": ["B#1"], "B#1": ["A#1"]}


def test_different_dates_for_the_same_event_are_a_conflict():
    a = pub("A#1", "Acme was founded in 1887.", "2026-01-10")
    b = pub("B#1", "Acme was founded in 1889.", "2025-05-01", url="https://index.example/acme",
            verification="single_secondary")
    assert contested([a, b]) == {"A#1": ["B#1"], "B#1": ["A#1"]}


def test_different_guidance_published_on_the_same_day_is_a_conflict():
    a = pub("A#1", "Acme expects revenue of $5 billion for the full year 2026.", "2026-10-06")
    b = news("WEB-b", "Acme expects revenue of $6 billion for the full year 2026.", "2026-10-06T12:00:00+00:00")
    assert contested([a, b]) == {"A#1": ["WEB-b"], "WEB-b": ["A#1"]}


def test_a_copy_published_later_still_restates_the_primary_source():
    official = pub("P#1", "At the end of 2025, Acme operated 4 plants.", "2026-02-15")
    copy = pub("D#1", "At the end of 2025, Acme operated 4 plants.", "2026-09-01", url="https://index.example/acme",
               verification="single_secondary")
    assert ep.profile([official, copy], DOMAIN)["D#1"]["restates"] == ["P#1"] and contested([official, copy]) == {}


# --- the original crash: a web result (no document ID) on one side ------------------------------------

def _raw(e, text):
    return {"evidence_id": e["evidence_id"], "info_origin": "public_source", "provenance_label": e["provenance_label"],
            "text": text, "excerpt": e["excerpt"], "document_id": e["document_id"], "time_window": e["time_window"],
            "metadata": {"doc_type": "public_profile"}}


def test_a_conflict_between_a_web_result_and_a_document_builds_its_topic_without_crashing():
    doc = pub("P#1", "At the end of 2025, Acme operated 4 plants.", "2026-02-15")
    web = news("WEB-x", "At the end of 2025, Acme operated 5 plants.")
    bundle = {"purpose": "general", "identity": {"name": "Acme", "domain": DOMAIN, "org_id": "acme"},
              "internal": {"company_profile": {"evidence": [_raw(doc, doc["excerpt"])]}},
              "external": {"evidence": [{k: v for k, v in web.items() if k != "source"}]}, "selection": {}}
    topics = [t for t in contract.essential_topics(bundle) if t["id"].startswith("contested:")]
    assert len(topics) == 1
    assert sorted(i for side in topics[0]["groups"] for i in side) == ["P#1", "WEB-x"]


def test_conflicts_between_web_results_are_kept_apart_and_named_by_their_evidence():
    doc = pub("P#1", "At the end of 2025, Acme operated 4 plants.", "2026-02-15")
    web1 = news("WEB-1", "At the end of 2025, Acme operated 5 plants.")
    web2 = news("WEB-2", "At the end of 2025, Acme operated 6 plants.", url="https://news.example/b")
    conflicts = [c for c in chronology.derived_conflicts([doc, web1, web2], DOMAIN) if c["kind"] == "unresolved_conflict"]
    assert len(conflicts) == 3  # three distinct pairs; web results are no longer one shared "None" document
    text = " ".join(chronology.disclosure(c)["text"] for c in conflicts)
    assert "None (" not in text and "WEB-1 (" in text and "WEB-2 (" in text
