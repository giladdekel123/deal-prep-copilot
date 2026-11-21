"""C2.1: the noun "project(s)" is not forecasting language; genuine forecasting language still is. Historical statements
that mention projects are results; real forecasts stay forecasts. The conflict profile and the conflict safeguard keep
their verdicts on every stored development draft (tests/test_dev_replay.py)."""
import pytest

from deal_prep import evidence_profile as ep

HISTORICAL = [
    "Profit for the period was DKK 2.6 billion, mainly due to non-cash impairments on our US projects.",
    "One of the world's leading construction and project development groups, we operate in select markets.",
    "In October the project achieved commercial operations under its offtake contracts.",
    "With the commissioning of the two projects, our installed capacity has now increased to 11.8 GW.",
    "Unit: per project (fixed fee) | Proposed price (USD): 80000",
    "The project to build the plant was completed in March 2026.",
    "Revenue rose 12% as large projects were delivered on time.",
]
FORECASTS = [
    "We project revenue of EUR 1.2 billion for 2027.",
    "The company projects that margins will improve.",
    "Management now projects EBITDA of EUR 340 million.",
    "Revenue is projected to reach EUR 2 billion by 2028.",
    "Our projections show double-digit growth.",
    "The Group expects to deliver growth of 5 to 7 per cent.",
    "The 1H27 fuel cost is now expected to be approximately $3.75 billion.",
    "The company maintains its full-year guidance.",
    "We target EUR 1 billion in revenue by 2030.",
    "The Group will take delivery of up to 31 new aircraft.",
    "The outlook for 2026 is unchanged.",
]


@pytest.mark.parametrize("sentence", HISTORICAL)
def test_historical_statements_mentioning_projects_are_not_forecasts(sentence):
    assert not ep._FORWARD.search(sentence)


@pytest.mark.parametrize("sentence", FORECASTS)
def test_genuine_forecasting_language_is_still_recognized(sentence):
    assert ep._FORWARD.search(sentence)


def test_a_profit_statement_about_projects_now_counts_as_a_dated_result():
    """The latest-results selection no longer drops a result because it mentions projects."""
    from datetime import date, timedelta
    from deal_prep import company_context
    published = (date(2026, 11, 15) - timedelta(days=10)).isoformat()
    label = (f"PUBLIC SOURCE · Acme Corp · https://acme.example/q3 · published {published} · retrieved 2026-11-15 · "
             f"verification primary")
    text = 'Excerpts > [E1] "Profit for the period was EUR 2.6 billion, down EUR 3.9 billion, due to impairments on US ' \
           'projects."'
    entry = {"evidence_id": "Q3#1", "document_id": "Q3", "info_origin": "public_source", "provenance_label": label,
             "excerpt": text, "text": text, "metadata": {}}
    bundle = {"identity": {"name": "Acme Corp", "domain": "acme.example"}, "created_at": "2026-11-15T10:00:00+00:00",
              "internal": {"company_profile": {"evidence": [entry]}}}
    assert [s["eid"] for s in company_context.analyse(bundle)["results"]] == ["Q3#1"]
