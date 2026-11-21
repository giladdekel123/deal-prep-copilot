"""I7 (owner-approved 2026-11-16): company context, research coverage, business unknowns, dates, news excerpts and
length. General rules on simulated evidence ("Acme Corp", fictional, offline); no real company and no paid call.

Groups: company essentials reaching the contract (and omissions caught and repaired); diverse retrieval and the
agent; business unknowns and discovery questions; dates; news excerpts; length; negative tests (no invented
relationship, need, product claim or irrelevant requirement); genuine contradictions still detected."""
import json
import re
from datetime import date, timedelta
from types import SimpleNamespace

import pytest

from deal_prep import agent, briefing, company_context, contract, kb_index, pdf_export, provenance, web_research
from deal_prep import chronology, evidence_profile as ep
from deal_prep.citations import validate_citations
from deal_prep.disclosures import required_disclosures
from deal_prep.evidence import evidence_index, model_evidence

DOMAIN = "acme.example"
TODAY = date(2026, 11, 15)
CREATED = "2026-11-15T10:00:00+00:00"
NAME = "Acme Corp"


def ago(days):
    return (TODAY - timedelta(days=days)).isoformat()


def label(published, url, verification="primary"):
    return (f"PUBLIC SOURCE · Acme Corp · {url} · published {published} · retrieved 2026-11-15 · "
            f"verification {verification}")


def doc(doc_id, published, quotes, title="release", url=None, verification="primary"):
    """A curated public document as knowledge-base evidence: a header passage, then one verbatim excerpt each."""
    url = url or f"https://{DOMAIN}/{doc_id.lower()}"
    meta = {"doc_type": "public_profile", "subject_org_id": "acme", "publication_date": published,
            "approval_status": "approved"}
    out = [{"evidence_id": f"{doc_id}#0", "info_origin": "public_source", "document_id": doc_id,
            "provenance_label": label(published, url, verification), "metadata": dict(meta),
            "text": f"PUBLIC SOURCE — Acme Corp: {title} - **Subject organization:** Acme Corp (real organization) "
                    f"- **Publication date:** {published}"}]
    for n, q in enumerate(quotes, 1):
        out.append({"evidence_id": f"{doc_id}#{n}", "info_origin": "public_source", "document_id": doc_id,
                    "provenance_label": label(published, url, verification), "metadata": dict(meta),
                    "text": f'Excerpts > [E{n}] "{q}"'})
    return out


def web(eid, text, published=None, window="last_30_days"):
    pub = published or f"{ago(3)}T08:00:00+00:00"
    return {"evidence_id": eid, "info_origin": "public_source", "document_id": None, "time_window": window,
            "excerpt": text, "provenance_label": f"PUBLIC SOURCE · news.example · https://news.example/{eid} · "
                                                  f"published {pub} · retrieved 2026-11-15 · window {window}"}


def bundle(entries, purpose="introduction", relationship=(), news=(), gaps=None):
    return {"purpose": purpose, "created_at": CREATED, "status": "complete", "company_input": NAME,
            "identity": {"name": NAME, "org_id": "acme", "domain": DOMAIN, "country": None, "confidence": 1.0},
            "internal": {"company_profile": {"sections": ["company_overview"], "evidence": list(entries)},
                         "relationship_history": {"sections": ["our_relationship"], "evidence": list(relationship)}},
            "external": {"status": "fallback_30d_found", "evidence": list(news)}, "selection": {},
            "gaps": gaps if gaps is not None else
            [f"No prior relationship records (proposals, meetings, correspondence) with {NAME}."]}


ABOUT = doc("ACME-ABOUT", "unknown", ["Acme Corp is a global supplier of industrial valves, and we operate in 12 "
                                      "countries.", "Acme has more than 4,000 employees."], title="about us")
RESULTS = doc("ACME-Q3", ago(10), ["Revenue amounted to EUR 1.2 billion (1.1).", "Operating income was EUR 140 million.",
                                   "Order intake reached EUR 1.4 billion.", "Net debt totaled EUR 0.3 billion."],
              title="interim report, third quarter 2026")
DEAL = doc("ACME-DEAL", ago(200), ["Borealis Holdings will acquire Acme Corp for EUR 20.00 per share in cash."])
STATUS = doc("ACME-STATUS", ago(60), ["The acquisition remains subject to regulatory approvals and is expected to "
                                      "close in the first quarter of 2027."])
CEO = doc("ACME-CEO", ago(100), ["The Board appointed Dana Ortiz as Chief Executive Officer, effective 1 September "
                                 "2026."])
OUTLOOK_OLD = doc("ACME-H1", ago(110), ["Acme expects to generate EBITDA of EUR 300 million to EUR 320 million for the "
                                        "full year 2026."])
OUTLOOK_NEW = doc("ACME-RAISE", ago(40), ["Acme now expects EBITDA of EUR 340 million to EUR 360 million for the full "
                                          "year 2026."])
ALL = ABOUT + RESULTS + DEAL + STATUS + CEO + OUTLOOK_OLD + OUTLOOK_NEW


def topics_of(b):
    return {t["id"]: t for t in contract.essential_topics(b)}


def fact(text, ids):
    return {"kind": "fact", "text": text, "evidence_ids": ids, "claim_type": "real_world_fact"}


def rec(text, ids=()):
    return {"kind": "recommendation", "text": text, "evidence_ids": list(ids), "claim_type": None}


def draft(**sections):
    out = {s: [] for s in briefing.SECTIONS}
    out.update(sections)
    return {"sections": out, "disclosures": []}


def valid(b, sections):
    """A draft that acknowledges every required disclosure and explains every empty section."""
    d = draft(**sections)
    d["disclosures"] = [{"id": x["id"], "text": x["text"]} for x in required_disclosures(b)]
    d["disclosures"] += [{"id": f"empty_section:{s}", "text": "Nothing supported."} for s, v in d["sections"].items()
                         if not v]
    return d


# --- 1. company essentials reach the contract ------------------------------------------------------------------

def test_a_new_lead_gets_the_company_essentials_as_contract_topics():
    topics = topics_of(bundle(ALL))
    assert {"company:identity", "company:ownership", "company:leadership", "company:outlook",
            "company:latest_release"} <= set(topics)
    latest = topics["company:latest_release"]
    assert latest["section"] == "recent_developments" and latest["require_all"]  # published 10 days ago
    assert "'interim report, third quarter 2026'" in latest["requirement"] and "5 November 2026" in latest["requirement"]
    assert "at most 3" in latest["requirement"]
    own = topics["company:ownership"]
    assert len(own["groups"]) == 2  # what was announced, and its newest status
    assert "pending" in own["requirement"] and "never state a closing date" in own["requirement"]
    out = topics["company:outlook"]
    assert out["groups"] == [["ACME-RAISE#1"]] and "superseded" in out["requirement"]
    assert "not a conflict" in out["requirement"]
    assert "date not stated" in topics["company:identity"]["requirement"]  # the about page is undated
    assert topics["company:leadership"]["groups"] == [["ACME-CEO#1"]]


def test_a_release_about_the_outlook_is_outlook_not_the_latest_results():
    guide = doc("ACME-GUIDE", ago(5), ["Acme raised its guidance for the year.",
                                       "EBIT of between EUR 50 million and EUR 60 million for the full year 2026"],
                title="full-year guidance raised")  # the second excerpt is a fragment without an outlook word
    results = doc("ACME-Q2", ago(60), ["Revenue amounted to EUR 1.1 billion (1.0).",
                                       "Order intake was between EUR 0.9 billion and EUR 1.0 billion."],
                  title="interim report, second quarter")
    t = topics_of(bundle(ABOUT + guide + results))
    assert t["company:outlook"]["groups"] == [["ACME-GUIDE#2"]]
    assert t["company:latest_release"]["groups"] == [["ACME-Q2#0", "ACME-Q2#1"]]  # a range is not a reported result


def test_an_older_release_is_company_context_not_a_recent_development():
    old = doc("ACME-Q2", ago(80), ["Revenue amounted to EUR 1.1 billion (1.0)."], title="interim report, second quarter")
    t = topics_of(bundle(ABOUT + old))["company:latest_release"]
    assert t["section"] == "company_overview" and "second quarter" in t["requirement"]


def test_received_company_facts_that_the_draft_omits_are_detected():
    topic = [topics_of(bundle(ABOUT + RESULTS))["company:latest_release"]]
    assert contract.coverage(draft(), topic)["topics"]["company:latest_release"] == "missing"
    figures_only = contract.coverage(draft(recent_developments=[fact("Revenue was EUR 1.2 billion.",
                                                                     ["ACME-Q3#1"])]), topic)
    assert figures_only["topics"]["company:latest_release"] == "cited_only"
    assert figures_only["missing_capabilities"]["company:latest_release"] == ["the release or period and its date"]
    full = draft(recent_developments=[fact("Acme's interim report for the third quarter of 2026, published 5 November "
                                           "2026, gives revenue of EUR 1.2 billion.", ["ACME-Q3#0", "ACME-Q3#1"])])
    assert contract.coverage(full, topic)["topics"]["company:latest_release"] == "communicated"


class TwoDrafts:
    """Simulated drafter: a valid first draft that omits the latest release, then a complete one on repair."""

    def __init__(self):
        self.messages = []

    def __call__(self, messages):
        self.messages.append(messages)
        payload = json.loads(messages[1]["content"])
        recent = [] if len(self.messages) == 1 else [fact(
            "Acme's interim report for the third quarter of 2026, published 5 November 2026, gives revenue of EUR 1.2 "
            "billion.", ["ACME-Q3#0", "ACME-Q3#1"])]
        d = draft(recent_developments=recent, company_overview=[fact("Acme Corp says it is a global supplier of "
                                                                     "industrial valves (date not stated).",
                                                                     ["ACME-ABOUT#1"])])
        d["disclosures"] = [{"id": x["id"], "text": x["text"]} for x in payload["required_disclosures"]]
        d["disclosures"] += [{"id": f"empty_section:{s}", "text": "Nothing supported."}
                             for s, v in d["sections"].items() if not v]
        return json.dumps(d)


def test_an_omitted_company_topic_is_sent_back_once_and_the_complete_draft_is_kept():
    gen = TwoDrafts()
    out = briefing.draft_briefing(bundle(ABOUT + RESULTS), gen, repair_coverage=True)
    assert out["status"] == "ok" and out["coverage"]["repaired"] is True and len(gen.messages) == 2
    assert "company:latest_release" in gen.messages[1][-1]["content"]
    assert out["coverage"]["topics"]["company:latest_release"] == "communicated"


def test_company_topics_use_only_the_organizations_own_recent_dated_official_documents():
    aggregator = doc("DIR-1", ago(20), ["Borealis Holdings acquired Acme Corp."],
                     url="https://directory.example/acme", verification="single_secondary")
    old_deal = doc("ACME-OLD", ago(500), ["Acme Corp acquired Valvex Ltd."])
    undated_ceo = doc("ACME-TEAM", "unknown", ["The Board appointed Lee Park as Chief Executive Officer."])
    old_results = doc("ACME-FY", ago(200), ["Revenue amounted to EUR 4.5 billion."])
    vendor = [{"evidence_id": "NVQ-X#1", "info_origin": "synthetic_record", "document_id": "NVQ-X",
               "provenance_label": "SYNTHETIC — not a real business fact · vendor", "metadata": {"doc_type": "x"},
               "text": 'Excerpts > [E1] "The vendor was acquired by a fund for USD 9.00 per share."'}]
    news = [web("WEB-deal", "Borealis Holdings agreed to acquire Acme Corp.")]
    ids = set(topics_of(bundle(aggregator + old_deal + undated_ceo + old_results + vendor, news=news)))
    assert not {t for t in ids if t.startswith("company:")}


def test_a_release_filed_on_a_regulators_site_counts_but_a_directory_entry_does_not():
    filed = doc("ACME-6K", ago(30), ["The Board appointed Dana Ortiz as Chief Executive Officer."],
                url="https://filings.example/acme/6k")  # primary, not on the company's domain
    directory = doc("DIR-2", ago(20), ["The Board appointed Lee Park as Chief Executive Officer."],
                    url="https://directory.example/acme", verification="single_secondary")
    assert topics_of(bundle(ABOUT + filed + directory))["company:leadership"]["groups"] == [["ACME-6K#1"]]


# REPLACED in C2 (owner decision of 2026-11-17, "every briefing must contain a concise, purpose-sensitive company
# essentials summary"). The former test, test_company_and_discovery_topics_are_for_introductions_and_general_meetings_
# only, asserted that negotiation, follow-up and product-demonstration briefings get NO company topic. That was the I7
# specification, which the owner has changed: those purposes now get exactly one compact company:brief (the full set
# stays for introductions and general meetings). Discovery questions are unchanged by C2 (introductions and general
# meetings only; C3 will extend them to early-stage leads). The new specification is tested in full in
# test_company_essentials_by_purpose_c2.py.
@pytest.mark.parametrize("purpose", ["negotiation", "follow_up", "product_demo"])
def test_other_purposes_get_one_compact_company_brief_and_no_discovery_questions(purpose):
    found = [t for t in topics_of(bundle(ALL, purpose=purpose)) if t.startswith(("company:", "discovery:"))]
    assert found == ["company:brief"]


def test_a_company_with_only_an_about_page_gets_only_its_identity():
    assert [t for t in topics_of(bundle(ABOUT)) if t.startswith("company:")] == ["company:identity"]


# --- 2. diverse retrieval and the research agent ----------------------------------------------------------------

def passage(doc_id, n, published):
    return {"evidence_id": f"{doc_id}#{n}", "document_id": doc_id, "info_origin": "public_source",
            "text": f'Excerpts > [E{n}] "Statement {n}."', "provenance_label": label(published, "https://acme.example/x"),
            "metadata": {"subject_org_id": "acme", "publication_date": published}}


def test_profile_search_keeps_one_passage_per_document_and_adds_the_newest_documents(monkeypatch):
    dates = {"ABOUT": "unknown", "A": ago(300), "B": ago(200), "C": ago(90), "D": ago(30), "E": ago(5)}
    pool = [passage(d, n, day) for d, day in dates.items() for n in (0, 1, 2)]
    monkeypatch.setattr(kb_index, "passages_where", lambda where, chroma_dir=None: pool)
    ranked = [passage("ABOUT", 1, "unknown"), passage("ABOUT", 2, "unknown"), passage("ABOUT", 0, "unknown"),
              passage("A", 1, dates["A"]), passage("ABOUT", 3, "unknown")]
    out = company_context.profile_passages(ranked, "acme", None)
    docs = [e["document_id"] for e in out]
    assert docs[:2] == ["ABOUT", "A"] and len(docs) == len(set(docs))  # one passage per page
    assert {"C", "D", "E"} <= set(docs)  # the three newest dated documents always reach selection


def test_a_document_the_agent_finds_arrives_with_its_excerpts(monkeypatch):
    found = doc("ACME-Q3", ago(10), ["Revenue amounted to EUR 1.2 billion (1.1).", "Order intake reached EUR 1.4 "
                                                                                   "billion."])
    monkeypatch.setattr(kb_index, "passages_where", lambda where, chroma_dir=None: found)
    out = company_context.document_excerpts([found[0]], {"ACME-Q3#0"}, None)
    assert [e["evidence_id"] for e in out] == ["ACME-Q3#1", "ACME-Q3#2"]  # the excerpts, not the header again


@pytest.fixture
def public_only_registry(monkeypatch):
    monkeypatch.setattr(provenance, "load_registry",
                        lambda *a, **kw: {"acme": {"org_id": "acme", "name": NAME, "public_only": True}})


def test_the_agent_is_told_that_a_public_only_organization_has_no_relationship_records(public_only_registry):
    ctx = agent.agent_context(bundle(ABOUT + RESULTS), [], 3)
    assert not [g for g in ctx["gaps"] if "relationship records" in g]
    assert "public-only" in ctx["not_held"] and "do not search for them" in ctx["not_held"]
    assert ctx["company_coverage_gaps"] == []  # identity, a recent dated release and financial results are present


def test_the_agent_reports_missing_company_coverage(public_only_registry):
    gaps = agent.agent_context(bundle(ABOUT), [], 3)["company_coverage_gaps"]
    assert any("dated official release" in g for g in gaps) and "no financial results" in gaps


class Script:
    def __init__(self, *actions):
        self.actions = list(actions)

    def __call__(self, context):
        return self.actions.pop(0)


def test_the_agent_may_not_spend_searches_on_relationship_records_of_a_public_only_organization(
        public_only_registry, monkeypatch):
    ran = []
    monkeypatch.setattr(agent, "_internal_lookup", lambda q, *a, **kw: ran.append(q) or [])
    monkeypatch.setattr(web_research, "identify_company",
                        lambda *a, **kw: {"identity": SimpleNamespace(name=NAME, org_id="acme", domain=DOMAIN)})
    decide = Script({"action": "search_internal", "query": "Acme Corp CRM proposals correspondence"},
                    {"action": "search_internal", "query": "Acme Corp latest annual results"},
                    {"action": "finish_research"})
    out = agent.run_agent(bundle(ABOUT), decide, news_client=None, budget=None, chroma_dir=None)
    assert out["history"][0]["outcome"].startswith("rejected: public-only organization")
    assert ran == ["Acme Corp latest annual results"]  # the company-coverage search ran; the CRM search did not


def test_relationship_searches_are_still_allowed_for_an_organization_with_records(monkeypatch):
    monkeypatch.setattr(provenance, "load_registry", lambda *a, **kw: {"acme": {"org_id": "acme", "name": NAME}})
    assert not company_context.public_only(bundle(ABOUT))
    assert company_context.relationship_query("Acme Corp CRM proposals correspondence")
    assert not company_context.relationship_query("Acme Corp shareholder meeting results")
    assert not company_context.relationship_query("Acme Corp headquarters contact page")


# --- 3. business unknowns and discovery questions --------------------------------------------------------------

def test_a_new_lead_gets_one_neutral_disclosure_of_what_the_evidence_does_not_establish():
    [u] = company_context.unknowns(bundle(ABOUT))
    assert u["id"] == "unknown:business" and u["kind"] == "gap"
    for part in ("systems Acme Corp uses today", "who at Acme Corp would evaluate or decide", "none is assumed",
                 "financial results"):
        assert part in u["text"]
    assert not re.search(r"\b(?:customer|deal|interested|interest in|budget|intends?|wants? to buy|opportunity)\b",
                         u["text"], re.I)


def test_an_existing_customer_gets_only_the_unknowns_its_evidence_raises():
    record = {"evidence_id": "PRP-1#1", "info_origin": "synthetic_record", "document_id": "PRP-1",
              "provenance_label": "SYNTHETIC", "text": "Proposal", "metadata": {"customer_org_id": "acme"}}
    customer = dict(relationship=[record], gaps=[])  # records found, so the research states no records gap
    [u] = company_context.unknowns(bundle(ALL, purpose="general", **customer))
    assert "uses today" not in u["text"] and "pending acquisition" in u["text"] and "16 September 2026" in u["text"]
    assert company_context.unknowns(bundle(ABOUT + RESULTS, purpose="general", **customer)) == []
    assert "discovery:buying_context" not in topics_of(bundle(ALL, purpose="general", **customer))


def test_unknowns_are_a_required_disclosure_that_the_draft_must_acknowledge():
    b = bundle(ABOUT + RESULTS)
    assert "unknown:business" in {d["id"] for d in required_disclosures(b)}
    d = valid(b, {"company_overview": [fact("Acme Corp says it is a global supplier of industrial valves (date not "
                                            "stated).", ["ACME-ABOUT#1"])]})
    assert validate_citations(d, b)["valid"]
    d["disclosures"] = [x for x in d["disclosures"] if x["id"] != "unknown:business"]
    assert "missing_disclosure" in {i["code"] for i in validate_citations(d, b)["issues"]}


def test_discovery_questions_must_cover_systems_decision_and_timing_in_the_recommendations():
    topic = [topics_of(bundle(ABOUT))["discovery:buying_context"]]
    good = rec("Ask which systems Acme uses today for drawings, who would evaluate or decide on such tools, and on "
               "what timing.")
    assert contract.coverage(draft(meeting_recommendations=[good]), topic)["topics"]["discovery:buying_context"] == \
        "communicated"
    narrow = contract.coverage(draft(meeting_recommendations=[rec("Ask how approval workflows run.")]), topic)
    assert narrow["topics"]["discovery:buying_context"] == "cited_only"
    assert narrow["missing_capabilities"]["discovery:buying_context"] == ["current systems", "timing"]
    elsewhere = draft(opportunities=[{**good, "kind": "inference"}])  # only the home section counts
    assert contract.coverage(elsewhere, topic)["topics"]["discovery:buying_context"] == "missing"


def test_a_pending_ownership_change_adds_a_neutral_discovery_question():
    t = topics_of(bundle(ALL))["discovery:ownership_change"]
    assert "pending acquisition" in t["requirement"] and "without assuming its outcome" in t["requirement"]
    assert "discovery:ownership_change" not in topics_of(bundle(ABOUT + RESULTS))


# --- 4. dates ----------------------------------------------------------------------------------------------------

def test_a_dated_official_release_within_the_news_window_may_be_a_recent_development(monkeypatch):
    b = bundle(ABOUT + RESULTS + OUTLOOK_OLD)

    def issues(eid):
        d = valid(b, {"recent_developments": [fact("Revenue amounted to EUR 1.2 billion.", [eid])]})
        return {i["code"] for i in validate_citations(d, b)["issues"]}
    assert "not_recent_evidence" not in issues("ACME-Q3#1")  # published 10 days ago (stated date)
    assert "not_recent_evidence" in issues("ACME-H1#1")  # 110 days ago
    assert "not_recent_evidence" in issues("ACME-ABOUT#1")  # undated
    monkeypatch.setattr(company_context, "ENABLED", False)
    assert "not_recent_evidence" in issues("ACME-Q3#1")  # the earlier rule, with I7 off


def test_a_news_copy_carries_the_publication_date_of_the_official_release_it_restates():
    b = bundle(ABOUT + RESULTS, news=[web("WEB-q3", "Revenue amounted to EUR 1.2 billion (1.1).")])
    prof = {e["evidence_id"]: e.get("profile", {}) for e in model_evidence(b)}
    assert prof["WEB-q3"]["restated_published"] == ago(10)
    assert prof["ACME-Q3#1"]["recent_official"] is True and "recent_official" not in prof["ACME-ABOUT#1"]


def test_anything_used_from_an_undated_page_must_say_date_not_stated():
    topics = [t for t in contract.essential_topics(bundle(ABOUT + RESULTS)) if t["id"].startswith("undated:page:")]
    assert [t["id"] for t in topics] == ["undated:page:ACME-ABOUT"] and topics[0]["conditional"]
    status = lambda text: contract.coverage(draft(company_overview=[fact(text, ["ACME-ABOUT#2"])]),  # noqa: E731
                                            topics)["topics"]["undated:page:ACME-ABOUT"]
    assert status("Acme has more than 4,000 employees.") == "cited_only"
    assert status("Acme has more than 4,000 employees (date not stated).") == "communicated"
    assert contract.coverage(draft(), topics)["topics"]["undated:page:ACME-ABOUT"] == "not_used"


# --- 5. news excerpts ---------------------------------------------------------------------------------------------

def test_a_short_news_text_is_kept_whole():
    text = "Acme Corp opened a plant in Lyon. Production starts in March 2027."
    assert company_context.bounded_excerpt(text, 50) == text


def test_a_dateline_is_split_off_so_the_excerpt_keeps_its_complete_sentences():
    body = ("Acme Corp announced today the launch of a new valve series for water utilities, further expanding its "
            "range across Europe and Asia and adding service centres in four regions. Built exclusively at its Lyon "
            "plant, the series is scheduled to ship in December 2026")
    line, rest = company_context.split_dateline(f"LYON, France, October 30, 2026 - {body}")
    assert line == "LYON, France, October 30, 2026 -" and rest == body
    assert company_context.bounded_excerpt(rest, 50) == body  # 48 words: complete, including the schedule
    ev = web_research.to_evidence({"url": "https://news.example/a", "content": f"LYON, France, October 30, 2026 - "
                                                                               f"{body}"},
                                  SimpleNamespace(org_id="acme", name=NAME), "last_30_days", "repeated_mention",
                                  __import__("datetime").datetime(2026, 11, 15), False)
    assert ev["dateline"] == line and ev["excerpt"] == body
    dates = chronology.event_dates({"source": "external_news", "excerpt": ev["excerpt"], "dateline": ev["dateline"]})
    assert dates == ["December 2026", "October 30, 2026"]  # the dateline's date counts as the release's own text


def test_a_long_news_text_keeps_whole_factual_sentences_and_marks_what_was_left_out():
    lead = "Acme Corp agreed to buy a pump maker for EUR 80 million in cash."
    filler = ("The company said the combination would bring together two teams with a shared commitment to quality "
              "and to the communities in which they work and live every day.")
    when = "The purchase is expected to close in March 2027."  # 51 words in all: one sentence must go
    out = company_context.bounded_excerpt(" ".join([lead, filler, when]), 50)
    assert out == f"{lead} … {when}" and len(out.split()) <= 50  # the dated, scheduled sentence wins over filler


def test_a_first_sentence_longer_than_the_bound_is_cut_and_marked():
    text = "Acme " + "word " * 80 + "end."
    out = company_context.bounded_excerpt(text, 50)
    assert out.endswith(" …") and len(out.split()) == 50


def test_an_ellipsis_already_in_the_source_is_kept_between_sentences():
    text = ("Acme Corp reported record orders of EUR 2 billion. " + "Filler sentence without data here. " * 10
            + "... Deliveries begin in 2027.")
    out = company_context.bounded_excerpt(text, 20)
    assert out == "Acme Corp reported record orders of EUR 2 billion. … Deliveries begin in 2027."


def test_with_i7_off_news_excerpts_are_cut_as_before(monkeypatch):
    monkeypatch.setattr(company_context, "ENABLED", False)
    text = "LYON, France, October 30, 2026 - " + "word " * 60
    assert web_research._excerpt(text) == " ".join(text.split()[:50]) and web_research._dateline(text) == {}


# --- 6. length -----------------------------------------------------------------------------------------------------

def test_the_drafting_policy_prefers_one_page_and_allows_a_second_for_important_content(monkeypatch):
    rules = briefing.system_rules()
    assert "one-page" not in rules and "You draft a concise meeting briefing" in rules
    assert "One page is preferred. Use a second page only to keep important content" in rules
    assert "about 45 words at most" in rules  # the I6 item limit is kept
    monkeypatch.setattr(company_context, "ENABLED", False)
    assert briefing.system_rules().startswith("You draft a one-page meeting briefing")  # I6 prompt, unchanged


def _pdf_result(n_company, n_recs):
    words = "Acme Corp says its newest release gives revenue of EUR 1.2 billion, published 5 November 2026, " \
            "and its order intake rose; the figures are attributed to that release and dated as it states them."
    b = {k: [] for k in pdf_export.SECTION_KEYS}
    b["company_overview"] = [fact(words, ["PUB#1"]) for _ in range(n_company)]
    b["opportunities"] = [{"kind": "inference", "text": "Hypothesis to verify: " + words, "evidence_ids": ["PUB#1"],
                           "claim_type": None}] * 2
    b["meeting_recommendations"] = [rec("Ask which systems Acme uses today, who decides on such tools and on what "
                                        "timing; do not assume a need or a purchase.", ["PUB#1"])] * n_recs
    unknown = company_context.unknowns(bundle(ABOUT))
    return {"created_at": CREATED, "identity": {"name": NAME}, "company_input": NAME, "purpose": "introduction",
            "labels": {"completeness": "complete", "market_intelligence": "current"}, "run_id": "test", "briefing": b,
            "disclosures": unknown, "section_notes": {}, "business_analysis": {"eligibility": []},
            "evidence": {"PUB#1": {"provenance_label": label(ago(10), "https://acme.example/q3"),
                                   "info_origin": "public_source"}}}


def test_a_typical_briefing_and_a_full_one_each_fit_two_readable_pages():
    # PDF presentation revised 2026-11-20: about 10 pt body type and natural pagination (no longer squeezed onto one page)
    _, typical = pdf_export.build_pdf(_pdf_result(2, 2))
    assert typical["pages"] <= 2 and typical["font_size"] >= pdf_export.MIN_FONT
    _, full = pdf_export.build_pdf(_pdf_result(6, 4))  # all company topics, two hypotheses, four questions
    assert full["pages"] <= 2 and full["font_size"] >= pdf_export.MIN_FONT


# --- 7. negative tests ------------------------------------------------------------------------------------------------

def test_no_requirement_asserts_a_relationship_a_need_or_an_intention_to_buy():
    topics = [t for t in contract.essential_topics(bundle(ALL)) if t["id"].startswith(("company:", "discovery:"))]
    text = " ".join(t["requirement"] for t in topics)
    assert not re.search(r"\b(?:customer|the deal|is interested|plans to buy|needs? (?:a|our|the))\b", text, re.I)
    assert all("do not imply a relationship, a need, a budget or an intention to buy" in t["requirement"]
               for t in topics if t["id"] == "discovery:buying_context")
    assert "never imply a relationship, a need, a budget or an intention to buy" in briefing.I7_RULES


def test_company_topics_require_no_product_claim_and_no_vendor_evidence():
    topics = [t for t in contract.essential_topics(bundle(ALL)) if t["id"].startswith(("company:", "discovery:"))]
    ids = {i for t in topics for g in t["groups"] for i in g}
    assert ids and all(i.startswith("ACME-") for i in ids)  # only the organization's own documents
    assert not re.search(r"Nivarque|product|tier|price", " ".join(t["requirement"] for t in topics))


def test_irrelevant_facts_are_not_required():
    topics = topics_of(bundle(ALL))
    assert len([t for t in topics if t.startswith("company:")]) <= 5
    assert "at most 3" in topics["company:latest_release"]["requirement"]
    assert "belong to them, not to Acme Corp" in topics["company:ownership"]["requirement"]
    assert not [t for t in topics_of(bundle(ABOUT + doc("ACME-OLD", ago(500), ["Acme Corp acquired Valvex Ltd."])))
                if t == "company:ownership"]  # an old transaction is not a current development


def test_with_i7_off_nothing_of_it_reaches_the_contract_or_the_disclosures(monkeypatch):
    monkeypatch.setattr(company_context, "ENABLED", False)
    b = bundle(ALL)
    assert not [t for t in topics_of(b) if t.startswith(("company:", "discovery:", "undated:page:"))]
    assert "unknown:business" not in {d["id"] for d in required_disclosures(b)}
    assert "recent_official" not in json.dumps(model_evidence(b))


# --- 8. genuine contradictions are still detected --------------------------------------------------------------------

def test_a_genuine_contradiction_is_still_contested_with_the_i7_profile():
    official = doc("ACME-P", ago(30), ["At the end of 2025, Acme operated 4 plants."])
    directory = doc("DIR-P", ago(20), ["At the end of 2025, Acme operated 5 plants."],
                    url="https://directory.example/acme", verification="single_secondary")
    entries = list(evidence_index(bundle(official + directory)).values())
    prof = ep.profile(entries, DOMAIN, as_of=TODAY)
    assert prof["ACME-P#1"]["contested_with"] == ["DIR-P#1"] and prof["DIR-P#1"]["contested_with"] == ["ACME-P#1"]
