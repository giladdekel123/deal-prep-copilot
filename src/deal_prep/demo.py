"""Offline demo components: no paid calls, no credentials, nothing presented as real that is not.

- OfflineNewsClient: live news is disabled. It sends nothing and spends no credits; the pipeline
  reports the news as "not searched" (status "disabled", not a failure), so the briefing is still
  labelled partial with no current market intelligence. Simulated articles are deliberately NOT
  generated: they would carry public-source labels for content that is not real.
- TemplateDrafter: stands in for the drafting model. It assembles a rule-abiding draft from the
  evidence it is shown (short excerpts, cited by ID) and acknowledges every required disclosure.
  The output is labelled as template-assembled; no AI model is used.

How the template composes a briefing (general rules, for any company):
- It works from each passage's document type, section and chunk type, read from the local corpus
  (or supplied with the evidence). Nothing depends on a particular company, document ID or wording.
- Text is copied from the cited passages and only reformatted (headings, markers and table syntax
  removed). It is never paraphrased, and a number is shown only if the cited passage contains it.
- Each document appears once; a passage that only repeats figures already shown is not repeated.
- Where the retrieved passages cannot support a meaningful item, the item says so.
"""
import functools
import json
import re

from deal_prep import evidence_profile
from deal_prep.web_research import NewsDisabled, SearchConfig

GENERATION_LABEL = "Draft assembled by a template from the evidence (offline demo; no AI model used)."
NEWS_DISABLED = "live news is disabled in offline demo mode"
LIVE_AI_NEWS_OFF = "live news is not enabled in Live AI drafting mode"


class OfflineNewsClient:
    """Same interface as TavilyClient.search, but never sends a request or reserves credits.
    `reason` says why news is off in the current mode; it appears in the trace and the gap text."""

    def __init__(self, config: SearchConfig | None = None, reason: str = NEWS_DISABLED):
        self.config = config or SearchConfig()
        self.reason = reason

    def search(self, payload, budget, today, trace):
        trace.append({"service": "none", "query": payload["query"], "window": "n/a",
                      "outcome": f"skipped: {self.reason}", "results": 0, "attempt": 0, "credits": 0,
                      "elapsed_ms": 0})
        raise NewsDisabled(None, message=self.reason)


# Fallback list of section headings, used only when a passage's own section is unknown.
_HEADINGS = ("Claims", "Excerpts", "Limitations", "Proposed pricing", "Commercial terms", "Scope", "Discussion",
             "Decisions and commitments", "Meeting", "Status", "List prices", "Notes", "Product family",
             "Identity and provisioning", "Deployment", "Competitor summary", "Where we win", "Where we lose",
             "Price objection")
_HEADER_ONLY = re.compile(r"^(?:Subject|From|To|Date):")
_TABLE_ROW = re.compile(r"[^|:]+:[^|]+(?: \| [^|:]+:[^|]+)+")
MAX_WORDS = 40  # longer passages are cut at a sentence boundary and marked with "…" (R6)
PREFIXES = {"relationship": "Synthetic demonstration record: ",
            "meeting_history": "Past meeting (synthetic user-entered demonstration record, not a verified fact): "}
ITEM_MAX_CHARS = 600  # briefing.Item.text max_length (checked by a test)
CUSTOMER_PREFIX = "From this customer's synthetic records: "
GENERAL_PREFIX = "General price list (not specific to {company}): "
_SENTENCE_BREAK = re.compile(r"(?<=[.!?])\s+(?=[A-Z\"(])")
_MARKERS = re.compile(r"\[(?:E|C)\d+\]|\((?:E|C)\d+\)")
_NUMBER = re.compile(r"\d[\d,]*\d|\d")
_MONTHS = "January|February|March|April|May|June|July|August|September|October|November|December"
_DATE = re.compile(rf"\b(?:\d{{1,2}} (?:{_MONTHS}) \d{{4}}|(?:{_MONTHS}) \d{{4}}|\d{{4}}-\d{{2}}-\d{{2}})\b")
# General email conventions (not tied to any company): courtesy sentences and lead-in phrases carry no content.
_COURTESY = re.compile(r"^(?:Thank you|Thanks|Dear |Hi |Hello|Best regards|Kind regards|Regards|Sincerely)")
_LEAD_IN = re.compile(r"^(?:As discussed|As agreed|As promised|Further to our (?:call|meeting|conversation)),\s*")
_DOC_PRIORITY = {"proposal": 0, "meeting_notes": 1, "correspondence": 2}  # terms first, then meetings, then emails


# --- passage structure ---------------------------------------------------------------------------

@functools.cache
def _kb_structure() -> dict:
    """evidence ID -> document type, section heading and chunk type, from the local corpus (read once)."""
    from deal_prep.kb_index import load_kb_chunks
    out = {}
    for c in load_kb_chunks():
        m = c["metadata"]
        out[c.get("chunk_id") or m["chunk_id"]] = {"doc_type": m.get("doc_type"), "section": m.get("section") or "",
                                                    "chunk_type": m.get("chunk_type")}
    return out


def _meta(e: dict) -> dict:
    """Structure of one evidence passage: supplied with the evidence, else looked up in the corpus."""
    if e.get("doc_type"):
        return {"doc_type": e["doc_type"], "section": e.get("section") or "", "chunk_type": e.get("chunk_type")}
    if e["evidence_id"].startswith("HIST-"):
        return {"doc_type": "meeting_record", "section": "", "chunk_type": "paragraph"}
    try:
        return _kb_structure().get(e["evidence_id"], {})
    except Exception:  # noqa: BLE001 - the template still works from the text alone
        return {}


def _usable(excerpt: str, section: str = "") -> bool:
    """Passages that may be shown as an item. A public snapshot's "Limitations" section describes the source,
    not the company (R1); profile metadata and email header lines carry no content (R2)."""
    text = " ".join((excerpt or "").split())
    return (bool(text) and section != "Limitations" and not text.startswith(("Limitations", "PUBLIC SOURCE"))
            and not _HEADER_ONLY.match(text))


def _strip_heading(text: str, section: str = "") -> str:
    """Remove the passage's own section heading. Without a known section, fall back to the heading list, but
    only where the word is a heading ("Discussion The buyer asked…"), not a sentence ("Meeting record (…)") (R5)."""
    if section and text.startswith(section + " "):
        return text[len(section):].lstrip(" ->")
    for heading in sorted(_HEADINGS, key=len, reverse=True):
        rest = text[len(heading):]
        if text.startswith(heading + " ") and re.match(r" (?:[A-Z\-\[>(]|\*\*)", rest):
            return rest.lstrip(" ->")
    return text


def _row_pairs(text: str) -> dict:
    return {k.strip(): v.strip() for k, v in (p.split(":", 1) for p in text.split(" | "))}


def _row_sentence(pairs: dict) -> str:
    """One table row as a sentence; every value is kept and nothing is added (R3)."""
    pairs = dict(pairs)
    if "Product" in pairs:
        head = pairs.pop("Product") + (f" ({pairs.pop('Tier')} tier)" if "Tier" in pairs else "")
    else:
        key, value = next(iter(pairs.items()))
        head = f"{key} {pairs.pop(key)}"
    unit, qty = pairs.pop("Unit", ""), pairs.pop("Quantity", None)
    if "List price (USD)" in pairs:
        text = f"{head}: list price USD {pairs.pop('List price (USD)')} {unit}".rstrip()
        if "Minimum term" in pairs:
            text += f"; minimum term {pairs.pop('Minimum term')}"
    elif "Proposed price (USD)" in pairs:
        counted = {"per user": "users", "per TB": "TB"}
        noun = next((n for u, n in counted.items() if unit.startswith(u)), None)
        lead = f"{qty} {noun} " if qty and noun else ""
        text = f"{head}: {lead}proposed at USD {pairs.pop('Proposed price (USD)')} {unit}".rstrip()
        if qty and not noun:
            text += f", quantity {qty}"
        if "Valid until" in pairs:
            text += f", valid until {pairs.pop('Valid until')}"
    else:
        text = f"{head}: {unit}" if unit else head
        if qty:
            text += f"; quantity {qty}"
    if pairs:  # any other column is still shown, never dropped
        text += "; " + "; ".join(f"{k.lower()} {v}" for k, v in pairs.items())
    return text + "."


def _fields(text: str, keys=("Subject", "From", "To", "Date")) -> dict:
    alternation = "|".join(keys)
    return {k: v.strip().rstrip(".") for k, v in
            re.findall(rf"({alternation}):\s*(.+?)(?=\s+(?:{alternation}):|$)", " ".join(text.split()))}


def _header_sentence(text: str) -> str | None:
    """An email header line ("From: … To: … Date: …") as a sentence (only for an item that already cites it)."""
    if not _HEADER_ONLY.match(text):
        return None
    fields = _fields(text)
    if "Subject" in fields and len(fields) == 1:
        return f"Email subject: {fields['Subject']}."
    parts = ["Email"] + [f"from {fields['From']}"] * ("From" in fields) + [f"to {fields['To']}"] * ("To" in fields)
    text = " ".join(parts) + (f", dated {fields['Date']}" if "Date" in fields else "")
    return text + (f" (subject: {fields['Subject']})" if "Subject" in fields else "") + "."


def _shorten(text: str, words: int, source_cut: bool) -> str:
    """Whole sentences up to the word limit; "…" only where text was actually left out (R6)."""
    sentences = _SENTENCE_BREAK.split(text)
    if source_cut and len(sentences) > 1 and not sentences[-1].endswith((".", "!", "?")):
        sentences = sentences[:-1]  # the stored excerpt ended mid-sentence: drop the fragment
    kept = []
    for s in sentences:
        if len(" ".join(kept + [s]).split()) > words:
            break
        kept.append(s)
    if not kept:  # a single very long sentence: cut at the last clause boundary within the limit
        cut = " ".join(text.split()[:words])
        cut = cut[:max(cut.rfind(","), cut.rfind(";"))] if max(cut.rfind(","), cut.rfind(";")) > len(cut) // 2 else cut
        return cut.rstrip(" ,;") + " …"
    out = " ".join(kept)
    if len(kept) < len(_SENTENCE_BREAK.split(text)) or (source_cut and not out.endswith((".", "!", "?"))):
        return out + " …"
    return out if out.endswith((".", "!", "?")) else out + "."


def readable(excerpt: str, words: int = MAX_WORDS, capitalize: bool = True, section: str = "") -> str:
    """A cited passage as plain sentences: no section heading, claim or excerpt markers, markdown or table
    syntax. Wording is copied, never paraphrased."""
    text = " ".join((excerpt or "").split())
    source_cut = text.endswith("…")
    text = _strip_heading(text.rstrip(" …"), section)
    if _TABLE_ROW.fullmatch(text):
        return _row_sentence(_row_pairs(text))
    header = _header_sentence(text)
    if header:
        return header
    claims = re.findall(r"\[C\d+\]\s*(.+?)\s*\(E\d+\)", text)
    quote = re.match(r'\[E\d+\]\s*"(.+?)"?$', text)
    if claims:
        text, source_cut = claims[0], False  # the first complete claim of a claims list
    elif quote:
        text = quote.group(1)
    text = " ".join(_MARKERS.sub(" ", text).replace("**", "").split())
    return _shorten((text[:1].upper() if capitalize else text[:1]) + text[1:], words, source_cut)


def fact_text(excerpt: str, claim_type: str) -> str:
    """The text of a fact item: the readable passage, with the synthetic prefix where one applies."""
    return PREFIXES.get(claim_type, "") + readable(excerpt)


def _numbers(text: str) -> set[str]:
    return set(_NUMBER.findall(text))


def _chunk(e: dict) -> int:
    tail = e["evidence_id"].rsplit("#", 1)[-1]
    return int(tail) if tail.isdigit() else 0


def _names(company: str) -> list[str]:
    """The company's name and registered aliases (empty registry entry: the name alone)."""
    try:
        from deal_prep.provenance import load_registry
        org = next((o for o in load_registry().values() if o["name"].casefold() == company.casefold()), None)
    except Exception:  # noqa: BLE001
        org = None
    return [company, *((org or {}).get("aliases") or [])]


# --- items ---------------------------------------------------------------------------------------

def _publisher(e: dict, company: str) -> str:
    parts = (e.get("provenance_label") or "").split(" · ")
    publisher = parts[1].strip() if len(parts) > 1 and parts[1].strip() else "another source"
    return f"{company}'s own website" if publisher.casefold() == company.casefold() else publisher


def contested_text(e: dict, others: list[dict], company: str) -> str:
    """Sources that give different figures for the same statement (I2): each side quoted and attributed; neither
    is presented as established."""
    sides = [f'{_publisher(x, company)} states "{readable(x["excerpt"], capitalize=False, section=_meta(x).get("section", ""))}"'
             for x in [e, *others]]
    return "Sources differ: " + "; ".join(sides) + ". The figure is unresolved."


def chronology_text(e: dict, others: list[dict], company: str) -> str:
    """I4: a decision and a state whose dates do not fit together, both quoted; neither date established."""
    sides = [f'{_publisher(x, company)} states "{readable(x["excerpt"], capitalize=False, section=_meta(x).get("section", ""))}"'
             for x in [e, *others]]
    return ("The timeline is unclear: " + "; ".join(sides)
            + ". How the two dates relate is not stated, so neither is treated as established.")


_SOURCE_RANK = {"official_company_source": 0, "primary_third_party": 1, "primary_source": 1, "news": 1,
                "company_announcement": 1, "secondary_profile": 2}
_FORM_RANK = {"verbatim_excerpt": 0, "passage": 1, "claims_summary": 2, "document_header": 3}


def overview_selection(evidence: list[dict], profile: dict, n: int = 5) -> list[tuple[dict, list[dict]]]:
    """Company-overview passages (I2): official and verbatim first; a claims summary is skipped when a verbatim
    excerpt of the same document is available; a secondary source that only restates an official figure is
    skipped; contested figures are returned together. Returns [(passage, [contested counterparts])]."""
    verbatim_docs = {e.get("document_id") for e in evidence if profile[e["evidence_id"]]["statement_form"] == "verbatim_excerpt"}
    order = sorted(range(len(evidence)), key=lambda i: (
        _SOURCE_RANK.get(profile[evidence[i]["evidence_id"]]["source_class"], 3),
        _FORM_RANK.get(profile[evidence[i]["evidence_id"]]["statement_form"], 1), i))
    by_id = {e["evidence_id"]: e for e in evidence}
    out, used = [], set()
    for i in order:
        e = evidence[i]
        p = profile[e["evidence_id"]]
        if e["evidence_id"] in used or p.get("restates"):
            continue
        if p["statement_form"] == "claims_summary" and e.get("document_id") in verbatim_docs:
            continue
        others = [by_id[o] for o in p.get("contested_with", []) + p.get("ambiguous_with", [])  # I4
                  if o in by_id and o not in used]
        used |= {e["evidence_id"], *(o["evidence_id"] for o in others)}
        out.append((e, others))
    return out[:n]


def overview_text(e: dict, company: str) -> str:
    """A public fact about the company. A passage that does not name the company is quoted verbatim and
    attributed to the publisher in its source label, so the reader knows whose statement it is (F1)."""
    section = _meta(e).get("section", "")
    text = readable(e["excerpt"], section=section)
    if any(n.casefold() in text.casefold() for n in _names(company)):
        return text
    parts = (e.get("provenance_label") or "").split(" · ")
    publisher = parts[1].strip() if len(parts) > 1 and parts[1].strip() else "The cited source"
    owner = f"{company}'s own website" if publisher.casefold() == company.casefold() else publisher
    return f'{owner} states: "{readable(e["excerpt"], capitalize=False, section=section)}"'


def meeting_summary(excerpt: str) -> str:
    """An approved meeting record (the system's own record format) as one concise item: date, summary,
    concerns, decisions, commitments and follow-up tasks; participants are left out. A field cut off in the
    stored excerpt is dropped and the item says so; a due date is shown only if the record contains one (F3)."""
    text = " ".join((excerpt or "").split())
    cut = text.endswith("…")
    if cut:
        text = text.rstrip(" …")
        last = max(text.rfind(" Follow-up task ("), text.rfind(" Decisions: "), text.rfind(" Concerns raised: "),
                   text.rfind(" Commitments: "), text.rfind(" Participants: "))
        text = text[:last] if last > 0 else text
    head = re.match(r"Meeting record \(([^)]*)\):\s*", text)
    if not head:
        return readable(excerpt)
    pieces = re.split(r"\s(?=(?:Participants|Concerns raised|Decisions|Commitments): |Follow-up task \()",
                      text[head.end():])
    out = [f"Meeting on {head.group(1)}: {_shorten(pieces[0], MAX_WORDS, False).rstrip(' …')}"]
    shown = pieces[0].casefold()
    for piece in pieces[1:]:
        task = re.match(r"Follow-up task \(([^,]+), due (.+?)\):\s*(.+)$", piece)
        if task:
            status, due, what = task.groups()
            what = re.sub(r"^(?:Action|Task):\s*", "", what).rstrip(". ")
            due_text = f"due {due}" if re.fullmatch(r"\d{4}-\d{2}-\d{2}", due) else (
                "due date not confirmed" if due.startswith("not confirmed") else None)
            out.append(f"Follow-up task: {what} ({status}{', ' + due_text if due_text else ''}).")
            continue
        label, _, value = piece.partition(": ")
        value = re.sub(r"^(?:Decision|Concern|Commitment):\s*", "", value).strip()
        if label == "Participants" or not value or value.casefold().rstrip(".") in shown:
            continue
        name = "Concerns" if label == "Concerns raised" else label
        out.append(f"{name}: {value if value.endswith('.') else value + '.'}")
        shown += " " + value.casefold()
    if cut:
        out.append("Later details of this record were not in the retrieved excerpt.")
    out[0] = out[0] if out[0].endswith((".", "!", "?")) else out[0] + "."
    # Fit one briefing item (I1: complete records can be longer). Follow-up tasks are kept first; other fields are
    # dropped from the end, and the item says so.
    budget = ITEM_MAX_CHARS - len(PREFIXES["meeting_history"])
    if len(" ".join(out)) > budget:
        note = "Other details of this record are omitted here for length."
        tasks = [p for p in out[1:] if p.startswith("Follow-up task:")]
        rest = [p for p in out[1:] if not p.startswith("Follow-up task:")]
        while rest and len(" ".join([out[0], *rest, *tasks, note])) > budget:
            rest.pop()
        out = [out[0], *rest, *tasks, note]
        while len(" ".join(out)) > budget and len(out) > 2:
            out.pop(-2)  # still too long: drop the last task shown (the note stays)
    return " ".join(out)


def _document_item(doc_type: str, passages: list[dict], shown: set[str], shown_from: str | None):
    """One relationship item for one document, from its retrieved passages (in document order). Returns
    (text, cited passages, proposal-with-status (name, status passages, row) or None)."""
    usable = [e for e in passages if _usable(e["excerpt"], _meta(e).get("section", ""))]

    def text_of(e, **kw):
        return readable(e["excerpt"], section=_meta(e).get("section", ""), **kw)

    rows = [e for e in passages if _meta(e).get("chunk_type") == "table_row"
            or _TABLE_ROW.fullmatch(_strip_heading(" ".join(e["excerpt"].split()), _meta(e).get("section", "")))]
    if doc_type == "proposal" and rows:
        main = rows[0]  # the first row is the proposal's main item
        terms = text_of(main)
        status = [e for e in usable if e not in rows and set(_DATE.findall(text_of(e))) - set(_DATE.findall(terms))]
        name = _row_pairs(_strip_heading(" ".join(main["excerpt"].split()), _meta(main).get("section", "")))
        name = name.get("Product") or next(iter(name.values()))
        return terms, [main], ((name, status, main) if status else None)
    if doc_type == "correspondence":
        header = _fields(" ".join(e["excerpt"] for e in passages if _HEADER_ONLY.match(e["excerpt"])))
        heads = [e for e in passages if _HEADER_ONLY.match(e["excerpt"]) and not e["excerpt"].startswith("Subject:")]
        parties = " to ".join(re.sub(r"\s*\([^)]*\)", "", header[k]) for k in ("From", "To") if k in header)
        lead = "Email" + (f" of {header['Date']}" if "Date" in header else "") + (f" ({parties})" if parties else "")
        sentences = [s for s in _SENTENCE_BREAK.split(" ".join(text_of(e) for e in usable)) if not _COURTESY.match(s)]
        summary = _LEAD_IN.sub("", " ".join(sentences)).strip()
        summary = summary[:1].upper() + summary[1:]
        if not summary:
            return f"{lead}: its content was not among the retrieved records.", heads, None
        if _numbers(summary) and _numbers(summary) <= shown:  # repeats figures already shown: say so instead
            return f"{lead}: restated the {shown_from or 'details'} shown above.", heads + usable, None
        return f"{lead}: {summary}", heads + usable, None
    if doc_type == "meeting_notes":
        def raw(e):
            return _strip_heading(" ".join(e["excerpt"].split()), _meta(e).get("section", ""))
        dated = [e for e in usable if raw(e).startswith("Date:")]  # the notes' date line (with participants)
        date = _fields(raw(dated[0]), ("Date", "Participants")).get("Date") if dated else None
        content = [e for e in usable if e not in dated][:2]
        said = " ".join((f"{_meta(e)['section']}: " if _meta(e).get("section") else "") + text_of(e) for e in content)
        lead = f"Meeting on {date}" if date else "Meeting"
        if not said:
            return f"{lead}: its discussion was not among the retrieved records.", dated[:1], None
        return f"{lead}. {said}", dated[:1] + content, None
    return (text_of(usable[0]), usable[:1], None) if usable else (None, [], None)


class TemplateDrafter:
    """Deterministic stand-in for the drafting model (same input and output contract)."""

    def __init__(self):
        self.calls = 0

    def __call__(self, messages):
        self.calls += 1
        payload = json.loads(messages[1]["content"])
        company = payload["company"]
        unresolved = {d["id"].split(":", 1)[1] for d in payload["required_disclosures"]
                      if d["id"].startswith("conflict:")}
        eligible = [e for e in payload["evidence"]
                    if e["conflict_group"] not in unresolved and e["approval_status"] in (None, "approved")]
        evidence = [e for e in eligible if _usable(e["excerpt"], _meta(e).get("section", ""))]

        def take(source, n):
            return [e for e in evidence if e["source"] == source][:n]

        def item(text, cited, claim_type, kind="fact"):
            return {"kind": kind, "text": text, "claim_type": claim_type if kind == "fact" else None,
                    "evidence_ids": [e["evidence_id"] for e in sorted(cited, key=_chunk)]}

        def distinct(items, n=2):  # an excerpt and the claim restating it read the same: show it once
            seen, out = set(), []
            for it in items:
                if it["text"].casefold() not in seen:
                    seen.add(it["text"].casefold())
                    out.append(it)
            return out[:n]

        sections = {s: [] for s in ("company_overview", "recent_developments", "our_relationship", "opportunities",
                                    "competitive_positioning", "meeting_recommendations")}
        # I2 / CP-2: the profile supplied with the evidence (computed with the company's domain); else computed here.
        prof = ({e["evidence_id"]: e["profile"] for e in payload["evidence"] if "profile" in e}
                or evidence_profile.profile(payload["evidence"]))
        sections["company_overview"] = distinct(
            item((chronology_text(e, others, company) if prof[e["evidence_id"]].get("ambiguous_with")
                  else contested_text(e, others, company)) if others else overview_text(e, company),
                 [e, *others], "real_world_fact")
            for e, others in overview_selection(take("internal:company_profile", 8), prof))
        sections["recent_developments"] = [item(readable(e["excerpt"]), [e], "real_world_fact") for e in evidence
                                           if e["time_window"] in ("last_48h", "last_30_days")][:2]

        # Our relationship (F2): one item per document, proposal terms first; repeated figures are not repeated.
        docs = {}
        for e in eligible:
            if e["source"] == "internal:relationship_history":
                docs.setdefault(e["document_id"] or e["evidence_id"], []).append(e)
        ordered = sorted(docs.values(), key=lambda ps: _DOC_PRIORITY.get(_meta(ps[0]).get("doc_type"), 9))
        shown, shown_from, proposals = set(), None, []
        for passages in ordered[:2]:
            doc_type = _meta(passages[0]).get("doc_type")
            text, cited, proposal = _document_item(doc_type, sorted(passages, key=_chunk), shown, shown_from)
            if text:
                sections["our_relationship"].append(item(PREFIXES["relationship"] + text, cited, "relationship"))
                shown |= _numbers(text)
                shown_from = shown_from or ("proposal terms" if doc_type == "proposal" else None)
            if proposal:
                proposals.append(proposal)
        sections["our_relationship"] += [item(PREFIXES["meeting_history"] + meeting_summary(e["excerpt"]), [e],
                                              "meeting_history") for e in take("internal:meeting_history", 2)]

        # Opportunities (F4): only a proposal in this customer's own records, with its recorded status quoted as written
        # (no judgement such as "open" is added), is customer-specific; price-list
        # rows are labelled as general vendor information, never as interest expressed by the customer.
        for name, status, row in proposals[:1]:
            said = " ".join(readable(e["excerpt"], section=_meta(e).get("section", "")) for e in status)
            sections["opportunities"].append(item(f"{CUSTOMER_PREFIX}Proposal for {name}. {said}",
                                                  [row, *status], "relationship"))
        general = GENERAL_PREFIX.format(company=company)
        sections["opportunities"] += [item(general + readable(e["excerpt"], section=_meta(e).get("section", "")),
                                           [e], "vendor_product")
                                      for e in take("internal:vendor_products_pricing", 5)
                                      if _meta(e).get("chunk_type", "table_row") == "table_row"
                                      and _TABLE_ROW.fullmatch(_strip_heading(" ".join(e["excerpt"].split()),
                                                                              _meta(e).get("section", "")))]
        sections["opportunities"] = sections["opportunities"][:2]

        competition = [e for e in take("internal:competition", 5)
                       if _meta(e).get("doc_type") == "battlecard" or (e["document_id"] or "").startswith("NVQ-CMP")][:1]
        if competition:
            sections["competitive_positioning"] = [{
                "kind": "recommendation", "evidence_ids": [competition[0]["evidence_id"]],
                "text": "Use the competitor battlecard: "
                        + readable(competition[0]["excerpt"], section=_meta(competition[0]).get("section", ""))}]
        recs = [f"Confirm {company}'s current document-control priorities before proposing a configuration."]
        if proposals:
            recs.append("Review the synthetic proposal, its recorded status and validity date before the meeting.")
        elif sections["our_relationship"]:
            recs.append(f"Review the synthetic relationship records above before meeting {company}.")
        else:
            recs.append(f"Treat {company} as a new contact; no prior relationship records exist.")
        if not sections["recent_developments"]:  # the missing news is already disclosed once (F5): action only
            recs.append(f"Check {company}'s latest news before the meeting.")
        sections["meeting_recommendations"] = [{"kind": "recommendation", "text": r, "evidence_ids": []} for r in recs]

        disclosures = [{"id": d["id"], "text": d["text"]} for d in payload["required_disclosures"]]
        disclosures += [{"id": f"empty_section:{s}", "text": "No supported content for this section."}
                        for s, items in sections.items() if not items]
        return json.dumps({"sections": sections, "disclosures": disclosures})
