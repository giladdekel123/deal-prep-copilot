"""I7.1 (owner-approved 2026-11-16): compatibility findings for the drafter, and a safeguard against conflict claims
the evidence does not support.

Found by the I7 live comparison (eval/real_companies_v1/I7_LIVE_COMPARISON.md): the drafter called two compatible
figures of one release ("226 centers worldwide" and "214+ treatment centres worldwide") an unresolved conflict. Three
general gaps allowed it:
  1. evidence_profile.figure_relations computed compatibility (bounds, different periods, different publication
     days) but returned only contested and restated pairs, so compatibility never reached the model;
  2. it compares only identically worded statements of different documents, so differently worded statements, or
     two statements of one document, were never compared at all;
  3. the drafting rule told the model to call any "different figures" unresolved, and no output check looked at
     conflict claims the model made on its own.

This module adds, as general rules over the sanitized evidence (no company, figure or expected answer is used):
  - relations(): compatibility and possible differences between QUANTITIES (a number with what it counts), also across
    wording and within one document. Two quantities are comparable when they count the same thing (the same content
    words after the number, singular and spelling-normalized), in the same scope (worldwide by default, or a named
    region), about the same named organization (or an unnamed one), in the same currency and scale; a measurement
    (percent, TEU, ...) or a money amount also needs the same metric named before it. I7.1b (owner-approved
    2026-11-16) separates what is proven from what is presumed. Comparable quantities are (classify()):
      compatible  - LOGICAL only: explicitly different stated reporting periods, or bounds that the values satisfy
                    ("more than X" and "over X" strict; "at least X" and "X+" inclusive; "up to", "fewer than"; two
                    bounds in one direction; overlapping bounds);
      uncertain   - not established either way: an approximate figure ("about", "approximately"; "nearly", "almost"
                    just under it; "just over" just over it) that fits only within the precision it is written to
                    (heuristic: half its rounding step, at most 10%, or 5 points for a percentage), a reporting period
                    stated on one side only, no period on either side with different publication dates, or a
                    forward-looking statement (guidance, expectations) and a later one for the same period (a presumed
                    update). Different publication dates by themselves never prove compatibility;
      differs     - values that do not fit for the SAME stated period (whatever the publication dates), or with no
                    period on the same or an unknown date: a possible contradiction that this lexical check does not
                    establish (never promoted to a contested figure; that stays the job of figure_relations).
    figure_relations' own compatible pairs are included: different reporting periods and same-direction bounds as
    compatible, its date-based ones as uncertain. All three reach the model as profile.compatible_with,
    profile.uncertain_with and profile.differs_from, each with its basis.
  - check(): every briefing item (fact or inference, outside meeting_recommendations) that calls statements
    conflicting, contradictory, inconsistent, discrepant or unresolved, and cites at least two public statements, is
    classified:
      supported            - it cites both sides of an established conflict (a contested figure or chronological
                             ambiguity derived from the evidence, or a curated public conflict group): allowed;
      unsupported_conflict - every comparable pair it cites is LOGICALLY compatible, and none is uncertain or differs:
                             the claim contradicts the evidence; it fails validation (one controlled retry);
      unverified_conflict  - no check establishes the disagreement (the detector did not compare, the comparison is
                             uncertain, or it found a possible difference): allowed only as an inference that says it
                             must be verified (a genuine conflict the detector missed can still be disclosed, as an
                             uncertainty for review); stated as established, it fails validation. Temporal
                             presumptions and approximations therefore lead to verification, never to removal.
  - neutralize(): the last resort after the retry, applied only when the guard's issues are the only problems left:
    an unsupported conflict item is removed; an unverified one becomes an inference with a sentence saying the sources
    do not establish it and it must be verified. Every action is recorded; evidence and required disclosures are never
    changed.
ENABLED switches I7.1 off for a controlled comparison only.
"""
import re
from itertools import combinations

ENABLED = True
MAX_RELATED = 8  # per entry and kind, in the model input
# The heuristic tolerance of an approximate figure (I7.1b): half the step it is written to (see _precision), at most
# MAX_RELATIVE of the figure, or at most MAX_RATE_POINTS for a percentage. It is never proof of compatibility.
MAX_RELATIVE = 0.10
MAX_RATE_POINTS = 5.0

_LOWER = r"more than|over|at least|in excess of|upwards of|above|no fewer than|no less than|exceeding"
_UPPER = r"up to|less than|fewer than|under|at most|no more than|below|not more than"
_APPROX = r"about|approximately|around|roughly|some|circa|an estimated|estimated"  # either side of the figure
_BELOW = r"nearly|almost|close to|just under|just below|not quite|slightly less than|slightly under"  # just under it
_ABOVE = r"just over|just above|slightly more than|slightly over"  # just over it
_STRICT = {"more than", "over", "above", "in excess of", "upwards of", "exceeding", "less than", "fewer than", "under",
           "below"}
_NUMBER = re.compile(r"(?<![\w.])(?:(?P<cur>[$€£])\s?)?(?P<num>\d+(?:[.,]\d+)*)(?P<plus>\+)?(?![\d])")  # C1: whole
_BEFORE = re.compile(rf"\b(?P<word>{_BELOW}|{_ABOVE}|{_LOWER}|{_UPPER}|{_APPROX})\s+(?:(?:[A-Z]{{3}}|[$€£])\s?)?$",
                     re.I)
APPROXIMATE = ("approx", "near_below", "near_above")
_CURRENCY_CODE = re.compile(r"\b([A-Z]{3})\s?$")
_SCALE = {"billion": 1e9, "bn": 1e9, "b": 1e9, "million": 1e6, "mn": 1e6, "m": 1e6, "thousand": 1e3, "k": 1e3}
_PERCENT = {"percent", "per cent", "%"}
# Units that measure without naming what is measured (the metric is named before the number: "carried volume ... 922
# thousand TEUs", "revenue increased 12 percent"): such quantities compare only when that metric matches too.
_MEASURES = {"percent", "teu", "tonne", "ton", "kg", "km", "mile", "meter", "foot", "feet", "mw", "gw", "mwh", "gwh",
             "hour", "day", "week", "month", "year", "point", "basis", "time", "share", "vote", "unit", "x", "amount"}
_VERBS = set("""was were is are amounted totaled totalled reached rose increased decreased fell grew declined reported
reports operates operated operate currently now approximately stood came had has have generated achieved recorded
improved improvement by expects expect expected expecting forecasts forecast forecasted projects projected plans plan
targets targeted anticipates anticipated says said announced announces raised raises lowered lowers narrowed today
guidance outlook full year""".split())  # verbs, forecast and reporting words: not part of a metric's name
_STOP = set("""a an the and or of at in on to for from by with as is are was were be been being has have had will would
can could may might this that these those its it their our we which who whose than then also including include
includes about around across over under per each all every more most less fewer between within into through during
since until after before while where when what so such not no nor but if yet including""".split())
_GLOBAL = re.compile(r"\b(?:worldwide|globally|global|around the world|across the world|world)\b", re.I)
_REGION = re.compile(r"\b(?i:in|across|throughout)\s+(?i:the\s+)?((?:[A-Z][A-Za-z.]*\.?)(?:\s+[A-Z][A-Za-z.]*\.?)*)")
_MONTHS = {"january", "february", "march", "april", "may", "june", "july", "august", "september", "october",
           "november", "december", "jan", "feb", "mar", "apr", "jun", "jul", "aug", "sep", "sept", "oct", "nov", "dec"}
_COMMON_CAPS = {"the", "a", "an", "to", "in", "on", "at", "for", "since", "by", "as", "our", "we", "its", "it", "this"}
CONFLICT_WORDS = re.compile(r"\b(?:conflict\w*|contradict\w*|inconsisten\w*|discrepan\w*|unresolved|disagree\w*|"
                            r"irreconcil\w*|at odds|do(?:es)? not (?:match|agree|fit|reconcile)|cannot be reconciled)\b",
                            re.I)
REVIEW_WORDS = re.compile(r"\b(?:verif\w*|confirm\w*|check\w*|may|might|appear\w*|possibl\w*|unclear|"
                          r"to be (?:confirmed|checked|verified))\b", re.I)
VERIFY_NOTE = ("The sources do not establish this disagreement; verify it before relying on it.")


# --- quantities -----------------------------------------------------------------------------------------------

def _norm_word(w: str) -> str:
    w = w.casefold().strip("'’.").removesuffix("'s").removesuffix("’s")
    if re.fullmatch(r"[a-z]+tres", w):  # British -tre: centres, metres -> centers, meters
        w = w[:-4] + "ters"
    elif re.fullmatch(r"[a-z]+tre", w):  # centre, metre -> center, meter
        w = w[:-3] + "ter"
    if len(w) > 4 and w.endswith("ies"):
        w = w[:-3] + "y"
    elif len(w) > 3 and w.endswith("s") and not w.endswith("ss"):
        w = w[:-1]
    return w


def _entities(sentence: str) -> frozenset:
    """Named organizations or products a statement mentions: capitalized words that do not start it, are not months,
    places of scope, currency codes or common words."""
    words = re.findall(r"[A-Za-z][\w'’&.-]*", sentence)
    if len(words) >= 4 and sum(w[0].isupper() for w in words) >= 0.6 * len(words):
        return frozenset()  # a title-case headline: capitals do not mark names there
    out = set()
    for i, w in enumerate(words):
        if i == 0 or not w[0].isupper() or w.isupper() and len(w) <= 4:
            continue
        n = _norm_word(w)
        if n in _MONTHS or n in _COMMON_CAPS:
            continue
        out.add(n)
    return frozenset(out)


def _scope(segment: str, sentence_regions: set) -> frozenset:
    regions = {re.sub(r"[^a-z]", "", r.casefold()) for r in _REGION.findall(segment)}
    regions = {r for r in regions if r and r not in _MONTHS}
    if regions:
        return frozenset(regions)
    if _GLOBAL.search(segment):
        return frozenset({"global"})
    return frozenset(sentence_regions) if sentence_regions else frozenset({"global"})


def quantities(sentence: str, style: str | None = None) -> list[dict]:
    """Each number with what it counts: {value, kind (exact|lower|upper|approx), strict, unit (content words after
    it), scale, currency, scope, entities, text}. Years, dates and identifiers are not quantities.
    C1: numbers are read with deal_prep.numbers, in the sentence's own number style, else `style` (its source
    document's); a figure whose reading stays uncertain ("1,569" with no style to decide it) is not counted: an
    uncertain value is never compared as if it were known."""
    from deal_prep import numbers
    from deal_prep.evidence_profile import _FORWARD, _PERIOD
    style = numbers.style_of(sentence) or style
    masked = _PERIOD.sub(lambda m: "§" * len(m.group(0)), sentence)  # dates and periods are not counted things
    forward = bool(_FORWARD.search(sentence))  # guidance, expectations, plans: a later one may update it
    nums = list(_NUMBER.finditer(masked))
    regions = {re.sub(r"[^a-z]", "", r.casefold()) for r in _REGION.findall(sentence)} - {""}
    regions = {r for r in regions if r not in _MONTHS}
    entities = frozenset(_entities(sentence) - regions)  # a place of scope is not a named organization
    out = []
    for k, m in enumerate(nums):
        before = masked[max(0, m.start() - 40):m.start()]
        end = nums[k + 1].start() if k + 1 < len(nums) else len(masked)
        after = masked[m.end():end]
        words = re.findall(r"[A-Za-z%][\w'’-]*|%", after)
        scale, currency, unit = 1.0, m.group("cur") or "", []
        cc = _CURRENCY_CODE.search(before)
        currency = currency or (cc.group(1) if cc else "")
        for w in words:
            lw = w.casefold()
            if not unit and lw in _SCALE and scale == 1.0:
                scale = _SCALE[lw]
                continue
            if lw in _PERCENT or lw == "%":
                unit.append("percent")
                break
            if lw in _STOP or len(unit) >= 3:
                break
            if re.fullmatch(r"[A-Z]{3}", w) and not unit:  # a currency code after the number
                currency = currency or w
                continue
            unit.append(_norm_word(w))
        unit = [u for u in unit if u and not _GLOBAL.fullmatch(u) and u not in regions]
        if not unit and currency:  # I7.1b: a money amount ("revenue was USD 2 billion"); its metric must match too
            unit = ["amount"]
        if not unit:
            continue
        b = _BEFORE.search(before)
        word = " ".join(b.group("word").casefold().split()) if b else ""
        kind = ("lower" if m.group("plus") or re.fullmatch(_LOWER, word or "-") else
                "upper" if re.fullmatch(_UPPER, word or "-") else
                "near_below" if re.fullmatch(_BELOW, word or "-") else
                "near_above" if re.fullmatch(_ABOVE, word or "-") else
                "approx" if re.fullmatch(_APPROX, word or "-") else "exact")
        readings, uncertain, decided = numbers.interpret(m.group("num"), style)
        if len(readings) > 1:  # a count of whole things settles it ("4,250 employees")
            readings = numbers.counted(readings, masked[m.end():m.end() + 60])
            uncertain = len(readings) != 1
        if len(readings) != 1 or uncertain:  # malformed or uncertain: not compared (C1)
            continue
        value = readings[0][0] * scale
        written = m.group("num") if decided != "eu" else m.group("num").replace(".", "").replace(",", ".")
        tolerance = 0.0
        if kind in APPROXIMATE:  # heuristic: the step the figure is written to, capped
            tolerance = _precision(written) * scale / 2
            tolerance = min(tolerance, MAX_RATE_POINTS if "percent" in unit else MAX_RELATIVE * abs(value))
        # The metric a measurement belongs to: the content words of the sentence before it ("revenues ... second
        # quarter ... year-over-year increase" is not "adjusted EBITDA ... year-over-year increase").
        prev = [_norm_word(w) for w in re.findall(r"[A-Za-z][\w'’-]*", masked[:m.start()])]
        metric = tuple(dict.fromkeys(w for w in prev if w and w not in _STOP and w not in _VERBS and w not in _SCALE
                                     and not re.fullmatch(rf"{_LOWER}|{_UPPER}|{_APPROX}", w)
                                     and not re.fullmatch(r"[a-z]{3}", w)))
        out.append({"value": value, "kind": kind, "strict": word in _STRICT, "unit": tuple(unit),
                    "currency": currency.upper(), "scale": scale, "scope": _scope(after, regions),
                    "entities": entities, "metric": metric, "tolerance": tolerance, "qualifier": word, "forward": forward,
                    "figure": m.group(0), "text": (f"{word} " if word else "") + m.group(0) + f" {' '.join(unit)}"})
    return out


def _precision(num: str) -> float:
    """The step a written figure is rounded to: 4,000 -> 1,000; 4,200 -> 100; 4,250 -> 50 (a final 5 is a step of 5);
    4.2 -> 0.1; 4.25 -> 0.05; 12 -> 1. Heuristic: a figure ending in zeros may be exact."""
    digits = num.replace(",", "")
    if "." in digits:
        frac = digits.split(".", 1)[1]
        place, last = 10.0 ** -len(frac), (frac[-1:] or "0")
    else:
        stripped = digits.rstrip("0") or "0"
        place, last = 10.0 ** (len(digits) - len(stripped)), stripped[-1]
    return place * (5 if last == "5" else 1)


def _subset(x, y) -> bool:
    shorter, longer = sorted((set(x), set(y)), key=len)
    return bool(shorter) and shorter <= longer


def _same_thing(a: dict, b: dict) -> bool:
    if not _subset(a["unit"], b["unit"]) or a["currency"] != b["currency"] or a["scope"] != b["scope"]:
        return False
    if not (a["entities"] == b["entities"] or not a["entities"] or not b["entities"]):
        return False
    if set(a["unit"]) <= _MEASURES or a["currency"]:  # a measurement: the metric named before it must match too
        return _subset(a["metric"], b["metric"])
    return True


_INF = float("inf")


def _interval(q: dict) -> tuple[float, float, bool, bool]:
    """The values a quantity allows: (low, high, low included, high included). An approximate figure's width is its
    heuristic tolerance (_precision); "nearly X" lies just under X, "just over X" just over it."""
    v, t, k = q["value"], q["tolerance"], q["kind"]
    return {"exact": (v, v, True, True), "approx": (v - t, v + t, True, True), "near_below": (v - t, v, True, False),
            "near_above": (v, v + t, False, True), "lower": (v, _INF, not q["strict"], False),
            "upper": (-_INF, v, False, not q["strict"])}[k]


def _overlap(i, j) -> bool:
    lo, lo_in = max((i[0], i[2]), (j[0], j[2]), key=lambda x: (x[0], not x[1]))
    hi, hi_in = min((i[1], i[3]), (j[1], j[3]), key=lambda x: (x[0], x[1]))
    return lo < hi or (lo == hi and lo_in and hi_in)


def _fit(a: dict, b: dict) -> tuple[str, str]:
    """('equal' | 'logical' | 'heuristic' | 'conflict', basis) for the VALUES of two comparable quantities, whatever
    their dates: logical when bounds make both true, heuristic when only an approximation's inferred tolerance does."""
    ka, kb = a["kind"], b["kind"]
    if ka == kb and a["value"] == b["value"]:  # the same figure, stated the same way
        return "equal", ""
    if ka == kb == "exact":
        return "conflict", f"{a['figure']} and {b['figure']} do not match"
    fits = _overlap(_interval(a), _interval(b))
    if ka in APPROXIMATE or kb in APPROXIMATE:
        return ("heuristic", f"{a['text']} and {b['text']} fit only within the precision an approximate figure is "
                             f"written to (heuristic, not proof)") if fits else \
            ("conflict", f"{a['text']} and {b['text']} do not fit even within that precision")
    if ka == kb:
        return ("logical", f"both are {ka} bounds") if fits else ("conflict", "the bounds do not overlap")
    if "exact" in (ka, kb):
        bound, other = (a, b) if ka != "exact" else (b, a)
        verb = "satisfies" if fits else "does not satisfy"
        return ("logical" if fits else "conflict", f"{other['figure']} {verb} the {bound['kind']} bound {bound['text']}")
    return ("logical", "the bounds overlap") if fits else ("conflict", "the bounds do not overlap")


def period_relation(pa: list, pb: list) -> str:
    """'same', 'different', 'none' (no period stated) or 'ambiguous' (stated on one side only, or partly the same)."""
    a, b = set(pa), set(pb)
    if not a and not b:
        return "none"
    if a and b and a == b:
        return "same"
    return "different" if a and b and a.isdisjoint(b) else "ambiguous"


def classify(a: dict, b: dict, period: str, days: str) -> tuple[str, str] | None:
    """('compatible' | 'uncertain' | 'differs', basis) for two quantities, or None when they are not comparable or
    equal. period: period_relation(); days: 'same', 'different' or 'unknown' (a missing publication day).
      compatible - LOGICAL only: explicitly different stated periods, or bounds the values satisfy;
      uncertain  - not established either way: an approximation's inferred tolerance, a period missing on one side
                   or both with different publication dates (dates alone never prove compatibility), or a
                   forward-looking statement and a later one for the same period (a presumed update);
      differs    - the values do not fit for the same stated period, or with no period on the same or an unknown
                   day: a possible contradiction that this lexical check does not establish."""
    if not _same_thing(a, b):
        return None
    if period == "different":
        return "compatible", "different stated reporting periods"
    fit, basis = _fit(a, b)
    if fit == "equal":
        return None
    if fit == "logical":
        return "compatible", basis
    if fit == "heuristic":
        return "uncertain", basis
    if period == "same":
        if (a["forward"] or b["forward"]) and days == "different":  # a forecast for the period, and a later one
            return "uncertain", (f"a later forward-looking statement for the same period may update the earlier one "
                                 f"(a presumption, not established): {basis}")
        return "differs", f"the same stated period, whatever the publication dates: {basis}"
    if period == "ambiguous":
        return "uncertain", f"a reporting period is stated on one side only, or only partly the same: {basis}"
    if days == "different":
        return "uncertain", (f"no reporting period is stated and the sources were published on different dates, so "
                             f"they may describe different moments; that is a presumption, not established: {basis}")
    return "differs", f"no reporting period stated, the same or an unknown publication date: {basis}"


# --- relations between evidence entries ------------------------------------------------------------------------

KINDS = ("compatible_with", "uncertain_with", "differs_from")
# figure_relations' own compatible pairs (identically worded statements): which of its bases are logical. Its date
# bases ("different publication dates", "a later forward-looking statement updates ...") are presumptions (I7.1b).
_LOGICAL_FIGURE_BASES = ("different reporting periods", "bounds in the same direction")


def relations(entries: list[dict], company_domain: str | None = None) -> dict[str, dict]:
    """{evidence_id: {"compatible_with" | "uncertain_with" | "differs_from": {other: basis}}} over public statements
    (see classify), including figure_relations' own compatible pairs. Pairs that figure_relations contests are left
    to it. A pair has one status, the most cautious its quantities give: differs, then uncertain, then compatible."""
    from deal_prep import evidence_profile as ep
    public = [e for e in entries if e.get("info_origin") == "public_source"
              and ep.statement_form(e) not in ("claims_summary", "document_header")]
    fig = ep.figure_relations(entries, company_domain)
    found: dict[tuple, dict[str, list]] = {}

    def add(kind, x, y, basis):
        bases = found.setdefault(tuple(sorted((x, y))), {k: [] for k in KINDS})[kind]
        if basis not in bases:
            bases.append(basis)
    for eid, r in fig.items():
        for oid, basis in r.get("compatible_with", {}).items():
            logical = basis in _LOGICAL_FIGURE_BASES
            add("compatible_with" if logical else "uncertain_with", eid, oid,
                basis if logical else f"{basis}: a presumption from the publication dates, not established")
    contested = {(eid, o) for eid, r in fig.items() for o in r.get("contested_with", [])}
    from deal_prep import numbers
    doc_style = {}  # C1: each source document's number style, for figures its own sentence leaves uncertain
    for e in public:
        doc_style.setdefault(ep.document_key(e), []).append(e.get("excerpt") or "")
    doc_style = {d: numbers.style_of(texts) for d, texts in doc_style.items()}
    stated = []
    for e in public:
        for s in ep.statements(e["excerpt"]):
            stated.append((e, ep._parse(s), quantities(s, doc_style.get(ep.document_key(e)))))
    for (e, pa, qa), (o, pb, qb) in combinations(stated, 2):
        if e["evidence_id"] == o["evidence_id"] or (e["evidence_id"], o["evidence_id"]) in contested:
            continue
        de, do = ep.publication_day(e), ep.publication_day(o)
        days = "unknown" if not (de and do) else "same" if de == do else "different"
        period = period_relation(pa["periods"], pb["periods"])
        for x in qa:
            for y in qb:
                res = classify(x, y, period, days)
                if res:
                    add({"compatible": "compatible_with", "uncertain": "uncertain_with",
                         "differs": "differs_from"}[res[0]], e["evidence_id"], o["evidence_id"], res[1])
    out: dict[str, dict] = {}
    for (x, y), by in found.items():
        kind = next(k for k in ("differs_from", "uncertain_with", "compatible_with") if by[k])
        for p, q in ((x, y), (y, x)):
            out.setdefault(p, {k: {} for k in KINDS})[kind][q] = "; ".join(by[kind])
    return out


def model_view(rel: dict) -> dict:
    """The profile fields for one entry (empty lists are dropped from the model input)."""
    return {k: [{"evidence_id": o, "basis": b} for o, b in sorted(rel.get(k, {}).items())][:MAX_RELATED]
            for k in KINDS}


# --- the output safeguard -----------------------------------------------------------------------------------------

def _supported_sides(bundle: dict, index: dict) -> list[list[set]]:
    """Sides of every established conflict about public statements: derived contested figures and chronological
    ambiguities, and curated conflict groups (the passages of one group, by document) in the evidence."""
    from deal_prep import chronology
    domain = (bundle.get("identity") or {}).get("domain")
    out = [[{s["evidence_id"]} for s in c["sides"]] for c in chronology.derived_conflicts(list(index.values()), domain)]
    curated: dict[str, dict[str, set]] = {}
    for eid, e in index.items():
        if e.get("conflict_group"):
            curated.setdefault(e["conflict_group"], {}).setdefault(e.get("document_id") or eid, set()).add(eid)
    out += [list(docs.values()) for docs in curated.values() if len(docs) >= 2]
    return out


def check(draft: dict, bundle: dict, index: dict | None = None) -> list[dict]:
    """Validation issues for conflict claims the evidence does not support (see the module docstring). index: the
    drafting input ({evidence_id: sanitized entry}); computed from the bundle when not given."""
    if not ENABLED:
        return []
    from deal_prep.evidence import evidence_index
    index = index if index is not None else evidence_index(bundle)
    public = {eid for eid, e in index.items() if e.get("info_origin") == "public_source"}
    rel = None
    sides = None
    issues = []
    for section, items in draft["sections"].items():
        if section == "meeting_recommendations":
            continue
        for i, item in enumerate(items):
            cited = [e for e in item["evidence_ids"] if e in public]
            if item["kind"] not in ("fact", "inference") or len(set(cited)) < 2 \
                    or not CONFLICT_WORDS.search(item["text"]):
                continue
            sides = sides if sides is not None else _supported_sides(bundle, index)
            if any(all(set(cited) & s for s in group) for group in sides if len(group) >= 2):
                continue  # it reports an established conflict
            rel = rel if rel is not None else relations(list(index.values()), (bundle.get("identity") or {})
                                                        .get("domain"))
            pairs = list(combinations(sorted(set(cited)), 2))
            compat = [(a, b, rel[a]["compatible_with"][b]) for a, b in pairs
                      if b in rel.get(a, {}).get("compatible_with", {})]
            open_ = [(a, b) for a, b in pairs if b in rel.get(a, {}).get("differs_from", {})
                     or b in rel.get(a, {}).get("uncertain_with", {})]
            if compat and not open_:  # only LOGICAL compatibility may refuse a conflict claim (I7.1b)
                a, b, basis = compat[0]
                issues.append({"section": section, "item": i, "evidence_id": a, "code": "unsupported_conflict",
                               "message": f"this item calls {a} and {b} conflicting or unresolved, but they are "
                                          f"compatible ({basis}; see profile.compatible_with): do not present a "
                                          f"conflict; state the figure with its basis, or both with their bases"})
            elif not (item["kind"] == "inference" and REVIEW_WORDS.search(item["text"])):
                why = next((rel[a].get(k, {}).get(b) for a, b in open_ for k in ("differs_from", "uncertain_with")
                            if rel[a].get(k, {}).get(b)), None)
                issues.append({"section": section, "item": i, "evidence_id": cited[0], "code": "unverified_conflict",
                               "message": "no check of the evidence establishes this disagreement (it is not a "
                                          "contested figure or disclosed conflict"
                                          + (f"; the code found: {why}" if why else "") + "): state it as an "
                                          "inference that the statements may differ and must be verified, or leave "
                                          "it out"})
    return issues


GUARD_CODES = {"unsupported_conflict", "unverified_conflict", "one_sided_conflict_claim"}
ONE_SIDED_NOTE = "The vendor's own documents disagree on this, so it is not established (see the disclosure)."


def neutralize(draft: dict, issues: list[dict]) -> tuple[dict, list[dict]]:
    """Last resort (after the controlled retry): remove each unsupported conflict item; turn each unverified one into
    an inference saying it must be verified. Returns the new draft and the actions taken (evidence and required
    disclosures are not touched)."""
    import copy
    out = copy.deepcopy(draft)
    actions, drop = [], {}
    for x in issues:
        item = out["sections"][x["section"]][x["item"]]
        if x["code"] == "unsupported_conflict":
            drop.setdefault(x["section"], set()).add(x["item"])
            actions.append({"action": "removed", "section": x["section"], "text": item["text"],
                            "evidence_ids": item["evidence_ids"], "reason": x["message"]})
        elif x["code"] in ("unverified_conflict", "one_sided_conflict_claim"):
            note = VERIFY_NOTE if x["code"] == "unverified_conflict" else ONE_SIDED_NOTE
            item.update(kind="inference", claim_type=None, text=(item["text"].rstrip() + " " + note).strip())
            actions.append({"action": "marked_for_verification", "section": x["section"], "text": item["text"],
                            "evidence_ids": item["evidence_ids"], "reason": x["message"]})
    for section, idx in drop.items():
        out["sections"][section] = [it for n, it in enumerate(out["sections"][section]) if n not in idx]
        if not out["sections"][section] and not any(d["id"] == f"empty_section:{section}" for d in out["disclosures"]):
            out["disclosures"].append({"id": f"empty_section:{section}",
                                       "text": "No supported content for this section."})
    return out, actions
