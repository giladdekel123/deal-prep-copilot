"""C1 (owner-approved 2026-11-17): verify every figure a briefing states against the evidence its drafter received.

Replaces the value-only check behind business.figure_check (I5). A figure is checked for its value and, where both
the briefing and the evidence state them, for what it measures:
  - value: read with deal_prep.numbers (one reader for both sides; an ambiguous literal keeps all its readings and is
    reported, never silently normalized). A value matches when a reading equals an evidence reading (as written, or
    after an explicit scale: "1.5697 billion" = "1,569.7 million"), or when the same literal is written in the evidence;
  - currency (code or symbol: "EUR 1,569.7", "A$2.06bn", "List price (USD): 34"; "$" agrees with any dollar);
  - scale and unit (million or billion; percent, percentage points, GW, MW, TB ...);
  - metric (the nearest financial metric named before the figure in its clause: revenue, EBITDA, operating profit,
    profit, debt, investment, cost ...; profit and operating profit are not told apart);
  - reporting period (quarter, nine months, half and fiscal year with the same notation; an evidence clause without a
    period takes its document header's period, unless a comparison precedes the figure);
  - reported against expected ("reported", "was", "grew" ... against "expected", "guidance", "forecast", "will" ...;
    the noun "project(s)" is not a forecast word).
An attribute counts only when BOTH sides state it explicitly and they differ: a missing attribute is unverified, not a
problem, so an unusual phrasing cannot produce a false alarm. Results:
  - untraced: no evidence or analysis value matches (as before);
  - calculated_in_fact: a FACT item's figure that only the business analysis computes (as before);
  - mismatched: the value matches, but every matching evidence occurrence (the item's own citations first) states a
    different currency, scale, unit, metric, period or reported/expected meaning;
  - ambiguous: a figure matched through a reading that is not certain (recorded for audit, not a problem);
  - verified and attributes_checked: counts, for measurement.
Provenance (owner-approved 2026-11-17, after C2): a matching value is proof only where it is related to the item. A
figure is verified when it is found, with an agreeing meaning, in the item's own cited evidence; else in another
passage of a cited document; else in a business-analysis result calculated from evidence the item cites (or from a
cited document). A figure found only in evidence the item neither cites nor shares a document with, or only in an
analysis result the item does not cite, or only in analysis values with no recorded evidence, is weakly_traced: it is
reported distinctly, it is not a figure problem (no repair is asked to remove it, and a repair that drops it counts it
as lost), because a correct figure is never deleted merely because its trace is weak. The untraced, mismatched and
calculated_in_fact results are unchanged.
"""
import re

from deal_prep import numbers

TOLERANCE = 0.005  # two written values are equal within this (unchanged from I5)
_CODES = {"USD", "EUR", "DKK", "AUD", "GBP", "SEK", "NOK", "CHF", "JPY", "CAD", "NZD", "SGD", "HKD", "ILS", "NIS",
          "CNY", "INR", "ZAR", "BRL", "PLN"}
_SYMBOLS = {"A$": "AUD", "AU$": "AUD", "US$": "USD", "C$": "CAD", "NZ$": "NZD", "S$": "SGD", "HK$": "HKD", "€": "EUR",
            "£": "GBP", "₪": "ILS", "$": "$"}
_SYMBOL_BEFORE = re.compile(r"(A\$|AU\$|US\$|C\$|NZ\$|S\$|HK\$|\$|€|£|₪)\s?$")
_CODE_BEFORE = re.compile(r"\b([A-Z]{3})\)?:?\s?$")
_CODE_AFTER = re.compile(r"^\s?([A-Z]{3})\b")
_SCALE_AFTER = re.compile(r"^\s?(billion|bn|million|mn|thousand)\b", re.I)
_PERCENT = re.compile(r"^\s?(?:%|per ?cent\b|percent\b)", re.I)
_POINTS = re.compile(r"^\s?(?:percentage points?\b|pp\b|basis points?\b|bps?\b)", re.I)
_MEASURE = re.compile(r"^\s?(?:(?:billion|million|thousand|bn|mn)\s)?(GWh|MWh|GW|MW|TB|GB|PB|km|kg|tonnes?|TEUs?)\b")
_METRICS = (  # (family, pattern): the nearest one before a figure in its clause names what it measures
    ("ebitda", r"\bEBITDA\b"),
    ("operating", r"\boperating (?:profit|income|result|margin|earnings)\b|\bEBITA?\b"),
    ("profit", r"\bnet (?:profit|income|earnings|loss|result)\b|\bprofits? (?:before|after) tax\b|\bprofits?\b|"
               r"\bearnings\b|\bPBT\b|\bPAT\b|\blosses\b"),
    ("revenue", r"\brevenues?\b|\bnet sales\b|\bsales\b|\bturnover\b"),
    ("debt", r"\bnet (?:interest-bearing )?debt\b|\bdebt\b|\bleverage\b"),
    ("investment", r"\bcapital expenditure\b|\bcapex\b|\binvestments?\b"),
    ("dividend", r"\bdividends?\b"),
    ("buyback", r"\bbuy-?backs?\b|\brepurchased?\b|\bshare repurchases?\b"),
    ("cash_flow", r"\bcash flows?\b"),
    ("impairment", r"\bimpairments?(?: losses)?\b"),
    ("orders", r"\border (?:intake|bookings|backlog)\b|\bbacklog\b|\bbookings\b"),
    ("headcount", r"\bemployees\b|\bstaff\b|\bworkforce\b|\bheadcount\b"),
    ("cost", r"\bcosts?\b|\bexpenses?\b|\bexpenditure\b"),
)
_COMPATIBLE_METRICS = {frozenset({"profit", "operating"})}
_YEAR = r"((?:19|20)\d{2})"
_PERIODS = (  # (kind, pattern, how to normalize): compared only within the same kind (same notation)
    ("quarter", re.compile(rf"\b(?:Q([1-4])|(first|second|third|fourth)[- ]quarter)(?:\s+of)?[\s,]+(?:FY\s?)?{_YEAR}\b",
                           re.I)),
    ("nine_months", re.compile(rf"\b(?:9M|nine[- ]months?|first nine months)(?:\s+of)?[\s,]+{_YEAR}\b", re.I)),
    ("half", re.compile(r"\b(?:([12])H\s?(\d{2})|H([12])\s?(\d{2}|(?:19|20)\d{2}))\b")),
    ("fiscal_year", re.compile(r"\bFY\s?(\d{2}|(?:19|20)\d{2})\b")),
)
_ORDINAL = {"first": "1", "second": "2", "third": "3", "fourth": "4"}
_COMPARISON = re.compile(r"\b(?:(?:up|down|rose|fell|increased|decreased|grew|declined) from|compared (?:with|to)|"
                         r"against|versus|vs\.?|prior|previous|last year|same period|a year earlier|year-on-year|"
                         r"year-over-year)\b", re.I)  # a comparison before a figure: it may belong to another period
_FORECAST = re.compile(r"\b(?:expects?|expected|expecting|forecasts?|forecasted|guidance|outlook|anticipates?|"
                       r"anticipated|targets?|targeted|aims? to|plans? to|will|projected|projecting|projections?|"
                       r"is set to|on track to|estimated to)\b", re.I)
_ACTUAL = re.compile(r"\b(?:reported|recorded|was|were|amounted|totall?ed|grew|rose|fell|increased|decreased|declined|"
                     r"achieved|delivered|generated|came in)\b", re.I)
_BOUNDARY = re.compile(r"[;!?\n]|\.(?=\s|$)")


def _clause(text: str, start: int, end: int) -> tuple[int, int]:
    """The clause (between ';', '!', '?', a line break or a full stop followed by a space) around a span."""
    left = max((m.end() for m in _BOUNDARY.finditer(text, 0, start)), default=0)
    right = next((m.start() for m in _BOUNDARY.finditer(text, end)), len(text))
    return left, right


def _masked(text: str) -> str:
    """The text with dates and identifiers blanked out, positions kept (they are not figures)."""
    from deal_prep.contract import _DATE, _ID
    blank = lambda m: " " * len(m.group(0))  # noqa: E731
    return _ID.sub(blank, _DATE.sub(blank, text or ""))


def currency(text: str, start: int, end: int, suffix: str = "") -> str:
    before = text[max(0, start - 10):start]
    if before[-1:] in ("-", "−", "–"):  # a minus sign sits between the currency and the figure
        before = before[:-1]
    s = _SYMBOL_BEFORE.search(before)
    if s:
        return _SYMBOLS[s.group(1)]
    c = _CODE_BEFORE.search(before)
    if c and c.group(1) in _CODES:
        return c.group(1)
    a = _CODE_AFTER.match(text[end + len(suffix):end + len(suffix) + 6])
    return a.group(1) if a and a.group(1) in _CODES else ""


def scale(text: str, end: int, suffix: str = "") -> float:
    if suffix in numbers.SCALE:
        return numbers.SCALE[suffix]
    m = _SCALE_AFTER.match(text[end + len(suffix):end + len(suffix) + 12])
    return numbers.SCALE[m.group(1).casefold()] if m else 1.0


def unit(text: str, end: int, suffix: str = "") -> str:
    after = text[end + len(suffix):end + len(suffix) + 40]
    if _PERCENT.match(after):
        return "percent"
    if _POINTS.match(after):
        return "points"
    m = _MEASURE.match(after)
    return re.sub(r"s$", "", m.group(1).casefold()) if m else ""


def metric(text: str, start: int, clause_start: int) -> str:
    before, best = text[clause_start:start], None
    for family, pattern in _METRICS:
        for m in re.finditer(pattern, before, re.I):
            key = (m.end(), m.end() - m.start())  # the nearest; at the same place, the longest ("operating profit")
            if best is None or key > best[0]:
                best = (key, family)
    return best[1] if best else ""


def periods(text: str) -> dict[str, set]:
    out: dict[str, set] = {}
    for kind, pattern in _PERIODS:
        for m in pattern.finditer(text):
            g = [x for x in m.groups() if x]
            if kind == "quarter":
                key = (_ORDINAL.get(g[0].casefold(), g[0]), g[-1])
            elif kind == "half":
                key = (g[0], g[1])
            else:
                key = (g[-1],)
            sub = kind if kind not in ("half", "fiscal_year") else f"{kind}_{len(key[-1])}"
            out.setdefault(sub, set()).add(key)
    return out


def tense(clause: str) -> str:
    f, a = bool(_FORECAST.search(clause)), bool(_ACTUAL.search(clause))
    return "expected" if f and not a else "reported" if a and not f else ""


def context(text: str, n, header_periods: dict | None = None) -> dict:
    """What a figure measures, as its own text states it."""
    cs, ce = _clause(text, n.start, n.end)
    clause = text[cs:ce]
    own = periods(clause)
    if not own and header_periods and not _COMPARISON.search(text[cs:n.end]):
        own = header_periods  # the document's period dates a figure its clause does not date
    return {"currency": currency(text, n.start, n.end, n.suffix), "scale": scale(text, n.end, n.suffix),
            "scale_stated": scale(text, n.end, n.suffix) != 1.0, "unit": unit(text, n.end, n.suffix),
            "metric": metric(text, n.start, cs), "periods": own, "tense": tense(clause),
            "clause": " ".join(clause.split())[:300]}


def _currency_conflict(a: str, b: str) -> bool:
    if not a or not b or a == b:
        return False
    return not ("$" in (a, b) and (a.endswith("D") or b.endswith("D")))


def conflicts(b: dict, e: dict) -> list[str]:
    """The attributes both state and that differ."""
    out = []
    if _currency_conflict(b["currency"], e["currency"]):
        out.append("currency")
    bu, eu = b["unit"], e["unit"]
    if bu and eu and bu != eu:
        out.append("unit")
    elif ("percent" in (bu, eu) or "points" in (bu, eu)) and bu != eu:
        other = e if bu in ("percent", "points") else b
        if other["currency"] or other["unit"]:
            out.append("unit")
    if b["metric"] and e["metric"] and b["metric"] != e["metric"] \
            and frozenset({b["metric"], e["metric"]}) not in _COMPATIBLE_METRICS:
        out.append("metric")
    shared = set(b["periods"]) & set(e["periods"])
    if any(not (b["periods"][k] & e["periods"][k]) for k in shared):
        out.append("period")
    if b["tense"] and e["tense"] and b["tense"] != e["tense"]:
        out.append("reported_or_expected")
    return out


def _value_match(bn, bc: dict, en, ec: dict) -> str:
    """'match', 'scale' (the same digits at an explicitly different scale) or '' (no match)."""
    if bn.literal == en.literal and bn.negative == en.negative and bn.suffix == en.suffix:
        return "scale" if bc["scale_stated"] and ec["scale_stated"] and bc["scale"] != ec["scale"] else "match"
    for vb in bn.values:
        for ve in en.values:
            if abs(vb - ve) <= TOLERANCE + 1e-9:
                if bc["scale_stated"] and ec["scale_stated"] and bc["scale"] != ec["scale"]:
                    return "scale"
                return "match"
            if (bc["scale_stated"] or ec["scale_stated"]) and \
                    abs(vb * bc["scale"] - ve * ec["scale"]) <= 1e-9 * max(1.0, abs(vb * bc["scale"])):
                return "match"
    return ""


class _Evidence:
    """The numbers of every evidence passage, each with its context, read once."""

    def __init__(self, evidence: dict[str, dict]):
        from deal_prep import evidence_profile as ep
        self.texts = {eid: e.get("text") or "" for eid, e in evidence.items()}
        self.docs = {eid: e.get("document_id") or eid for eid, e in evidence.items()}
        headers: dict[str, dict] = {}
        for eid, e in evidence.items():
            if ep.statement_form(e.get("entry") or {}) == "document_header":
                for k, v in periods(self.texts[eid]).items():
                    headers.setdefault(self.docs[eid], {}).setdefault(k, set()).update(v)
        self.numbers: dict[str, list] = {}
        for eid, text in self.texts.items():
            doc = self.docs[eid]
            same_doc = [t for j, t in self.texts.items() if j != eid and self.docs[j] == doc]  # the source's style
            nums = [n for n in numbers.read(_masked(text), same_doc) if not numbers.is_year(n.literal)]
            self.numbers[eid] = [(n, context(text, n, headers.get(doc))) for n in nums]

    def style_context(self, ids) -> list[str]:
        docs = {self.docs[i] for i in ids if i in self.docs}
        return [t for i, t in self.texts.items() if self.docs[i] in docs]


def prepare(evidence: dict[str, dict]) -> "_Evidence":
    """The evidence read once, for checking several drafts against the same evidence."""
    return _Evidence(evidence)


_IDENTIFIER = re.compile(r"(?:^|_)(?:id|about|evidence_ids?)$")


def analysis_values(x, ids: frozenset = frozenset()) -> list[tuple[float, frozenset]]:
    """The values of the business analysis, each with the evidence it was calculated from: a value inside a result
    (at any depth) that records its evidence IDs carries them; a value outside every such result (the analysis date)
    has none, so its provenance is not established. Identifiers (evidence IDs, result IDs) are not values."""
    from deal_prep.business import _numbers
    if isinstance(x, dict):
        own = set(x.get("evidence_ids") or []) | ({x["evidence_id"]} if isinstance(x.get("evidence_id"), str)
                                                  else set())
        ids = ids | frozenset(own)
        return [v for k, y in x.items() if not _IDENTIFIER.search(str(k)) for v in analysis_values(y, ids)]
    if isinstance(x, list):
        return [v for y in x for v in analysis_values(y, ids)]
    if isinstance(x, bool):
        return []
    if isinstance(x, (int, float)):
        return [(float(x), ids)]
    if isinstance(x, str):
        return [(v, ids) for v in _numbers(x)]
    return []


def verify(draft: dict, evidence: dict[str, dict], analysis=None, prepared: "_Evidence | None" = None) -> dict:
    """evidence: evidence_id -> {"text": what the check reads, "document_id", "entry": the evidence entry}."""
    from deal_prep.business import _walk_numbers
    ev = prepared or _Evidence(evidence)
    computed = _walk_numbers(analysis) if analysis else set()
    sourced = analysis_values(analysis) if analysis else []
    out = {"untraced": [], "calculated_in_fact": [], "mismatched": [], "ambiguous": [], "weakly_traced": [],
           "verified": 0, "verified_figures": [],
           "attributes_checked": {k: 0 for k in ("currency", "scale", "unit", "metric", "period",
                                                 "reported_or_expected")}}
    for section, items in draft["sections"].items():
        for i, item in enumerate(items):
            text = item["text"]
            cited = [e for e in item.get("evidence_ids", []) if e in ev.numbers]
            cited_docs = {ev.docs[e] for e in cited}

            def tier(eid):  # 0: a cited passage; 1: another passage of a cited document; 2: unrelated evidence
                return 0 if eid in cited else 1 if ev.docs.get(eid) in cited_docs else 2

            def related(ids):  # an analysis result calculated from cited evidence or a cited document
                return bool(ids & set(cited)) or bool({ev.docs.get(j, j) for j in ids} & cited_docs)
            for bn in numbers.read(_masked(text), ev.style_context(cited)):
                if numbers.is_year(bn.literal):
                    continue
                where = {"section": section, "item": i, "figure": bn.literal}
                bc = context(text, bn)
                matches, scale_only = [], []
                for eid, nums in ev.numbers.items():
                    for en, ec in nums:
                        kind = _value_match(bn, bc, en, ec)
                        if kind == "match":
                            matches.append((eid, en, ec))
                        elif kind == "scale":
                            scale_only.append((eid, en, ec))
                in_computed = any(abs(v - c) <= TOLERANCE + 1e-9 for v in bn.values for c in computed)
                own = [m for m in matches if m[0] in cited]
                if not matches and not in_computed:
                    if scale_only:
                        eid, en, ec = scale_only[0]
                        out["mismatched"].append({**where, "attributes": ["scale"], "evidence_id": eid,
                                                  "evidence": ec["clause"]})
                    else:
                        out["untraced"].append(where)
                    continue
                if item["kind"] == "fact" and not own and in_computed:
                    out["calculated_in_fact"].append(where)
                    continue
                in_analysis = [ids for v, ids in sourced if any(abs(b - v) <= TOLERANCE + 1e-9 for b in bn.values)]
                by_analysis = any(related(ids) for ids in in_analysis)
                pool = own or matches
                if not pool:  # matched by the business analysis only
                    entry = {**where, "values": list(bn.values), "checked": [], "evidence_id": None}
                    if by_analysis:
                        out["verified"] += 1
                        out["verified_figures"].append({**entry, "trace": "analysis"})
                    else:
                        out["weakly_traced"].append({**entry, "basis": "analysis_not_cited" if any(in_analysis)
                                                     else "analysis_without_evidence", "item_cites": bool(cited)})
                    continue
                verdicts = [(conflicts(bc, ec), eid, en, ec) for eid, en, ec in pool]
                ok = sorted((v for v in verdicts if not v[0]), key=lambda v: tier(v[1]))
                if ok:
                    _, eid, en, ec = ok[0]
                    checked = [k for k in out["attributes_checked"] if _stated_both(k, bc, ec)]
                    entry = {**where, "values": list(bn.values), "checked": checked, "evidence_id": eid}
                    if tier(eid) < 2:
                        out["verified"] += 1
                        out["verified_figures"].append({**entry, "trace": ("cited", "same_document")[tier(eid)]})
                        for k in checked:
                            out["attributes_checked"][k] += 1
                    elif by_analysis:  # the proof is the analysis result; the unrelated occurrence is not
                        out["verified"] += 1
                        out["verified_figures"].append({**entry, "checked": [], "evidence_id": None,
                                                        "trace": "analysis"})
                    else:  # the value is stated only in evidence unrelated to the item: not proof
                        out["weakly_traced"].append({**entry, "basis": "unrelated_evidence",
                                                     "evidence_document": ev.docs.get(eid), "item_cites": bool(cited)})
                    if (bn.ambiguous or en.ambiguous) and bn.literal != en.literal:
                        out["ambiguous"].append({**where, "evidence_id": eid, "evidence_figure": en.literal,
                                                 "readings": list(bn.values)})
                else:
                    found, eid, en, ec = min(verdicts, key=lambda v: len(v[0]))
                    out["mismatched"].append({**where, "attributes": found, "evidence_id": eid,
                                              "evidence": ec["clause"]})
    return out


def _stated_both(k: str, b: dict, e: dict) -> bool:
    if k == "period":
        return bool(set(b["periods"]) & set(e["periods"]))
    if k == "scale":
        return b["scale_stated"] and e["scale_stated"]
    key = "tense" if k == "reported_or_expected" else k
    return bool(b[key] and e[key])
