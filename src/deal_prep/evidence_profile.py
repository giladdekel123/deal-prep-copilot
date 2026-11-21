"""Evidence profile (Phase 4.5, I2): source class, statement form, date status and contested figures.

Pure, company-independent rules over the sanitized evidence the drafters already receive (evidence ID, origin,
source, provenance label, excerpt, time window). Nothing is invented: a field the evidence does not support is
"unknown". The profile is used by the offline template now; sending it to the live model is checkpoint CP-2.

Also: detection of stock-quote and market-data pages, which are not news (used by web_research).
"""
import re

# --- quote and market-data pages (not news) -------------------------------------------------------

_PRICE_CHANGE = re.compile(r"\b\d+(?:\.\d+)?\s+[+-]?\d+(?:\.\d+)?\s+\([+-]?\d+(?:\.\d+)?%\)")
_DATA_WORDS = re.compile(r"\b(?:delayed quote|stock quote|share price|historical prices|market cap(?:italization)?|"
                         r"at close|pre-market|after hours|52[- ]week (?:high|low)|dividend yield|stock price)\b", re.I)
_DATA_URL = re.compile(r"/(?:quote|quotes|stock|stocks|symbol|market-data|historical-prices)(?:/|$|\?)|"
                       r"^https?://(?:[^/]*\.)?(?:quotes?|markets?|finance)[.-]", re.I)


def is_data_page(title: str, url: str, content: str, undated: bool = False) -> bool:
    """A stock-quote or market-data page: a price-change figure, two market-data terms, or a quote URL plus one
    market-data term. Ordinary news that mentions a share price once does not qualify. I3: an undated page on a
    quote or market-data URL is a data listing too (no date, so not an article; nothing on it is news)."""
    text = f"{title} {content}"
    words = len(_DATA_WORDS.findall(text))
    data_url = bool(_DATA_URL.search(url or ""))
    return bool(_PRICE_CHANGE.search(text)) or words >= 2 or (data_url and (words >= 1 or undated))


# --- profile of one sanitized evidence entry --------------------------------------------------------

_VERIFICATION = re.compile(r"verification (\w+)")
_PUBLISHED = re.compile(r"published (\S+)")
_URL = re.compile(r"https?://[^\s·]+")


def _host(url: str) -> str:
    m = re.match(r"https?://([^/:?#\s]+)", url or "")
    return (m.group(1).casefold().removeprefix("www.") if m else "")


def on_company_domain(e: dict, company_domain: str | None) -> bool | None:
    """True / False when the source URL can be compared with the company's official domain; None when either is
    unknown (ownership is then not established)."""
    m = _URL.search(e.get("provenance_label") or "")
    domain = (company_domain or "").casefold().removeprefix("www.").strip()
    if not m or not domain:
        return None
    host = _host(m.group(0))
    return host == domain or host.endswith("." + domain)


OFFICIAL_CLASSES = ("official_company_source", "company_announcement")


def source_class(e: dict, company_domain: str | None = None) -> str:
    """official_company_source: a primary source on the company's own domain. primary_third_party: a primary source
    elsewhere (for example a regulator): authoritative for what it records, but not the company's own statement.
    primary_source: primary, owner not established (no known company domain). secondary_profile: an aggregator or
    directory. news / company_announcement: web news, by whether it is on the company's own domain."""
    if e["evidence_id"].startswith("HIST-"):
        return "meeting_record"
    if e.get("info_origin") == "synthetic_record":
        return "internal_record"
    own = on_company_domain(e, company_domain)
    if e.get("source") == "external_news" or e["evidence_id"].startswith("WEB-"):
        return "company_announcement" if own else "news"
    v = _VERIFICATION.search(e.get("provenance_label") or "")
    if v and v.group(1) == "primary":
        return {True: "official_company_source", False: "primary_third_party", None: "primary_source"}[own]
    return "secondary_profile" if v else "unknown"


def statement_form(e: dict) -> str:
    text = (e.get("excerpt") or "").lstrip()
    if re.match(r"(?:Excerpts\s*>\s*)?\[E\d+\]\s*\"", text):
        return "verbatim_excerpt"
    if re.match(r"Claims\b", text):
        return "claims_summary"
    if text.startswith(("PUBLIC SOURCE", "SYNTHETIC")):
        return "document_header"
    return "passage"


def date_status(e: dict) -> str:
    m = _PUBLISHED.search(e.get("provenance_label") or "")
    if not m or m.group(1) in ("unknown", "undated"):
        return "publication_date_unknown"
    return "publication_date_provider_estimate" if e["evidence_id"].startswith("WEB-") else "publication_date_stated"


# --- contested and restated figures across sources -------------------------------------------------

_NUM = re.compile(r"\d[\d,]*(?:\.\d+)?")
# Reporting periods and dates stated in a sentence: a full date, a quarter, half or fiscal year, a month and year,
# or a year (a plain number from 1600 to 2099 is read as a year).
_MONTH = (r"(?:jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|june?|july?|aug(?:ust)?|sep(?:t(?:ember)?)?|"
          r"oct(?:ober)?|nov(?:ember)?|dec(?:ember)?)\.?")
_YEAR = r"(?:1[6-9]|20)\d{2}"
_PERIOD = re.compile(rf"\b(?:{_MONTH}\s+\d{{1,2}},?\s+{_YEAR}|\d{{1,2}}\s+{_MONTH},?\s+{_YEAR}|"
                     rf"{_YEAR}-\d{{2}}-\d{{2}}|(?:q[1-4]|h[12]|fy)\s?-?\s?{_YEAR}|{_MONTH}\s+{_YEAR}|{_YEAR})\b", re.I)
# Forward-looking statements (guidance, expectations, plans): a later one updates an earlier one.
# C2 (owner-approved 2026-11-17): "project" is a forecast word only as a verb ("we project", "the company projects that",
# "projected", "projections"); the noun ("US projects", "project development", "per project") is not.
_FORWARD = re.compile(r"\b(?:expects?|expected|expecting|guidance|outlook|forecasts?|forecasted|projected|projecting|"
                      r"projections?|projects? that|(?:we|it|they|management|the (?:company|group|board)) "
                      r"(?:now |also )?projects?|anticipates?|anticipated|targets?|targeted|aims? to|plans? to|will)\b",
                      re.I)
# A figure stated as a bound ("more than 25,000", "214+", "up to 40"): two bounds in the same direction never
# contradict each other.
_BOUND_BEFORE = re.compile(r"\b(?:more than|over|at least|in excess of|upwards of|above|up to|less than|fewer than|"
                           r"under|at most|no more than|below)\s*(?:[$€£]|sek|usd|eur|ils)?\s*$", re.I)


def document_key(e: dict) -> str:
    """The document an evidence entry comes from; a web result (no document ID) is its own document."""
    return e.get("document_id") or e["evidence_id"]


def recent_official(e: dict, as_of, days: int) -> bool:
    """I7: a public document (not a web result) whose stated publication date is at most `days` before as_of."""
    from datetime import date
    if e.get("info_origin") != "public_source" or e["evidence_id"].startswith("WEB-") \
            or date_status(e) != "publication_date_stated":
        return False
    day = publication_day(e)
    return day is not None and 0 <= (as_of - date.fromisoformat(day)).days <= days


def publication_day(e: dict) -> str | None:
    """The stated or provider-estimated publication day (YYYY-MM-DD), or None when unknown."""
    m = _PUBLISHED.search(e.get("provenance_label") or "")
    value = m.group(1) if m else ""
    return value[:10] if re.match(r"\d{4}-\d{2}-\d{2}", value) else None


def _norm_period(p: str) -> str:
    p = re.sub(r"[.,]", " ", p.casefold()).replace("-", " ")
    p = re.sub(r"\b(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*", r"\1", p)
    return " ".join(p.split())


def _parse(sentence: str) -> dict:
    """A statement's frame (its wording with figures masked: what is measured, and its scope, including any named
    organization), the reporting periods it states, its figures, and which figures are stated as bounds. When its
    only numbers are dates or years, those are what it states (for example a founding year)."""
    periods = [_norm_period(m.group(0)) for m in _PERIOD.finditer(sentence)]
    rest = _PERIOD.sub(" § ", sentence)
    dates_only = not _NUM.search(rest)
    text, periods = (sentence, []) if dates_only else (rest, periods)
    nums = list(_NUM.finditer(text))
    return {"frame": " ".join(_NUM.sub("#", text).casefold().split()), "periods": periods,
            "figures": [m.group(0) for m in nums], "dates_only": dates_only,
            "bounded": [bool(_BOUND_BEFORE.search(text[max(0, m.start() - 25):m.start()]))
                        or text[m.end():m.end() + 1] == "+" for m in nums]}


def _different_time(e: dict, a: dict, o: dict, frame: str) -> bool:
    """Two statements published on different days may describe different moments: a forward-looking statement is
    updated by the later one, and a figure that changes over time (not a date or year alone) stated without an
    explicit period describes the situation when it was published. Unknown publication days are not different."""
    de, do = publication_day(e), publication_day(o)
    if not de or not do or de == do:
        return False
    return bool(_FORWARD.search(frame)) or (not a["periods"] and not a["dates_only"])


def _within_bounds(a: dict, b: dict) -> bool:
    diff = [i for i, (x, y) in enumerate(zip(a["figures"], b["figures"])) if x != y]
    return bool(diff) and len(a["figures"]) == len(b["figures"]) and all(a["bounded"][i] for i in diff)


def statements(excerpt: str) -> list[str]:
    """The quoted statements of a verbatim excerpt (or the plain sentences of a passage)."""
    quoted = re.findall(r"\"([^\"]{8,})\"", excerpt or "")
    body = quoted or re.split(r"(?<=[.!?])\s+", re.sub(r"^(?:Excerpts|Claims)\s*>?\s*", "", excerpt or ""))
    return [s.strip() for s in body if _NUM.search(s)]


def claims_as_text(excerpt: str) -> str:
    """A claims summary ('Claims - [C1] ... (E1) - [C2] ...') as plain sentences; other excerpts unchanged."""
    if not re.match(r"\s*Claims\b", excerpt or ""):
        return excerpt or ""
    body = re.sub(r"^\s*Claims\s*", "", excerpt)
    return " ".join(re.sub(r"\(E\d+\)", "", p).strip(" -") for p in re.split(r"\s*-?\s*\[C\d+\]\s*", body) if p.strip(" -"))


def _frame(sentence: str) -> str:
    """A statement with its figures and periods masked: two statements with the same frame measure the same thing."""
    return _parse(sentence)["frame"]


PRIMARY_CLASSES = ("official_company_source", "primary_third_party", "primary_source")


def figure_relations(entries: list[dict], company_domain: str | None = None) -> dict[str, dict]:
    """For public evidence from different documents, two statements are comparable when they have the same frame
    (the same metric and scope, about the same named organization if one is named; the evidence of one briefing
    concerns one company) and the same explicitly stated reporting periods. Comparable statements:
      - with the same figures: a non-primary source restates the primary one;
      - with different figures: contested, unless the figures are bounds in the same direction, or the statements
        may describe different moments (see _different_time): different publication days with no common stated
        period, or a forward-looking statement and its later update.
    Document headers (source metadata) and claims summaries are not statements. Returns {evidence_id: relation}."""
    cls = {e["evidence_id"]: source_class(e, company_domain) for e in entries}
    public = [e for e in entries if e.get("info_origin") == "public_source"
              and statement_form(e) not in ("claims_summary", "document_header")]
    by_frame: dict[str, list[tuple[dict, dict]]] = {}
    for e in public:
        for s in statements(e["excerpt"]):
            p = _parse(s)
            by_frame.setdefault(p["frame"], []).append((e, p))
    rel: dict[str, dict] = {}
    for frame, group in by_frame.items():
        if len({document_key(e) for e, _ in group}) < 2:
            continue
        for e, a in group:
            # I7.1: the compatible pairs and their basis are kept too (compatible_with), so they can reach the model;
            # contested_with and restates are decided exactly as before.
            r = rel.setdefault(e["evidence_id"], {"contested_with": [], "restates": [], "compatible_with": {}})
            for o, b in group:
                if document_key(o) == document_key(e):
                    continue  # one document
                oid = o["evidence_id"]
                if a["periods"] != b["periods"]:  # explicitly different reporting periods
                    if a["figures"] != b["figures"]:
                        r["compatible_with"].setdefault(oid, "different reporting periods")
                    continue
                if a["figures"] == b["figures"]:
                    if cls[e["evidence_id"]] not in PRIMARY_CLASSES and cls[oid] in PRIMARY_CLASSES \
                            and oid not in r["restates"]:
                        r["restates"].append(oid)
                elif _within_bounds(a, b):
                    r["compatible_with"].setdefault(oid, "bounds in the same direction")
                elif _different_time(e, a, o, frame):
                    r["compatible_with"].setdefault(oid, "a later forward-looking statement updates the earlier one"
                                                    if _FORWARD.search(frame) else
                                                    "different publication dates (each states the figure at its "
                                                    "own date)")
                elif oid not in r["contested_with"]:
                    r["contested_with"].append(oid)
    for r in rel.values():  # a pair contested by one statement is not also listed as compatible
        for oid in r["contested_with"]:
            r["compatible_with"].pop(oid, None)
    return {k: v for k, v in rel.items() if v["contested_with"] or v["restates"] or v["compatible_with"]}


def profile(entries: list[dict], company_domain: str | None = None, as_of=None) -> dict[str, dict]:
    """{evidence_id: profile} for a list of sanitized evidence entries. company_domain: the company's official
    domain from the resolved identity (None when unknown: primary sources then have no established owner).
    as_of (I7, the briefing date): marks public documents published within the news window (recent_official)."""
    from deal_prep import chronology, company_context, conflict_guard  # I4, I7, I7.1 (they build on this module)

    rel = figure_relations(entries, company_domain)
    guard = conflict_guard.ENABLED and chronology.ENABLED
    compat = conflict_guard.relations(entries, company_domain) if guard else {}
    by_id = {e["evidence_id"]: e for e in entries}
    ambiguous: dict[str, list[str]] = {}
    for c in chronology.derived_conflicts(entries, company_domain):
        if c["kind"] == "chronological_ambiguity":
            ids = [s["evidence_id"] for s in c["sides"]]
            for i in ids:
                ambiguous.setdefault(i, []).extend(o for o in ids if o != i)
    out = {}
    for e in entries:
        p = {"source_class": source_class(e, company_domain), "statement_form": statement_form(e),
             "date_status": date_status(e),
             "contested_with": rel.get(e["evidence_id"], {}).get("contested_with", []),
             "restates": rel.get(e["evidence_id"], {}).get("restates", [])}
        if chronology.ENABLED:  # I4 fields; empty ones are dropped from the model input
            p["ambiguous_with"] = ambiguous.get(e["evidence_id"], [])
            p["statement_date"] = "not_stated" if chronology.undated_history(e) else []
            p["event_dates_in_text"] = chronology.event_dates(e)
        if company_context.ENABLED and chronology.ENABLED:  # I7 fields (on I4's dates); empty ones are dropped
            if as_of is not None:
                p["recent_official"] = True if recent_official(e, as_of, company_context.RECENT_DAYS) else []
            stated = sorted({publication_day(by_id[i]) for i in p["restates"] if i in by_id
                             and date_status(by_id[i]) == "publication_date_stated"} - {None})
            p["restated_published"] = stated[-1] if stated and e["evidence_id"].startswith("WEB-") else []
        if guard:  # I7.1: what the code found logically compatible, uncertain, or possibly different, and why
            view = conflict_guard.model_view(compat.get(e["evidence_id"], {}))
            for kind in conflict_guard.KINDS:
                p[kind] = [x for x in view[kind] if x["evidence_id"] not in p["contested_with"]]
        out[e["evidence_id"]] = p
    return out
