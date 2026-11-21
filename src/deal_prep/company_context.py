"""I7 (owner-approved 2026-11-16): company context, research coverage, business unknowns, dates and length.

Found by the real-company evaluation (eval/real_companies_v1/DIAGNOSIS_AND_IMPROVEMENT_PLAN.md): the drafter received
an organization's identity, its latest results, a pending acquisition, a leadership change and its newest outlook,
and left them out, because the meeting contract required none of them; retrieval kept five passages, so a company
with several short releases lost its newest one; the agent spent its searches on relationship records that cannot
exist for a public-only organization; news excerpts were cut mid-sentence; and nothing stated what is unknown.

General rules over the evidence and its profile (source class, stated publication date, statement patterns). No
company name, figure or expected answer is used.
1. Company essentials (contract topics company:*, introduction and general meetings), by priority and only from the
   organization's primary records (its own pages, and its releases or filings held elsewhere; never secondary
   profiles or news): who it is in its own words; an ownership development within EVENT_DAYS
   (what was announced and its newest status; pending stays pending); a leadership change; the newest outlook (an
   earlier one is superseded, not a conflict); the figures of its newest dated official release within LATEST_DAYS,
   with the release or period and its publication date. At most three figures per item; nothing else is required.
2. Retrieval coverage: the company-profile search keeps one passage per document (PROFILE_DOCUMENTS documents) plus
   the NEWEST_DOCUMENTS newest dated documents, so every one of them reaches the drafter with its excerpts (selection
   step 7). A document the agent finds arrives with its excerpts too. For a public-only organization the agent is
   told that no relationship records are held, and a search for them is refused.
3. Business unknowns: what the evidence does not establish is disclosed once (required disclosure unknown:business),
   and discovery questions are contract topics (discovery:*) in meeting_recommendations, asked neutrally: no
   relationship, need, budget or intention to buy is implied.
4. Dates: a public document's stated publication date dates it. One published within the news window may be a
   recent development (profile.recent_official); a news copy that restates it carries that date
   (profile.restated_published); anything used from an undated page says "date not stated" (topics undated:page:*).
5. News excerpts: at most MAX_EXCERPT_WORDS words ("…" markers included) of whole sentences, the lead and the most
   factual first (dates, figures, schedule); omitted text is marked "…". A release's leading dateline (place and
   date, at most DATELINE_MAX_WORDS words) is kept verbatim in its own field (dateline), outside the excerpt, and its
   date counts as a date in the item's own text (chronology.event_dates).
6. Length: one page preferred, a second page when needed to keep important content (prompt policy, briefing.I7_RULES).
ENABLED switches I7 off for a controlled comparison only; with it off the system behaves as at commit a0adca3.
"""
import re
from datetime import date

ENABLED = True
LATEST_DAYS = 120      # the newest dated official release counts as current context for about a quarter and a half
EVENT_DAYS = 365       # ownership, leadership and outlook developments of the last year
RECENT_DAYS = 30       # the news window (web_research fallback window): a release this recent is a development
PROFILE_DOCUMENTS = 8  # distinct documents kept from the ranked company-profile search
NEWEST_DOCUMENTS = 3   # newest dated documents of the organization always added
MAX_FIGURES = 3        # per company item (prioritization, not a full dump)
DATELINE_MAX_WORDS = 14
# Primary records about the organization: its own pages, and its releases or filings held elsewhere (for example on a
# regulator's site or an investor-relations file host). Never secondary profiles (directories, aggregators) or news.
PRIMARY = ("official_company_source", "primary_source", "primary_third_party")

_MONTHS = ("January", "February", "March", "April", "May", "June", "July", "August", "September", "October",
           "November", "December")
# C2 (owner-approved 2026-11-17): a self-description is a sentence whose SUBJECT is the organization (its name, an
# alias, "the Group"/"the Company", or a sentence-initial "We", also after an introductory phrase such as "Founded in
# 1887, we ...") followed by a description: "is a/an/the/one of ...", or a verb of what it does. Wording elsewhere in a
# sentence ("... and we are cooperating with them") never makes it one. Identity facts complement it: where the
# organization is based, where it is listed, and its scale.
_DESCRIBE = (r"(?:is|are|was|has been)\s+(?:a|an|the|one of)\b|(?:provides?|operates?|develops?|designs?|"
             r"manufactures?|offers?|delivers?|builds?|owns?|serves?|speciali[sz]es?|works?|produces?|"
             r"supplies?|makes?)\b")
_INTRO = r"(?:[^,.;:\"]{1,90},\s+)?"  # an introductory phrase before the subject
_SEAT = re.compile(r"\bheadquarter(?:s|ed)\b|\bregistered (?:office|address)\b|\bhead office\b", re.I)
_LISTING = re.compile(r"\b(?:listed on|stock exchange|listing rules?|shares are (?:listed|traded)|publicly (?:listed|"
                      r"traded))\b", re.I)
_SCALE = re.compile(r"\b\d[\d,.]*\s+(?:(?:million|thousand|billion)\s+)?(?:[a-z-]+\s+){0,2}?(?:employees|people|staff|"
                    r"colleagues|workforce|countries|offices|laboratories|sites|locations|customers|clients|"
                    r"passengers)\b", re.I)
_FACTS = (("seat", _SEAT), ("listing", _LISTING), ("scale", _SCALE))
MAX_SELF_DESCRIPTIONS = 2
# C2 (owner-approved 2026-11-17): the latest material developments. Statements of the newest official documents (all
# documents of the newest publication day) and, when those report no results, of the latest results document (within
# LATEST_DAYS), classified and ranked by general signals: headline results (profit; revenue, else the operating
# result) with their direction and stated reason, then guidance changes and trading updates, then business
# developments, then other figures. The headline results and the newest material update are always kept (essential);
# others fill up to DEFAULT_DEVELOPMENTS, a default, not a quota; MAX_DEVELOPMENTS bounds the total.
DEFAULT_DEVELOPMENTS = 3
MAX_DEVELOPMENTS = 5
_OPERATING = re.compile(r"\b(?:EBITDA|EBITA|EBIT|operating (?:profit|income|result|margin|earnings))\b", re.I)
_PROFIT = re.compile(r"\b(?:net (?:profit|income|earnings|loss|result)|profits?|earnings|PBT|PAT|loss for the period)"
                     r"\b", re.I)
_TOPLINE = re.compile(r"\b(?:revenues?|net sales|sales|turnover)\b", re.I)
_DIRECTION = re.compile(r"%|\b(?:up|down|rose|fell|grew|declined|increased?|decreased?|higher|lower|growth|decline|"
                        r"improved|improvement)\b", re.I)
_REASON = re.compile(r"\b(?:due to|driven by|mainly|primarily|because|as a result of|reflecting|despite|owing to)\b",
                     re.I)
_GUIDANCE_CHANGE = re.compile(r"\b(?:rais(?:es|ed|ing)|lower(?:s|ed|ing)?|maintain(?:s|ed)?|confirm(?:s|ed)?|"
                              r"reaffirm(?:s|ed)?|upgrade[sd]?|downgrade[sd]?|narrow(?:s|ed)?|reiterate[sd]?|now "
                              r"expect(?:s|ed)?|unchanged|on track)\b", re.I)
_TRADING = re.compile(r"\b(?:trading|in line with (?:the |its |our )?(?:outlook|guidance|expectations|plan)|ahead of "
                      r"(?:expectations|plan|guidance)|behind (?:expectations|plan|guidance))\b", re.I)
_DEVELOPMENT = re.compile(r"\b(?:effective|completed|commissioned|signed|launched|acquired|divested|reorgani[sz]\w*|"
                          r"restructur\w*|new (?:reporting|organi[sz]ational|operating) structure)\b", re.I)
_KIND_SCORE = {"result": 10, "guidance": 8, "trading": 8, "development": 8, "figure": 4}
_KINDS = (("acqui", "acquisition"), ("wholly owned", "acquisition"), ("merg", "merger"), ("spin", "spin-out"),
          ("spun", "spin-out"), ("divest", "divestment"), ("takeover", "takeover"), ("tender", "tender offer"),
          ("buy", "buyout"))
_OWNERSHIP = re.compile(r"\b(?:acquir(?:e|es|ed|ing)|acquisition|merger|merge[sd]?|takeover|tender offer|buy-?out|"
                        r"divest(?:s|ed|iture|ment)?|spin-?offs?|spin-?outs?|spun (?:off|out)|wholly owned subsidiary|"
                        r"pending transaction|closing of the (?:transaction|merger|acquisition))\b", re.I)
_PENDING = re.compile(r"\b(?:pending|subject to|expected to close|targeted to close|remains subject|until the "
                      r"closing|not yet)\b", re.I)
_ROLE = re.compile(r"\b(?:CEO|chief executive|president|chair(?:man|woman|person)?|CFO|chief financial officer|"
                   r"managing director)\b", re.I)
_CHANGE = re.compile(r"\b(?:appoint(?:s|ed|ment)?|named|resign(?:s|ed|ation)?|step(?:s|ped)? down|succeed(?:s|ed)?|"
                     r"successor|retire(?:s|d|ment)?)\b", re.I)
_OUTLOOK = re.compile(r"\b(?:guidance|outlook|forecast|now expects|expects to (?:generate|report|achieve|deliver|"
                      r"reach))\b", re.I)
_FINANCIAL = re.compile(r"\b(?:revenues?|net sales|sales|operating (?:income|profit|result)|EBITDA|EBIT|net (?:income|"
                        r"profit|loss)|profit|earnings|order bookings|order backlog|backlog)\b", re.I)
_OUTLOOK_TITLE = re.compile(r"\b(?:guidance|outlook|forecast)\b", re.I)  # a release about the outlook: all of it is
_RANGE = re.compile(r"\bbetween\s+(?:[A-Za-z]{1,4}\s+)?\S*\d[^.;]*?\b(?:and|to)\s+(?:[A-Za-z]{1,4}\s+)?\S*\d", re.I)  # "between X and Y": an estimate, not a result
_PERIOD_WORDS = (r"\b(?:first|second|third|fourth)[- ]quarter|\bQ[1-4]\b|\bhalf[- ]year|\bfull[- ]year|\binterim\b|"
                 r"\bannual report|\bquarterly\b")
_RELATIONSHIP_QUERY = re.compile(r"\b(?:crm|proposals?|quotes?|quotations?|correspondence|e-?mails?|opportunit\w*|"
                                 r"relationship|meeting (?:notes|records?|history)|prior (?:meetings?|contacts?)|"
                                 r"account (?:history|activity|records?|contacts?)|sales (?:activity|history|records?)|"
                                 r"pipeline)\b", re.I)
_HEADER_TITLE = re.compile(r"^PUBLIC SOURCE\s*[—-]\s*(?:[^—]*FICTIONAL[^—]*—\s*)?[^:]{1,80}:\s*(.+?)\s+-\s+\*\*")

# --- news excerpts (5) ------------------------------------------------------------------------------------------

_MON = r"(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Sept|Oct|Nov|Dec)[a-z]*\.?"
_DATE_TEXT = rf"(?:{_MON}\s+\d{{1,2}},?\s+\d{{4}}|\d{{1,2}}\s+{_MON},?\s+\d{{4}})"
_DATELINE = re.compile(rf"^\s*[A-Z][\w.'’-]*(?:(?:,\s*|\s+and\s+|\s+)[A-Z][\w.'’-]*)*,?\s*\(?{_DATE_TEXT}\)?"
                       rf"(?:\s*/[A-Za-z ]+/)?\s*(?:[-–—:]|\.\.\.|…)?\s*")
_UNIT_SPLIT = re.compile(r"((?<=[.!?])\s+(?=[A-Z0-9\"“(])|\s*(?:\.\.\.|…)\s*)")
_DATE_WORDS = re.compile(rf"\b(?:{'|'.join(_MONTHS)}|{_MON}\s+\d|(?:19|20)\d\d|today|tomorrow|quarter)\b", re.I)
_SCHEDULE = re.compile(r"\b(?:scheduled|expected|will|plans?|commenc\w*|begin\w*|start\w*|complet\w*|launch\w*|"
                       r"pending|approved|effective)\b", re.I)


def split_dateline(text: str) -> tuple[str, str]:
    """(dateline, rest): a news release's leading place-and-date line ("CITY, Country, Month D, YYYY -"), at most
    DATELINE_MAX_WORDS words, kept verbatim as its own field; ("", text) when there is none."""
    t = " ".join((text or "").split())
    m = _DATELINE.match(t)
    if m and len(m.group(0).split()) <= DATELINE_MAX_WORDS and m.end() < len(t):
        return m.group(0).strip(), t[m.end():]
    return "", t


def bounded_excerpt(text: str, max_words: int) -> str:
    """At most max_words words, "…" markers included, of whole sentences. Unchanged when the text fits. Otherwise
    the lead sentence and the most factual sentences (dates, figures, schedule) are kept in their order, and every
    omission is marked "…". A first sentence longer than the bound is cut, marked. (The dateline is split off first
    by the caller, split_dateline.)"""
    t = " ".join((text or "").split())
    if len(t.split()) <= max_words:
        return t
    head = ""
    parts = _UNIT_SPLIT.split(t)
    units, gaps = [], []  # gaps[i]: an ellipsis already stood between unit i and unit i+1 in the source
    for n, p in enumerate(parts):
        if n % 2 == 0:
            if p.strip():
                units.append(p.strip())
                gaps.append(False)
        elif units and ("." in p or "…" in p):
            gaps[-1] = True

    def value(i):
        u = units[i]
        return (4 if i == 0 else 0) + 2 * bool(_DATE_WORDS.search(u)) + 2 * bool(re.search(r"\d", u)) \
            + bool(_SCHEDULE.search(u))
    keep, used = [], 0
    for i in sorted(range(len(units)), key=lambda i: (-value(i), i)):
        n = len(units[i].split()) + 1  # its words and, at most, one "…" after it
        if used + n <= max_words - 1:  # one more "…" may stand before the first kept sentence
            keep.append(i)
            used += n
    if not keep:
        return f"{head} {' '.join(units[0].split()[:max_words - 1])} …".strip()
    keep.sort()
    out = [head] if head else []
    if keep[0] != 0:
        out.append("…")
    for k, i in enumerate(keep):
        out.append(units[i])
        nxt = keep[k + 1] if k + 1 < len(keep) else None
        if (nxt is not None and (nxt != i + 1 or gaps[i])) or (nxt is None and i != len(units) - 1):
            out.append("…")
    return " ".join(out)


# --- the organization's own statements ------------------------------------------------------------------------

def _quoted(excerpt: str) -> list[str]:
    return [q.strip() for q in re.findall(r"\"([^\"]{8,})\"", excerpt or "")]


def _day(e: dict) -> str | None:
    from deal_prep import evidence_profile as ep
    return ep.publication_day(e) if ep.date_status(e) == "publication_date_stated" else None


def _age(day: str | None, as_of: date | None) -> int | None:
    if not day or as_of is None:  # without a briefing date nothing counts as recent
        return None
    n = (as_of - date.fromisoformat(day)).days
    return n if n >= 0 else None


def fmt(day: str) -> str:
    d = date.fromisoformat(day)
    return f"{d.day} {_MONTHS[d.month - 1]} {d.year}"


def _title(index: dict, doc: str) -> str | None:
    from deal_prep import evidence_profile as ep
    for e in index.values():
        if e.get("document_id") == doc and ep.statement_form(e) == "document_header":
            m = _HEADER_TITLE.match(" ".join((e.get("excerpt") or "").split()))
            if m:
                return m.group(1).strip()
    return None


def _header_id(index: dict, doc: str) -> str | None:
    from deal_prep import evidence_profile as ep
    return next((eid for eid, e in index.items()
                 if e.get("document_id") == doc and ep.statement_form(e) == "document_header"), None)


def statements(bundle: dict, index: dict) -> list[dict]:
    """Verbatim statements of the organization's primary records (see PRIMARY) in the drafting input."""
    from deal_prep import evidence_profile as ep
    domain = (bundle.get("identity") or {}).get("domain")
    out = []
    for eid, e in index.items():
        if e.get("info_origin") != "public_source" or not e.get("document_id") or e.get("source") == "external_news":
            continue
        if ep.statement_form(e) != "verbatim_excerpt" or ep.source_class(e, domain) not in PRIMARY:
            continue
        for text in _quoted(e["excerpt"]):
            out.append({"eid": eid, "doc": e["document_id"], "day": _day(e), "text": text})
    return out


def _name_words(bundle: dict) -> set[str]:
    name = (bundle.get("identity") or {}).get("name", "")
    return {w.casefold() for w in re.findall(r"[A-Za-z][A-Za-z-]+", name)}


def subject_forms(bundle: dict) -> list[str]:
    """How a sentence names the organization as its subject: its name, its registered aliases and the first
    distinctive word of its name (letters of any alphabet: "Ørsted")."""
    identity = bundle.get("identity") or {}
    names = [identity.get("name") or ""] + list(identity.get("aliases") or [])
    if identity.get("org_id"):
        try:
            from deal_prep import provenance
            names += list(provenance.load_registry().get(identity["org_id"], {}).get("aliases") or [])
        except Exception:  # no registry available: the name alone
            pass
    words = [w for n in names for w in re.findall(r"[^\W\d_][\w'’&-]*", n) if len(w) >= 3]
    forms = {n.strip() for n in names if n.strip()} | set(words[:1])
    return sorted(forms, key=len, reverse=True)


def self_description(text: str, forms: list[str]) -> bool:
    """The sentence describes the organization itself (see _DESCRIBE): it is the subject, then what it is or does;
    or "<Name>, a/an/the ..." at the start."""
    subject = "|".join([re.escape(f) for f in forms] + [r"the (?:group|company)", r"our (?:group|company)", "we"])
    corp = r"(?:\s+(?:group|company|corporation|plc|inc\.?|ltd\.?|limited|a/s|ag|sa|se|n\.v\.))?"
    t = text.strip().lstrip("\"'“”‘’ ")
    words = re.findall(r"[^\W\d_][\w'’-]{3,}", t)
    if len(words) >= 3 and sum(w[0].isupper() for w in words) >= 0.6 * len(words):
        return False  # a title-case headline ("Acme Provides Update on Merger Agreement") is not a self-description
    for form in forms:  # longest first: a word of the name ("Acme Build Group", "Acme Works") is never read as a verb
        t = re.sub(rf"(?<!\w){re.escape(form)}(?!\w)", "\x00", t, flags=re.I)
    subject = "\x00|" + subject
    if re.match(rf"(?:the\s+)?(?:{subject}){corp},\s+(?:a|an|the)\s", t, re.I):
        return True
    return bool(re.match(rf"{_INTRO}(?:the\s+)?(?:{subject}){corp},?\s+(?:{_DESCRIBE})", t, re.I))


def metric_kind(text: str) -> str:
    """The headline metric a statement reports, by its first mention: 'profit', 'topline' (revenue, sales),
    'operating' (EBITDA, EBIT, operating profit), or ''."""
    found = []
    for kind, pattern in (("operating", _OPERATING), ("profit", _PROFIT), ("topline", _TOPLINE)):
        m = pattern.search(text)
        if m:
            found.append((m.start(), kind))
    if not found:
        return ""
    found.sort()
    # "operating profit" is matched by both: the operating pattern starts first
    return found[0][1]


def statement_kind(s: dict, identity: list | tuple = ()) -> str:
    """'identity', 'result', 'guidance', 'trading', 'development', 'figure' or '' (see the C2 note above)."""
    from deal_prep import evidence_profile as ep
    from deal_prep.contract import figures
    t = s["text"]
    if s in identity:
        return "identity"
    forward = bool(ep._FORWARD.search(t) or _OUTLOOK.search(t))
    figs = figures(t)
    if figs and not forward and not _RANGE.search(t) and metric_kind(t):
        return "result"
    if forward and (figs or _GUIDANCE_CHANGE.search(t)):
        return "guidance"
    if _TRADING.search(t):
        return "trading"
    if _DEVELOPMENT.search(t):
        return "development"
    return "figure" if figs and not forward else ""


def statement_score(s: dict, kind: str) -> int:
    score = _KIND_SCORE.get(kind, 0)
    if kind == "result":
        score += {"profit": 3, "topline": 2, "operating": 2}.get(metric_kind(s["text"]), 0)
        score += 2 * bool(_DIRECTION.search(s["text"])) + bool(_REASON.search(s["text"]))
    elif kind == "figure":
        score += bool(_DIRECTION.search(s["text"]))
    return score


def key_figure(text: str) -> str | None:
    """The figure a statement is about: the first amount with a currency, else with a scale, else a figure that is not
    a percentage, else a percentage (years, dates, identifiers and fiscal notation like "2025/26" excluded)."""
    from deal_prep import figure_verify, numbers
    masked = figure_verify._masked(text)
    nums = [n for n in numbers.read(masked) if not numbers.is_year(n.literal)
            and masked[n.start - 1:n.start] != "/" and masked[n.end:n.end + 1] != "/"]

    def rank(n):
        money = bool(figure_verify.currency(text, n.start, n.end, n.suffix))
        scaled = figure_verify.scale(text, n.end, n.suffix) != 1.0
        percent = figure_verify.unit(text, n.end, n.suffix) in ("percent", "points")
        return (0 if money else 1 if scaled else 3 if percent else 2, n.start)
    return min(nums, key=rank).literal if nums else None


def _position(s: dict) -> int:
    m = re.search(r"#(\d+)$", s["eid"])
    return int(m.group(1)) if m else 0


def developments(a: dict, taken: list[dict] = ()) -> dict:
    """The latest material developments (see the C2 note above): {"newest_day", "results_day", "chosen": [(statement,
    kind)], "essential": [statement]}; empty when no dated official document lies within LATEST_DAYS. `taken`:
    statements other company topics already require (outlook, ownership, leadership): not repeated here."""
    from deal_prep import numbers
    st = [s for s in a["statements"] if s["day"] and (_age(s["day"], a["as_of"]) or 0) <= LATEST_DAYS
          and _age(s["day"], a["as_of"]) is not None]
    if not st:
        return {}
    kinds = {id(s): statement_kind(s, a["identity"]) for s in st}
    newest = max(s["day"] for s in st)
    pool = [s for s in st if s["day"] == newest]
    results_day = newest
    if not any(kinds[id(s)] == "result" for s in pool):
        older = [s for s in st if kinds[id(s)] == "result"]
        if older:
            results_day = max(s["day"] for s in older)
            pool += [s for s in st if s["day"] == results_day]
    from deal_prep import chronology
    # a historical statement that gives no date (I4: "date not stated", never dated) is not a dated development
    pool = [s for s in pool if kinds[id(s)] not in ("identity", "") and s not in taken
            and not chronology.undated_history((a.get("index") or {}).get(s["eid"]) or {})]
    ranked = sorted(pool, key=lambda s: (-statement_score(s, kinds[id(s)]), s["day"] != newest, _position(s)))

    def key(s):  # what a statement is about: its metric and its key figure's value
        k = key_figure(s["text"])
        return metric_kind(s["text"]), frozenset(numbers.values(k)) if k else frozenset()
    chosen, seen = [], set()

    def take(s):
        if s in chosen or len(chosen) >= MAX_DEVELOPMENTS:
            return
        k = key(s)
        if k[1] and k in seen:  # the same figure for the same metric (an announcement and its report)
            return
        seen.add(k)
        chosen.append(s)
    results = [s for s in ranked if kinds[id(s)] == "result" and s["day"] == results_day]
    for want in ("profit", "topline"):  # the headline results
        best = next((s for s in results if metric_kind(s["text"]) == want), None)
        if best:
            take(best)
    if not any(metric_kind(s["text"]) == "topline" for s in chosen):  # no revenue: the operating result, if it moved
        best = next((s for s in results if metric_kind(s["text"]) == "operating"
                     and _DIRECTION.search(s["text"])), None)
        if best:
            take(best)
    update = next((s for s in ranked if s["day"] == newest and kinds[id(s)] in ("trading", "guidance")), None)
    if update and (newest != results_day or not chosen):  # a newer trading update or guidance change
        take(update)
        if not key_figure(update["text"]):  # a statement without a figure: also its newest figure
            figured = next((s for s in ranked if s["day"] == newest and kinds[id(s)] == "guidance"
                            and key_figure(s["text"])), None)
            if figured:
                take(figured)
    essential = list(chosen)
    for s in ranked:
        if len(chosen) >= max(DEFAULT_DEVELOPMENTS, len(essential)):
            break
        if statement_score(s, kinds[id(s)]) >= _KIND_SCORE["development"]:
            take(s)
    if not chosen:  # no results, guidance, update or development: the newest release's own figures (a milestone)
        for s in ranked:
            if s["day"] == newest and len(chosen) < DEFAULT_DEVELOPMENTS:
                take(s)
        essential = chosen[:1]
    return {"newest_day": newest, "results_day": results_day,
            "chosen": [(s, kinds[id(s)]) for s in chosen], "essential": essential}


def identity_facts(statements: list[dict], exclude: list[dict]) -> list[dict]:
    """The first statement (dated ones first) giving each identity fact: where it is based, where it is listed, its
    scale. Forward-looking statements are not facts about what the organization is."""
    from deal_prep import evidence_profile as ep
    out = []
    ordered = sorted(statements, key=lambda s: s["day"] is None)
    for _, pattern in _FACTS:
        found = next((s for s in ordered if s not in exclude and s not in out and pattern.search(s["text"])
                      and not ep._FORWARD.search(s["text"])), None)
        if found:
            out.append(found)
    return out


def analyse(bundle: dict, index: dict | None = None, as_of: date | None = None) -> dict:
    """What the organization's primary records say about it, by kind (used by the contract, the unknowns and
    the agent). as_of: the briefing date (default: the bundle's created_at; without one, nothing is dated)."""
    from deal_prep.contract import figures, terms
    from deal_prep.evidence import evidence_index
    from deal_prep import evidence_profile as ep
    index = index if index is not None else evidence_index(bundle)
    if as_of is None and bundle.get("created_at"):
        as_of = date.fromisoformat(bundle["created_at"][:10])
    st = statements(bundle, index)
    forms = subject_forms(bundle)
    # C2: a figure another source contradicts is not a fact about who the organization is (the contested topic gives
    # both sides, unresolved)
    rel = ep.figure_relations(list(index.values()), (bundle.get("identity") or {}).get("domain"))
    uncontested = [s for s in st if not rel.get(s["eid"], {}).get("contested_with")]
    own_words = []  # dated self-descriptions first; one that mostly repeats a chosen one adds nothing (C2)
    for s in sorted((s for s in uncontested if self_description(s["text"], forms)), key=lambda s: s["day"] is None):
        words = set(terms(s["text"], 5))
        seen = set().union(*(set(terms(x["text"], 5)) for x in own_words)) if own_words else set()
        if words and len(words - seen) < len(words) / 2:
            continue
        own_words.append(s)
        if len(own_words) == MAX_SELF_DESCRIPTIONS:
            break

    def within(s, days):
        a = _age(s["day"], as_of)
        return a is not None and a <= days
    about_outlook = {d for d in {s["doc"] for s in st} if _OUTLOOK_TITLE.search(_title(index, d) or "")}

    def outlook(s):  # an outlook statement, or any statement of a release about the outlook (excerpt fragments)
        return bool(_OUTLOOK.search(s["text"])) or s["doc"] in about_outlook
    a = {"as_of": as_of, "statements": st, "index": index,
         "identity": own_words + identity_facts(uncontested, own_words), "self_described": bool(own_words),
         "ownership": [s for s in st if within(s, EVENT_DAYS) and _OWNERSHIP.search(s["text"])],
         "leadership": [s for s in st if within(s, EVENT_DAYS) and _CHANGE.search(s["text"])
                        and _ROLE.search(s["text"])],
         "outlook": [s for s in st if within(s, EVENT_DAYS) and outlook(s) and figures(s["text"])],
         "results": [s for s in st if within(s, LATEST_DAYS) and figures(s["text"]) and not outlook(s)
                     and not ep._FORWARD.search(s["text"]) and not _RANGE.search(s["text"])],
         "financial": any(_FINANCIAL.search(s["text"]) and figures(s["text"]) for s in st),
         "outlook_docs": about_outlook}
    own = a["ownership"]
    if own:
        days = sorted({s["day"] for s in own})
        first = min(own, key=lambda s: s["day"])["doc"]
        later = [s for s in own if s["doc"] != first]
        word = _OWNERSHIP.search(" ".join(s["text"] for s in own if s["doc"] == first)).group(0).casefold()
        kind = next((noun for stem, noun in _KINDS if stem in word), "transaction")
        a["ownership_info"] = {"first_doc": first, "first_day": days[0], "newest_day": days[-1], "kind": kind,
                               "pending": any(_PENDING.search(s["text"]) for s in (later or own))}
    return a


# --- contract topics (1, 3, 4) ----------------------------------------------------------------------------------

def _date_marker(day: str) -> str:
    d = date.fromisoformat(day)
    month = _MONTHS[d.month - 1]
    m = rf"(?:{month}|{month[:3]}\.?)"
    return rf"\b(?:{d.day}\s+{m}|{m}\s+{d.day}\b|{d.isoformat()})|{_PERIOD_WORDS}"


def company_topics(bundle: dict, index: dict) -> list[dict]:
    """Company essentials for an introduction or a general meeting (see the module docstring), by priority."""
    from deal_prep.contract import _num_markers, _topic, _word_markers, figures, terms
    if not ENABLED or bundle.get("purpose") not in ("introduction", "general"):
        return []
    a = analyse(bundle, index)
    name = (bundle.get("identity") or {}).get("name") or "the organization"
    exclude = _name_words(bundle)
    topics = []
    if a["identity"]:
        ids = list(dict.fromkeys(s["eid"] for s in a["identity"]))[:5]  # self-descriptions first, then facts
        undated = any(s["day"] is None for s in a["identity"])
        text = " ".join(s["text"] for s in a["identity"])
        said = (f"Say who {name} is and what it does, in its own words, attributed to its source, adding where it is "
                f"based, where it is listed and its scale when the cited evidence states them"
                if a["self_described"] else
                f"The sources contain no description of {name} in its own words: state only what the cited facts "
                f"establish (where it is based, where it is listed, its scale), attributed; do not describe its "
                f"business beyond them")
        topics.append(_topic("company:identity", "company_overview",
                             said + (" (an undated page: say 'date not stated')" if undated else "") + ". One item.",
                             [ids], _word_markers(terms(text, 6, exclude=exclude))))
    if a["ownership"]:
        o = a["ownership_info"]
        first = [s["eid"] for s in a["ownership"] if s["doc"] == o["first_doc"]]
        later = [s["eid"] for s in a["ownership"] if s["doc"] != o["first_doc"]]
        text = " ".join(s["text"] for s in a["ownership"])
        topics.append(_topic("company:ownership", "company_overview",
                             f"State this ownership development as the sources give it: what was announced "
                             f"({fmt(o['first_day'])}), with its terms as stated"
                             + (f", and its newest stated status ({fmt(o['newest_day'])})" if later else "")
                             + ", each attributed and dated. "
                             + ("It is pending: say so, and never state a closing date, an approval or an outcome as "
                                "fact. " if o["pending"] else "")
                             + f"Facts about the other organizations involved belong to them, not to {name}.",
                             [first, later], _num_markers(figures(text))
                             + _word_markers(["acquir", "merger", "transaction", "pending", "spin", "subsidiar",
                                              "closing", "divest", "takeover"])))
    if a["leadership"]:
        newest = max(s["day"] for s in a["leadership"])
        chosen = [s for s in a["leadership"] if s["day"] == newest]
        text = " ".join(s["text"] for s in chosen)
        topics.append(_topic("company:leadership", "company_overview",
                             f"State this leadership change as the source states it ({fmt(newest)}): who holds the "
                             f"role now, and since when.", [[s["eid"] for s in chosen]],
                             _word_markers(terms(text, 5, exclude=exclude))))
    if a["outlook"]:
        newest = max(s["day"] for s in a["outlook"])
        chosen = [s for s in a["outlook"] if s["day"] == newest]
        older = sorted({s["day"] for s in a["outlook"] if s["day"] != newest})
        topics.append(_topic("company:outlook", "company_overview",
                             f"State the newest outlook exactly as the source gives it ({fmt(newest)}), attributed "
                             f"and dated."
                             + (f" The earlier outlook ({', '.join(fmt(d) for d in older)}) is superseded: if you "
                                f"mention it, label it superseded; an update is not a conflict." if older else ""),
                             [[s["eid"] for s in chosen]], _num_markers(figures(" ".join(s["text"] for s in chosen)))))
    taken = list(a["ownership"]) + list(a["leadership"]) + (
        [s for s in a["outlook"] if s["day"] == max(x["day"] for x in a["outlook"])] if a["outlook"] else []) +         [s for s in a["statements"] if s["doc"] in a["outlook_docs"]]  # a release about the outlook is the outlook's
    dev = developments(a, taken)
    if dev:
        days = [dev["newest_day"]] + ([dev["results_day"]] if dev["results_day"] != dev["newest_day"] else [])
        sets = [(day, [(s, k) for s, k in dev["chosen"] if s["day"] == day]) for day in days]
        sets = [(day, chosen) for day, chosen in sets if chosen]
        for n, (day, chosen) in enumerate(sets):  # one set keeps the stable id; a second, older one is the results
            topics.append(_development_topic(
                "company:latest_release" if n == 0 else "company:latest_results", day, chosen,
                [s for s in dev["essential"] if s["day"] == day], a, index, name, exclude,
                older=day != dev["newest_day"]))
    return topics


# C2 (owner-approved 2026-11-17): every other meeting purpose gets ONE compact company topic (company:brief): who the
# organization is, in a clause, and its most material recent development, dated. It is added after the topic cap, so it
# never displaces a relationship or commercial topic; its requirement keeps those first and, in a negotiation, forbids
# inferring the customer's budget, cost pressure, commercial priorities or negotiating stance from public results.
BRIEF_PURPOSES = ("follow_up", "negotiation", "product_demo")
_BRIEF_PRIORITY = {"follow_up": "the relationship history and open commitments come first",
                   "negotiation": "the proposals, approval requirements, open commercial issues and commitments come "
                                  "first",
                   "product_demo": "the capabilities to demonstrate and why each matters come first"}


# Final compact-brief correction (owner-approved 2026-11-18): a change among the brief's developments is stated with its
# direction and the source's reason, as the full development topic already requires; no reason is ever supplied.
BRIEF_CHANGE = ("For a change, state its direction and the reason the source gives: make the direction explicit when "
                "the evidence supports it, and never supply a reason the source does not give.")


def brief_topics(bundle: dict, index: dict) -> list[dict]:
    from deal_prep import numbers
    from deal_prep.contract import _topic, _word_markers, terms
    purpose = bundle.get("purpose")
    if not ENABLED or purpose not in BRIEF_PURPOSES:
        return []
    a = analyse(bundle, index)
    name = (bundle.get("identity") or {}).get("name") or "the organization"
    exclude = _name_words(bundle)
    who = a["identity"][:2]
    dev = developments(a)
    top = ((dev.get("essential") or [s for s, _ in dev.get("chosen", [])])[:2]) if dev else []
    if not who and not top:
        return []
    ids = {s["eid"] for s in who + top} | {h for s in top if (h := _header_id(index, s["doc"]))}
    markers, labels = [], []
    words = _word_markers(terms(" ".join(s["text"] for s in who), 6, exclude=exclude)) if who else []
    if words:
        markers.append(f"(?:{'|'.join(words)})")
        labels.append("who it is")
    if top:
        k = key_figure(top[0]["text"])
        dev_words = _word_markers(terms(top[0]["text"], 6, exclude=exclude))
        if k or dev_words:
            markers.append(numbers.marker(k) if k else f"(?:{'|'.join(dev_words)})")
            labels.append("its most material recent development" + (f" ({k})" if k else ""))
        markers.append(_date_marker(top[0]["day"]))
        labels.append("the development's date")
    said = (f"In one or two items in company_overview, give a compact view of {name}: who it is, in a clause"
            + (", and its most material recent development, attributed and dated, each figure exactly as the source "
               "gives it, with its period and currency" if top else "")
            + "." + " " + BRIEF_CHANGE
            + f" Keep it brief: {_BRIEF_PRIORITY[purpose]}.")
    said += (f" State public developments only as facts with their source and date; never infer {name}'s budget, cost "
             f"pressure, commercial priorities or negotiating stance from them." if purpose == "negotiation" else
             f" Never infer {name}'s budget or priorities from its public results.")
    return [{**_topic("company:brief", "company_overview", said, [sorted(ids)], markers), "require_all": True,
             "labels": labels}]


_KIND_LABEL = {"result": "the reported result", "guidance": "the guidance or expectation",
               "trading": "the trading update", "development": "the business development", "figure": "the figure"}


def _development_topic(tid: str, day: str, chosen: list, essential: list, a: dict, index: dict, name: str,
                       exclude: set, older: bool = False) -> dict:
    """One dated set of developments: every chosen statement is evidence; each ESSENTIAL statement's key figure (or,
    without a figure, its content words) and the date must be stated (require_all), so a briefing that keeps the
    release but drops its headline result is not counted as covering it (C2)."""
    from deal_prep import numbers
    from deal_prep.contract import _topic, _word_markers, terms
    docs = sorted({s["doc"] for s, _ in chosen})
    headers = {h for d in docs if (h := _header_id(index, d))}
    titles = [t for d in docs if (t := _title(index, d))]
    kinds = {id(s): k for s, k in chosen}
    markers, labels = [], []
    for s in essential or [chosen[0][0]]:
        k = key_figure(s["text"])
        if k:
            markers.append(numbers.marker(k))
            labels.append(f"{_KIND_LABEL.get(kinds.get(id(s)), 'the figure')} ({k})")
        else:
            words = _word_markers(terms(s["text"], 6, exclude=exclude))
            if words:
                markers.append(f"(?:{'|'.join(words)})")
                labels.append(_KIND_LABEL.get(kinds.get(id(s)), "the statement"))
    markers.append(_date_marker(day))
    labels.append("the release or period and its date")
    recent = (_age(day, a["as_of"]) or 0) <= RECENT_DAYS
    source = ("'" + "', '".join(titles) + "', " if titles else "")
    if not older:
        said = (f"From {name}'s newest official release(s) ({source}published {fmt(day)}): state only these "
                f"developments (at most {DEFAULT_DEVELOPMENTS} unless more are essential results), not the release's "
                f"other figures, as the source states them, attributed and dated")
    else:
        said = (f"{name}'s latest full-period results ({source}published {fmt(day)}, older than its newest release): "
                f"state the headline results as the source states them, attributed, with their period and "
                f"publication date")
    said += (": each figure exactly as written, with its currency and period; a reported result as a result and "
             "guidance or an expectation as an expectation; for a change, its direction and the reason the source "
             "gives. Never combine figures from different periods or currencies.")
    return {**_topic(tid, "recent_developments" if recent else "company_overview", said,
                     [sorted({s["eid"] for s, _ in chosen} | headers)], markers),
            "require_all": True, "labels": labels}


# The research's own gap texts (orchestrator.gather_research) when no relationship records were found.
_NO_RECORDS = ("No prior relationship records", "No internal records for")


def new_lead(bundle: dict) -> bool:
    """The research searched and found no relationship records for this organization: its own gap says so."""
    return any(str(g).startswith(_NO_RECORDS) for g in bundle.get("gaps") or [])


_SYSTEMS = r"\b(?:systems?|tools?|software|platforms?|today|currently|current|in use)\b"
_DECIDE = r"\b(?:decid\w*|decision\w*|approv\w*|authori\w*|evaluat\w*|sign[- ]off|who)\b"
_TIMING = r"\b(?:timing|timelines?|time ?frames?|when|schedul\w*|plann\w*|plans?)\b"


# C3 (owner-approved 2026-11-17): the lead state, from the organization's approved, current records only. A draft or
# superseded record (a draft meeting note) never counts: it neither makes a lead established nor answers a question.
CORRESPONDENCE_TYPES = ("correspondence",)
ESTABLISHED_TYPES = ("meeting_notes", "meeting_record", "proposal")


def approved_records(bundle: dict) -> list[dict]:
    """The organization's approved, current relationship records in the research (knowledge-base records and
    approved meeting records)."""
    from deal_prep.selection import current
    org = (bundle.get("identity") or {}).get("org_id")
    internal = bundle.get("internal") or {}
    out = []
    for topic in ("relationship_history", "meeting_history"):
        for e in (internal.get(topic) or {}).get("evidence", []):
            meta = e.get("metadata") or {}
            if current(meta) and (topic == "meeting_history" or meta.get("customer_org_id") == org):
                out.append(e)
    return out


def lead_state(bundle: dict) -> str:
    """'new': the research found no relationship records; 'early_stage': the approved records are correspondence
    only (an inquiry, outreach, a reply), with no approved meeting record and no approved proposal; 'established': an
    approved meeting record or proposal exists; '' otherwise (nothing approved to read)."""
    if new_lead(bundle):
        return "new"
    types = {(e.get("metadata") or {}).get("doc_type") for e in approved_records(bundle)}
    if types & set(ESTABLISHED_TYPES):
        return "established"
    return "early_stage" if types and types <= set(CORRESPONDENCE_TYPES) else ""


_MONTH_NAMES = "|".join(_MONTHS)
# (label, the question, what stays unknown, coverage marker, what in approved correspondence already addresses it)
QUALIFICATION = (
    ("current systems and workflows",
     "which systems and workflows {name} uses today for the documents in question",
     "which systems and workflows {name} uses today for the documents in question",
     r"\b(?:systems?|tools?|software|platforms?|workflows?|processes|today|currently|current|in use)\b",
     r"\b(?:we (?:currently |now |still )?(?:use|run|keep|store|manage)|(?:currently|today) (?:use|run|keep|store|"
     r"manage)|our (?:current|existing) (?:systems?|tools?|platforms?|software|process(?:es)?|workflows?))\b"),
    ("who decides and how approval works",
     "who would evaluate and decide on tools of this kind, and how approval works",
     "who at {name} would evaluate and decide on tools of this kind, and how approval works",
     _DECIDE,
     r"\b(?:decision[- ]makers?|will (?:decide|approve|sign off)|(?:approval|sign[- ]off) (?:from|by)|approved by|"
     r"must approve|steering (?:committee|group)|procurement (?:process|team|committee))\b"),
    ("budget or funding status",
     "whether budget or funding for this is available or still to be authorized (ask; never assume either)",
     "whether budget or funding is available or authorized (none is assumed)",
     r"\b(?:budget\w*|funding|funded)\b",
     r"\b(?:budget\w*|funding|funded)\b"),
    ("timing and decision process",
     "the timing and the steps of any decision",
     "the timing of any decision",
     r"\b(?:timing|timelines?|time ?frames?|when|schedul\w*|plann\w*|plans?|deadlines?|go[- ]live|(?:financial|"
     r"fiscal) year|quarter)\b",
     rf"\b(?:(?:next|this|the coming) (?:financial |fiscal |calendar )?(?:year|quarter)|(?:by|before|from) (?:the end "
     rf"of )?(?:Q[1-4]|H[12]|{_MONTH_NAMES}|20\d\d)|within (?:the next )?\w+ (?:weeks|months)|timelines?|"
     rf"time ?frames?|go[- ]live|deadlines?)\b"),
    ("scope, security, deployment or integration constraints",
     "any requirements or constraints for such tools: scope, security, hosting or deployment, and integration with "
     "existing systems",
     "{name}'s requirements or constraints (scope, security, hosting or deployment, integration)",
     r"\b(?:requirements?|constraints?|scope|security|hosting|hosted|deploy\w*|cloud|on[- ]prem\w*|integrat\w*|"
     r"single sign[- ]on|SSO|residency)\b",
     r"\b(?:hosted|hosting|data residency|on[- ]prem\w*|cloud|single sign[- ]on|SSO|SAML|integrat\w*|security|"
     r"ISO ?27001|SOC ?2|workflows?|\d[\d,]*\s+users)\b"),
)


def qualification(bundle: dict) -> list[dict]:
    """For an early-stage lead: each qualification area, with the approved correspondence passages that already
    address it (then the briefing builds on them instead of asking again). Draft notes are never read."""
    passages = [e for e in approved_records(bundle)
                if (e.get("metadata") or {}).get("doc_type") in CORRESPONDENCE_TYPES]
    name = (bundle.get("identity") or {}).get("name") or "the organization"
    return [{"label": label, "question": q.format(name=name), "unknown": u.format(name=name), "marker": marker,
             "addressed": sorted(e["evidence_id"] for e in passages
                                 if re.search(addressed, e.get("text") or e.get("excerpt") or "", re.I))}
            for label, q, u, marker, addressed in QUALIFICATION]


def discovery_topics(bundle: dict, index: dict) -> list[dict]:
    """Discovery questions (meeting_recommendations, no evidence required): the buying context for a new lead; C3:
    qualification questions for an early-stage lead (approved correspondence only), building on what the
    correspondence already addresses; and the effect of a pending ownership change. Neutral: never a relationship,
    need, budget or intention to buy that the records do not state. Introductions and general meetings only."""
    from deal_prep.contract import _topic
    if not ENABLED or bundle.get("purpose") not in ("introduction", "general"):
        return []
    name = (bundle.get("identity") or {}).get("name") or "the organization"
    topics = []
    if lead_state(bundle) == "early_stage":
        areas = qualification(bundle)
        ask = [a["question"] for a in areas if not a["addressed"]]
        built = [f"{a['label']} ({', '.join(i for i in a['addressed'] if i in index) or 'the correspondence'})"
                 for a in areas if a["addressed"]]
        text = (f"{name} has corresponded with us, but no approved meeting record or proposal exists: qualify the "
                f"lead with at most five questions." + (f" Ask {'; '.join(ask)}." if ask else "")
                + (f" The correspondence already addresses {'; '.join(built)}: build on what it says (confirm or "
                   f"update it); do not ask it afresh." if built else "")
                + " Ask neutrally: do not imply a need, a budget, a decision maker or an intention to buy that the "
                  "correspondence does not state.")
        topics.append({**_topic("discovery:qualification", "meeting_recommendations", text, [],
                                [a["marker"] for a in areas]),
                       "require_all": True, "home_only": True, "no_gap": True, "labels": [a["label"] for a in areas]})
    if new_lead(bundle):
        topics.append({**_topic("discovery:buying_context", "meeting_recommendations",
                                f"Ask discovery questions about what the evidence does not establish: which systems "
                                f"{name} uses today for the documents in question, who would evaluate or decide on "
                                f"tools of this kind and how, and on what timing. Ask neutrally: do not imply a "
                                f"relationship, a need, a budget or an intention to buy.", [],
                                [_SYSTEMS, _DECIDE, _TIMING]),
                       "require_all": True, "home_only": True, "no_gap": True,
                       "labels": ["current systems", "who decides and how", "timing"]})
    a = analyse(bundle, index)
    if a["ownership"] and a["ownership_info"]["pending"]:
        topics.append({**_topic("discovery:ownership_change", "meeting_recommendations",
                                f"Ask how the pending {a['ownership_info']['kind']} affects who decides on tools of "
                                f"this kind at {name}, and when, without assuming its outcome.", [],
                                [r"\b(?:transaction|merger|acquisition|ownership|closing|spin|takeover|divest)\w*",
                                 rf"{_DECIDE}|{_TIMING}|\bafter\b"]),
                       "require_all": True, "home_only": True, "no_gap": True,
                       "labels": ["the pending change", "who decides or when"]})
    return topics


def undated_documents(index: dict) -> dict[str, list[str]]:
    """Public documents (and news items) whose page shows no date: {document key: evidence IDs}."""
    from deal_prep import evidence_profile as ep
    out: dict[str, list[str]] = {}
    for eid, e in index.items():
        if e.get("info_origin") == "public_source" and ep.date_status(e) == "publication_date_unknown" \
                and ep.statement_form(e) != "document_header":
            out.setdefault(ep.document_key(e), []).append(eid)
    return {k: sorted(v) for k, v in out.items()}


def undated_topics(index: dict) -> list[dict]:
    from deal_prep.contract import _topic
    if not ENABLED:
        return []
    return [{**_topic(f"undated:page:{doc}", "company_overview",
                      "This page shows no publication date. Anything you use from it must say 'date not stated'; "
                      "never add a date.", [ids], [r"date not stated|undated|no date|not dated"]),
             "conditional": True} for doc, ids in sorted(undated_documents(index).items())]


# --- business unknowns (3) ----------------------------------------------------------------------------------------

def unknowns(bundle: dict, as_of: date | None = None) -> list[dict]:
    """One required disclosure listing what the evidence does not establish (introduction, general meeting, product
    demonstration). A new lead: current systems, who decides and how, any need or timeline (none assumed). C3: an
    early-stage lead: the qualification areas its approved correspondence does not address. From the evidence: a
    pending ownership change; financial results that no source states.
    C2: a follow-up or negotiation briefing discloses only that no recent official results or announcements are in
    the evidence, when none is (its compact company brief then has nothing to state)."""
    if not ENABLED or not bundle.get("identity"):
        return []
    name = bundle["identity"]["name"]
    if bundle.get("purpose") in ("follow_up", "negotiation"):
        if developments(analyse(bundle, as_of=as_of)).get("chosen"):
            return []
        return [{"id": "unknown:business", "kind": "gap", "text": "Not established by the evidence: "
                 f"{name}'s recent official results or announcements (none is in the evidence)."}]
    if bundle.get("purpose") not in ("introduction", "general", "product_demo"):
        return []
    a = analyse(bundle, as_of=as_of)
    parts = []
    if lead_state(bundle) == "early_stage":  # C3: what the approved correspondence does not address
        parts += [a["unknown"] for a in qualification(bundle) if not a["addressed"]]
    if new_lead(bundle):
        parts += [f"which document-management or document-control systems {name} uses today",
                  f"who at {name} would evaluate or decide on tools of this kind, and how such decisions are made",
                  f"whether {name} has any related need, initiative or timeline (none is assumed)"]
    if a["ownership"] and a["ownership_info"]["pending"]:
        o = a["ownership_info"]
        parts.append(f"how the pending {o['kind']} affects who decides and when, and its status after "
                     f"{fmt(o['newest_day'])} (the newest statement about it)")
    if a["statements"] and not a["financial"]:
        parts.append(f"{name}'s financial results (no source in the evidence states them)")
    if not parts:
        return []
    return [{"id": "unknown:business", "kind": "gap", "text": "Not established by the evidence: " + "; ".join(parts)
             + "."}]


# --- research coverage and the agent (2) -------------------------------------------------------------------------

def public_only(bundle: dict) -> bool:
    from deal_prep import provenance
    org = (bundle.get("identity") or {}).get("org_id")
    return bool(org) and provenance.load_registry().get(org, {}).get("public_only") is True


def relationship_query(query: str) -> bool:
    return bool(_RELATIONSHIP_QUERY.search(query or ""))


def coverage_gaps(bundle: dict) -> list[str]:
    """Company coverage still missing from the evidence (what the agent may usefully search for)."""
    if not ENABLED or not (bundle.get("identity") or {}).get("org_id"):
        return []
    a = analyse(bundle)
    gaps = []
    if not a["identity"]:
        gaps.append("no passage in which the organization describes itself")
    if not a["results"]:
        gaps.append(f"no dated official release with figures from the last {LATEST_DAYS} days")
    if not a["financial"]:
        gaps.append("no financial results")
    return gaps


def agent_view(bundle: dict, ctx: dict) -> dict:
    """The agent's context under I7: a public-only organization's relationship gap is not researchable."""
    if not ENABLED:
        return ctx
    ctx = dict(ctx)
    if public_only(bundle):
        ctx["gaps"] = [g for g in ctx["gaps"] if not g.startswith("No prior relationship records")]
        ctx["not_held"] = ("This organization is public-only: no relationship records (proposals, meetings, "
                           "correspondence, CRM) are held for it, so do not search for them.")
    ctx["company_coverage_gaps"] = coverage_gaps(bundle)
    ctx["rules"] += (" Use searches for missing company coverage (company_coverage_gaps) or recent news, never for "
                     "records listed in not_held.")
    return ctx


def profile_passages(ranked: list[dict], org: str, chroma_dir) -> list[dict]:
    """The company-profile search result under I7: the best passage of each of PROFILE_DOCUMENTS documents (instead
    of the top passages, which can all come from one page), plus the NEWEST_DOCUMENTS newest dated documents of the
    organization. Selection step 7 then adds every verbatim excerpt of each of these documents."""
    from deal_prep.kb_index import passages_where
    out, docs = [], []
    for e in ranked:
        if e["document_id"] not in docs and len(docs) < PROFILE_DOCUMENTS:
            docs.append(e["document_id"])
            out.append(e)
    first: dict[str, dict] = {}
    for p in passages_where({"$and": [{"subject_org_id": org}, {"info_origin": "public_source"}]}, chroma_dir):
        day = str(p["metadata"].get("publication_date") or "")
        if re.fullmatch(r"\d{4}-\d{2}-\d{2}", day):
            first.setdefault(p["document_id"], p)
    newest = sorted(first, key=lambda d: first[d]["metadata"]["publication_date"], reverse=True)[:NEWEST_DOCUMENTS]
    for d in newest:
        if d not in docs:
            docs.append(d)
            out.append(first[d])
    return out


def document_excerpts(found: list[dict], known_ids: set, chroma_dir) -> list[dict]:
    """Every verbatim excerpt (at most selection.MAX_PASSAGES_PER_DOCUMENT) of each public document the agent found,
    so a title found by a search arrives with its content."""
    from deal_prep import evidence_profile as ep
    from deal_prep.evidence import normalize
    from deal_prep.kb_index import passages_where
    from deal_prep.selection import MAX_PASSAGES_PER_DOCUMENT
    out = []
    for d in sorted({e["document_id"] for e in found if e.get("info_origin") == "public_source"
                     and e.get("document_id")}):
        for p in passages_where({"document_id": d}, chroma_dir)[:MAX_PASSAGES_PER_DOCUMENT]:
            if p["evidence_id"] not in known_ids and \
                    ep.statement_form(normalize(p, "supplemental")) == "verbatim_excerpt":
                out.append(p)
    return out
