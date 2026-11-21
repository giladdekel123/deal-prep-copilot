"""Phase 4.5 I2: evidence profile (source class, statement form, date status, contested figures), quote and
data pages kept out of news, and source-authority preference in the offline template. All offline."""
from datetime import datetime, timezone

from deal_prep import evidence_profile as ep
from deal_prep.demo import overview_selection
from deal_prep.web_research import Budget, CompanyIdentity, SearchConfig, research_company_news

NOW = datetime(2026, 11, 9, 9, 0, tzinfo=timezone.utc)


def kb(eid, excerpt, verification="primary", doc=None, published="2026-03-01"):
    return {"evidence_id": eid, "source": "internal:company_profile", "info_origin": "public_source",
            "document_id": doc or eid.split("#")[0], "excerpt": excerpt, "time_window": None,
            "provenance_label": f"PUBLIC SOURCE · Pub · https://x.example · published {published} · retrieved "
                                f"2026-11-02 · verification {verification}"}


# --- quote and data pages ---------------------------------------------------------------------------

def test_quote_and_market_data_pages_are_detected():
    assert ep.is_data_page("Acme Corp (ACME) stock quote", "https://news.example/a", "Delayed quote. 12.40 0.00 (0.00%).")
    assert ep.is_data_page("Acme Corp", "https://quotes.example/acme", "Acme Corp historical prices")
    assert ep.is_data_page("Acme Corp share price", "https://x.example/p", "Market cap 3bn. At close 4pm.")


def test_ordinary_news_mentioning_a_share_price_once_is_still_news():
    assert not ep.is_data_page("Acme Corp opens plant", "https://news.example/2026/acme-plant",
                               "Acme Corp opened a plant; its share price rose after the announcement.")
    assert not ep.is_data_page("Acme Corp wins contract", "https://news.example/acme", "Acme Corp won a 40m contract.")


class FixedNews:
    """Returns the same results for every window; the pipeline's own date rules decide what is kept."""

    def __init__(self, results):
        self.results, self.config, self.payloads = results, SearchConfig(), []

    def search(self, payload, budget, today, trace):
        budget.reserve(1, today)
        self.payloads.append(payload)
        trace.append({"service": "test", "query": payload["query"], "outcome": "ok", "results": len(self.results)})
        return {"results": self.results}


def test_a_fresh_quote_page_neither_counts_as_news_nor_blocks_the_30_day_search():
    quote = {"title": "Acme Corp (ACME) stock quote", "url": "https://quotes.example/acme",
             "published_date": "2026-11-08T13:00:00Z", "content": "Acme Corp. Delayed quote 12.40 0.00 (0.00%).",
             "score": 0.9}
    older = {"title": "Acme Corp opens a new plant", "url": "https://news.example/acme-plant",
             "published_date": "2026-10-25T10:00:00Z", "content": "Acme Corp opened a new plant, Acme Corp said.",
             "score": 0.8}
    client = FixedNews([quote, older])
    news = research_company_news(CompanyIdentity(name="Acme Corp"), client, Budget(SearchConfig()), now=NOW)
    ids = [e["source_url"] for e in news["evidence"]]
    assert quote["url"] not in ids and older["url"] in ids  # the quote page did not stop the fallback
    assert news["status"] == "fallback_30d_found" and news["excluded"]["data_page"] >= 1


# --- profile ----------------------------------------------------------------------------------------

def test_source_class_statement_form_and_date_status_follow_the_evidence_only():
    official = kb("P#1", 'Excerpts > [E1] "At the end of 2025, Acme Corp operated 4 plants."')
    claims = kb("P#5", "Claims - [C1] At the end of 2025, Acme Corp operated 4 plants. (E1)")
    directory = kb("D#1", 'Excerpts > [E1] "At the end of 2025, Acme Corp operated 4 plants."', "single_secondary",
                   published="unknown")
    news = {"evidence_id": "WEB-1", "source": "external_news", "info_origin": "public_source", "excerpt": "x",
            "provenance_label": "PUBLIC SOURCE · n.example · https://n.example · published 2026-11-08T13:00 · window"}
    record = {"evidence_id": "NVQ-PRP-1#0", "source": "internal:relationship_history", "info_origin": "synthetic_record",
              "excerpt": "Scope", "provenance_label": "SYNTHETIC — not a real business fact"}
    p = ep.profile([official, claims, directory, news, record], "x.example")
    assert (p["P#1"]["source_class"], p["P#1"]["statement_form"]) == ("official_company_source", "verbatim_excerpt")
    assert p["P#5"]["statement_form"] == "claims_summary"
    assert (p["D#1"]["source_class"], p["D#1"]["date_status"]) == ("secondary_profile", "publication_date_unknown")
    assert (p["WEB-1"]["source_class"], p["WEB-1"]["date_status"]) == ("news", "publication_date_provider_estimate")
    assert p["NVQ-PRP-1#0"]["source_class"] == "internal_record"
    assert p["D#1"]["restates"] == ["P#1"] and p["P#1"]["contested_with"] == []  # a copy, not a conflict


def test_a_primary_source_is_the_companys_own_only_on_its_official_domain():
    def primary(url):
        e = kb("R#1", 'Excerpts > [E1] "In 2025 Acme Corp held 3 licences."')
        e["provenance_label"] = e["provenance_label"].replace("https://x.example", url)
        return e
    assert ep.source_class(primary("https://acme.example/about"), "acme.example") == "official_company_source"
    assert ep.source_class(primary("https://www.ir.acme.example/report"), "acme.example") == "official_company_source"
    assert ep.source_class(primary("https://regulator.example/licences/acme"), "acme.example") == "primary_third_party"
    assert ep.source_class(primary("https://notacme.example/x"), "acme.example") == "primary_third_party"
    assert ep.source_class(primary("https://regulator.example/licences/acme"), None) == "primary_source"  # owner unknown
    news = {"evidence_id": "WEB-2", "source": "external_news", "info_origin": "public_source", "excerpt": "x",
            "provenance_label": "PUBLIC SOURCE · acme.example · https://acme.example/news/1 · published 2026-11-08"}
    assert ep.source_class(news, "acme.example") == "company_announcement" and ep.source_class(news, None) == "news"


def test_a_directory_copying_a_regulator_figure_restates_it():
    reg = kb("G#1", 'Excerpts > [E1] "In 2025 Acme Corp held 3 licences."')
    reg["provenance_label"] = reg["provenance_label"].replace("https://x.example", "https://regulator.example/acme")
    copy = kb("D#1", 'Excerpts > [E1] "In 2025 Acme Corp held 3 licences."', "single_secondary")
    p = ep.profile([reg, copy], "acme.example")
    assert p["G#1"]["source_class"] == "primary_third_party" and p["D#1"]["restates"] == ["G#1"]


def test_cp2_the_model_input_carries_the_profile_and_the_switch_removes_it(monkeypatch):
    from deal_prep import evidence
    official = kb("P#1", 'Excerpts > [E1] "At the end of 2025, Acme Corp operated 4 plants."')
    official["provenance_label"] = official["provenance_label"].replace("https://x.example", "https://acme.example/about")
    rival = kb("R#1", 'Excerpts > [E1] "At the end of 2025, Acme Corp operated 5 plants."', "single_secondary")
    raw = [{"evidence_id": e["evidence_id"], "info_origin": "public_source", "provenance_label": e["provenance_label"],
            "text": e["excerpt"], "document_id": e["document_id"], "metadata": {}} for e in (official, rival)]
    bundle = {"identity": {"name": "Acme Corp", "domain": "acme.example"},
              "internal": {"company_profile": {"sections": [], "evidence": raw}}}
    shown = {e["evidence_id"]: e for e in evidence.model_evidence(bundle)}
    assert shown["P#1"]["profile"] == {"source_class": "official_company_source", "statement_form": "verbatim_excerpt",
                                       "date_status": "publication_date_stated", "contested_with": ["R#1"]}
    assert shown["R#1"]["profile"]["source_class"] == "secondary_profile"
    monkeypatch.setattr(evidence, "PROFILE_IN_MODEL_INPUT", False)
    assert all("profile" not in e for e in evidence.model_evidence(bundle))


def test_different_figures_for_the_same_statement_are_contested_on_both_sides():
    official = kb("P#1", 'Excerpts > [E1] "At the end of 2025, Acme Corp operated 4 plants."')
    directory = kb("D#1", 'Excerpts > [E1] "At the end of 2025, Acme Corp operated 5 plants."', "single_secondary")
    unrelated = kb("D#2", 'Excerpts > [E2] "Acme Corp was founded in 1990."', "single_secondary", doc="D")
    p = ep.profile([official, directory, unrelated])
    assert p["P#1"]["contested_with"] == ["D#1"] and p["D#1"]["contested_with"] == ["P#1"]
    assert p["D#2"]["contested_with"] == [] and p["D#1"]["restates"] == []


def test_two_passages_of_one_document_are_never_compared():
    a = kb("P#1", 'Excerpts > [E1] "In 2020 Acme Corp operated 3 plants."')
    b = kb("P#2", 'Excerpts > [E2] "In 2021 Acme Corp operated 4 plants."')
    assert all(not v["contested_with"] for v in ep.profile([a, b]).values())


def test_overview_prefers_official_verbatim_skips_copies_and_keeps_disagreements_together():
    official = kb("P#1", 'Excerpts > [E1] "At the end of 2025, Acme Corp operated 4 plants."')
    claims = kb("P#5", "Claims - [C1] At the end of 2025, Acme Corp operated 4 plants. (E1)")
    copy = kb("C#1", 'Excerpts > [E1] "At the end of 2025, Acme Corp operated 4 plants."', "single_secondary")
    rival = kb("R#1", 'Excerpts > [E1] "At the end of 2025, Acme Corp operated 6 plants."', "single_secondary")
    evidence = [claims, copy, rival, official]
    chosen = overview_selection(evidence, ep.profile(evidence))
    assert [(e["evidence_id"], [o["evidence_id"] for o in others]) for e, others in chosen] == [("P#1", ["R#1"])]
