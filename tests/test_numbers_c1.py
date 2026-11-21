"""C1: one number reader for evidence and briefings (deal_prep.numbers). Decimal and thousands separators, negative
values, attached scales, dates and identifiers, and ambiguous formats read from their source's context, never silently
normalized."""
import re

import pytest

from deal_prep import contract, numbers


def one(text, context=()):
    found = [n for n in numbers.read(text, context) if not numbers.is_year(n.literal)]
    assert len(found) == 1, found
    return found[0]


@pytest.mark.parametrize("text, value, decimals", [
    ("revenue of EUR 1,569.7 million", 1569.7, 1),   # thousands and decimals together (the v2 defect)
    ("adjusted operating profit 1,052.9", 1052.9, 1),
    ("revenue 6,466.4 in 2025", 6466.4, 1),
    ("12,345,678 shares", 12345678.0, 0),
    ("EUR 1569.7 million", 1569.7, 1),
    ("DKK 20.2 billion", 20.2, 1),
    ("A$3.75 billion", 3.75, 2),
    ("up 10.1% year-on-year", 10.1, 1),
    ("85 per cent hedged", 85.0, 0),
    ("DKK 17.0 billion", 17.0, 1),
])
def test_unambiguous_figures_are_read_exactly(text, value, decimals):
    n = one(text)
    assert n.readings == ((value, decimals),) and not n.ambiguous


def test_the_v2_defect_is_gone_the_briefing_side_reads_the_whole_figure():
    assert contract.figures("reported revenue of EUR 1,569.7 million, up 10.1%") == ["1,569.7", "10.1"]
    assert contract.figures("adjusted operating profit of 1,052.9") == ["1,052.9"]


@pytest.mark.parametrize("text, value", [
    ("Profit for the period was DKK -0.7 billion in Q3 2026", -0.7),
    ("a loss of −0.7 billion", -0.7),
    ("(-12.5)", -12.5),
])
def test_a_minus_sign_before_a_figure_makes_it_negative(text, value):
    n = [x for x in numbers.read(text) if x.literal != "2026"][0]
    assert n.negative and n.values == (value,)


@pytest.mark.parametrize("text", ["the 2025-26 financial year", "DKK 45-50 billion", "DKK 45–50 billion"])
def test_a_hyphen_between_numbers_is_a_range_not_a_minus(text):
    assert not any(n.negative for n in numbers.read(text))


@pytest.mark.parametrize("text, literal, suffix", [
    ("EUR 68m", "68", "m"), ("A$2.06bn", "2.06", "bn"), ("leverage of 1.5x", "1.5", "x"), ("100k users", "100", "k")])
def test_an_attached_scale_or_multiple_is_read_as_a_suffix(text, literal, suffix):
    n = one(text)
    assert (n.literal, n.suffix) == (literal, suffix)


@pytest.mark.parametrize("text", ["Q3 2026", "FY26", "1H27", "9M 2026", "NVQ-PUB-BV-01#1", "the 21.10.2026 meeting",
                                  "time-stamped 07:30 CEST", "a 3:1 ratio"])
def test_periods_identifiers_and_malformed_literals_are_not_figures(text):
    assert contract.figures(text) == []


def test_years_and_dates_are_not_figures():
    assert contract.figures("On 21 October 2026, in 2025 and 2026") == []


def test_a_full_stop_or_comma_after_a_figure_is_not_part_of_it():
    assert contract.figures("It was 85. Then 7,200, and 3.75.") == ["3.75", "7,200", "85"]


@pytest.mark.parametrize("literal", ["1,569", "1.569", "7,200"])
def test_a_literal_the_two_styles_read_differently_is_ambiguous_without_context(literal):
    n = one(f"an index value of {literal} overall")
    assert n.ambiguous and len(n.values) == 2  # every reading kept; never normalized to one


@pytest.mark.parametrize("text, value", [("about 4,250 employees", 4250.0), ("1,050 users", 1050.0),
                                         ("4,250 full-time employees", 4250.0), ("7,200 people", 7200.0)])
def test_a_count_of_whole_things_settles_an_ambiguous_literal(text, value):
    n = one(text)
    assert (n.values, n.ambiguous) == ((value,), False)


def test_a_scale_word_makes_it_an_amount_not_a_count():
    assert one("1,569 million people").ambiguous


def test_the_texts_own_style_resolves_an_ambiguous_literal():
    en = [n for n in numbers.read("Revenue 1,569 million, margin 16.3%") if n.literal == "1,569"][0]
    eu = [n for n in numbers.read("Umsatz 1,569 Mio., Marge 16,3 %") if n.literal == "1,569"][0]
    assert (en.values, en.ambiguous) == ((1569.0,), False)
    assert (eu.values, eu.ambiguous) == ((1.569,), False)


def test_the_source_documents_other_texts_resolve_an_ambiguous_literal():
    n = one("approximately 7,200 people", context=["EBITDA grew to DKK 20.2 billion"])
    assert (n.values, n.ambiguous) == ((7200.0,), False)
    n = one("approximately 7,200 people", context=["Umsatz 6.466,4 Mio."])
    assert (n.values, n.ambiguous) == ((7.2,), False)


def test_a_continental_literal_is_read_continentally_and_flagged_in_an_english_text():
    assert one("Umsatz 1.569,7 Mio.").values == (1569.7,)
    flagged = [n for n in numbers.read("growth of 6,2% against 20.2 last year") if n.literal == "6,2"][0]
    assert flagged.values == (6.2,) and flagged.ambiguous  # its only reading contradicts the text's style


def test_the_style_of_a_set_of_texts():
    assert numbers.style_of(["DKK 20.2 billion", "7,200 people"]) == "en"
    assert numbers.style_of(["6.466,4 Mio."]) == "eu"
    assert numbers.style_of(["7,200 people"]) is None  # ambiguous literals show no style
    assert numbers.style_of(["20.2 and 6,2"]) == "mixed"


@pytest.mark.parametrize("literal, matches, rejects", [
    ("1,569.7", ["EUR 1,569.7 million", "EUR 1569.7 million"], ["1,569", "1,569.75", "11,569.7", "1,596.7"]),
    ("20.2", ["DKK 20.2 billion"], ["120.2", "20.25", "20"]),
    ("85", ["85 per cent", "85%"], ["185", "85.5"]),
])
def test_a_coverage_marker_matches_the_same_figure_with_or_without_separators(literal, matches, rejects):
    m = numbers.marker(literal)
    assert all(re.search(m, t) for t in matches)
    assert not any(re.search(m, t) for t in rejects)


def test_an_ambiguous_literals_marker_matches_only_the_literal_itself():
    m = numbers.marker("7,200")
    assert re.search(m, "7,200 people") and not re.search(m, "7200 people")
    assert numbers.marker("7,200", "en") != m  # with its source's style it is certain


def test_values_include_every_reading_and_the_scaled_value_of_an_attached_scale():
    assert numbers.values("EUR 68m") == {68.0, 68_000_000.0}
    assert numbers.values("an index of 1,050 overall") == {1050.0, 1.05}  # ambiguous: both readings, none chosen
    assert numbers.values("about 1,050 users") == {1050.0}  # a count settles it
