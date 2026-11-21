"""Phase 4.5 I4: conflicts derived from the evidence itself, chronology, undated history and event dates.

Until I4, a formal conflict disclosure existed only for conflicts curated in the knowledge-base manifest
(conflict_group). Disagreements inside the retrieved evidence were at most stated by the drafter. These rules are
company-independent and read only the sanitized evidence of the drafting input:

1. Contradiction (kind "unresolved_conflict"): public sources from different documents make the same statement with
   different figures (evidence_profile.figure_relations). Both statements cannot be true.
2. Chronological ambiguity (kind "chronological_ambiguity"; owner decision at the I4 approval): a state said to
   exist "since" a year EARLIER than the year a decision about the same subject was taken. This is NOT treated as a
   contradiction: the activity may have begun before it was formalised. It is disclosed so that neither date is
   presented as established and both sources are cited. A state from the decision year or later is compatible and
   not disclosed.
3. Undated history: a past-tense historical statement with no date ("began as", "was formed by", ...) is marked
   statement_date "not_stated", so the briefing can say "date not stated".
4. Event dates: dates written in a news item's own text are extracted separately from the provider's publication
   date, which is an estimate and is never the event date.
Every derived conflict cites the exact passages of both sides. ENABLED switches I4 off for the controlled
comparison only (then the I3.1 behaviour is unchanged).
"""
import re

from deal_prep import evidence_profile as ep

ENABLED = True
_MONTHS = "January|February|March|April|May|June|July|August|September|October|November|December"
_DECISION = re.compile(r"\b(?:in|during)\s+((?:19|20)\d{2}),?\s+(?:our|the|its)?\s*(?:board|management|company)?\s*"
                       r"decided\s+to\s+(?P<what>[^.\"]+)|decided\s+in\s+((?:19|20)\d{2})\s+to\s+(?P<what2>[^.\"]+)",
                       re.I)
_STATE = re.compile(r"\bsince\s+((?:19|20)\d{2}),?\s+(?P<what>[^.\"]+)|(?P<what2>[^.\"]+?)\s+since\s+((?:19|20)\d{2})",
                    re.I)
# A past event: a passive past ("was formed", "were sold") or a historical verb ("began as", "merged").
_HISTORY = re.compile(r"\b(?:was|were)\s+(?:\w+ed|bought|sold|founded|built|begun|made)\b|"
                      r"\b(?:began|started|merged|acquired|founded|bought|sold)\b", re.I)
# Month names are matched case-sensitively, so the verb "may" is not a date.
_ANY_DATE = re.compile(rf"\b(?:19|20)\d{{2}}\b|\b(?:{_MONTHS})\b")
_EVENT_DATE = re.compile(rf"\b(?:\d{{1,2}}\s+)?(?:{_MONTHS})(?:\s+\d{{1,2}})?,?\s+(?:19|20)\d{{2}}\b|"
                         rf"\b(?i:in|during|since)\s+(?:19|20)\d{{2}}\b")
_STOP = set("""about after again all also and are been before being board but by company decided every for from has
have into its itself our since that the their them they this those through was were which while with""".split())


def _stem(word: str) -> str:
    w = word.casefold()
    return w[:-1] if len(w) > 4 and w.endswith("s") else w


def _subject(text: str) -> set[str]:
    return {_stem(w) for w in re.findall(r"[A-Za-z][A-Za-z-]+", text or "")
            if len(w) >= 5 and w.casefold() not in _STOP}


def _public(entries):
    return [e for e in entries if e.get("info_origin") == "public_source" and ep.statement_form(e) == "verbatim_excerpt"]


def _sentences(e):
    return ep.statements(e["excerpt"]) or re.findall(r"\"([^\"]{8,})\"", e.get("excerpt") or "")


def _publisher(e) -> str:
    parts = (e.get("provenance_label") or "").split(" · ")
    return parts[1].strip() if len(parts) > 1 else "unknown publisher"


def _side(e, statement):
    return {"evidence_id": e["evidence_id"], "document_id": e.get("document_id"), "publisher": _publisher(e),
            "statement": statement.strip()}


def decision_state_pairs(entries: list[dict]) -> list[dict]:
    """(decision, state) pairs about the same subject, each with years; relation 'ambiguous' when the state begins
    before the decision, else 'compatible'."""
    decisions, states = [], []
    for e in _public(entries):
        for s in _sentences(e) + [e["excerpt"]]:
            for m in _DECISION.finditer(s):
                year, what = (m.group(1), m.group("what")) if m.group(1) else (m.group(3), m.group("what2"))
                decisions.append((e, s, int(year), _subject(what)))
            for m in _STATE.finditer(s):
                year, what = (m.group(1), m.group("what")) if m.group(1) else (m.group(4), m.group("what2"))
                states.append((e, s, int(year), _subject(what)))
    out, seen = [], set()
    for de, ds, dy, dsub in decisions:
        for se, ss, sy, ssub in states:
            if de["evidence_id"] == se["evidence_id"] or len(dsub & ssub) < 2:
                continue
            key = (de["evidence_id"], se["evidence_id"])
            if key in seen:
                continue
            seen.add(key)
            out.append({"decision": _side(de, _quoted(ds)), "state": _side(se, _quoted(ss)), "decision_year": dy,
                        "state_year": sy, "relation": "ambiguous" if sy < dy else "compatible"})
    return out


def _quoted(s: str) -> str:
    m = re.search(r"\"([^\"]{8,})\"", s)
    return m.group(1) if m else s


def derived_conflicts(entries: list[dict], company_domain: str | None = None) -> list[dict]:
    """Formal conflicts derived from the drafting input: contested figures and chronological ambiguities."""
    if not ENABLED:
        return []
    out = []
    rel = ep.figure_relations(entries, company_domain)
    by_id = {e["evidence_id"]: e for e in entries}
    done = set()
    for eid, r in sorted(rel.items()):
        for other in r["contested_with"]:
            pair = frozenset({eid, other})
            docs = frozenset({ep.document_key(by_id[eid]), ep.document_key(by_id[other])})
            if docs in done:
                continue
            done.add(docs)
            a, b = sorted(pair, key=lambda i: (ep.source_class(by_id[i], company_domain)
                                               != "official_company_source", i))
            sa = next((s for s in ep.statements(by_id[a]["excerpt"])), by_id[a]["excerpt"])
            sb = next((s for s in ep.statements(by_id[b]["excerpt"])
                       if ep._frame(s) == ep._frame(sa)), by_id[b]["excerpt"])
            out.append({"id": f"derived:figures:{len(out) + 1}", "kind": "unresolved_conflict",
                        "sides": [_side(by_id[a], sa), _side(by_id[b], sb)]})
    for p in decision_state_pairs(entries):
        if p["relation"] == "ambiguous":
            out.append({"id": f"derived:chronology:{len(out) + 1}", "kind": "chronological_ambiguity",
                        "sides": [p["decision"], p["state"]], "decision_year": p["decision_year"],
                        "state_year": p["state_year"]})
    return out


def disclosure(c: dict) -> dict:
    sides = "; ".join(f'{s["document_id"] or s["evidence_id"]} ({s["publisher"]}) states: '  # a web result: its ID
                      f'"{s["statement"].rstrip(".")}."' for s in c["sides"])
    if c["kind"] == "chronological_ambiguity":
        text = (f"Chronological ambiguity: {sides} The state is dated {c['state_year']}, earlier than the "
                f"{c['decision_year']} decision about the same subject. Both can be true (the practice may have begun "
                f"before it was formalised), but the sources do not establish how they relate, so neither date is "
                f"treated as established.")
    else:
        text = (f"Unresolved conflict: {sides} These sources give different figures for the same statement, so "
                f"neither figure is treated as established.")
    return {"id": f"conflict:{c['id']}", "kind": c["kind"], "evidence_ids": [s["evidence_id"] for s in c["sides"]],
            "text": text}


def undated_history(e: dict) -> bool:
    """A public historical statement that gives no date."""
    if not ENABLED or e.get("info_origin") != "public_source" or (e.get("source") == "external_news"):
        return False
    text = " ".join(_sentences(e)) or e.get("excerpt") or ""
    quoted = re.findall(r"\"([^\"]{8,})\"", e.get("excerpt") or "") or [text]
    return any(_HISTORY.search(q) and not _ANY_DATE.search(q) for q in quoted)


def event_dates(e: dict) -> list[str]:
    """Dates the news item's own text gives for what happened (not the provider's publication date)."""
    if not ENABLED or e.get("source") != "external_news":
        return []
    text = f"{e.get('dateline') or ''} {e.get('excerpt') or ''}"  # I7: the release's dateline is its own text
    return sorted({m.group(0).strip() for m in _EVENT_DATE.finditer(text)})
