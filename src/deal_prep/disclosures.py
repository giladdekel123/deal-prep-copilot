"""Required gap and conflict disclosures (Prompt 04 step 5; spec FR-07, FR-10, §8).

Code, not the model, decides what must be disclosed:
- every research gap recorded by the orchestrator (no internal records, no relationship records,
  news not found or incomplete);
- an incomplete research status (the briefing must say it is partial);
- every UNRESOLVED conflict among the retrieved evidence, decided by the authority rules: approved
  synthetic statements that disagree (policy_statement) or public sources that disagree
  (real_world_fact). Conflicts the rules resolve (e.g. a superseded price list) are not listed
  here; citing the superseded or draft side as a fact is rejected by citations.py instead.
  C4.3 (owner-approved 2026-11-17): a conflict is disclosed only when it is relevant to this briefing: a retrieved
  passage states one side's conflict_statement, or the conflict's subject appears in the organization's approved
  records (a term both statements share, or two distinctive terms of one statement; product, tier and generic words
  do not count). Passages of both documents on other subjects no longer trigger it. A conflict without recorded
  statements cannot be judged and stays disclosed. Safety rule (mentioned_conflicts): if the final briefing mentions
  the subject of a conflict that was set aside, the disclosure is added after all, with both sides.
  Each side is quoted only from the exact passage it cites. The manifest's conflict_type says
  whether the sources truly contradict each other or only leave a chronological ambiguity (both
  statements can be true but no single date is established); the wording follows that type.
The model must acknowledge each disclosure by ID; the final briefing carries this canonical text.
"""
from datetime import date

from deal_prep import authority, chronology
from deal_prep.evidence import kb_evidence
from deal_prep.kb_index import load_manifest

STATUS_TEXT = {
    "external_with_internal_gap": "Incomplete research: no company-specific internal records were found; "
                                  "the briefing relies on external news and vendor-wide documents only.",
    "partial_internal_only": "Incomplete research: the external news search failed, so this briefing does not "
                             "include current market intelligence.",
}
NEWS_OFF_TEXT = ("Incomplete research: news was not searched (live news is off), so this briefing does not include "
                 "current market intelligence.")


def _groups(bundle: dict) -> dict[str, list[dict]]:
    groups = {}
    for e in kb_evidence(bundle):
        g = e["metadata"].get("conflict_group")
        if g:
            groups.setdefault(g, []).append(e)
    return groups


def unresolved_conflicts(bundle: dict, as_of: date) -> dict[str, list[str]]:
    """conflict_group -> sorted document IDs, for groups the authority rules leave unresolved and that are relevant
    to this briefing (C4.3)."""
    return _classify(bundle, as_of)[0]


def set_aside_conflicts(bundle: dict, as_of: date) -> dict[str, list[str]]:
    """C4.3: unresolved groups whose documents were retrieved only through passages on other subjects."""
    return _classify(bundle, as_of)[1]


_SUBJECT_GENERIC = frozenset({"tier", "product", "edition", "plan", "version", "only"})


def _exclude(bundle: dict) -> frozenset:
    """Words that never make a conflict's subject: the organization's name, product and tier names (price rows)."""
    import re
    from deal_prep.selection import row_product
    rows = [row_product(e.get("text")) for e in kb_evidence(bundle)]
    text = " ".join([(bundle.get("identity") or {}).get("name") or ""] + [f"{r[0]} {r[1]}" for r in rows if r])
    return _SUBJECT_GENERIC | frozenset(w.casefold() for w in re.findall(r"\w+", text))


def about(text: str, statements: list[str], exclude: frozenset) -> bool:
    """Whether a text is about the subject of a conflict: it names a content term both statements share, or two
    distinctive content terms of one statement."""
    from deal_prep.selection import _terms
    terms = [_terms(s, exclude) for s in statements]
    shared = set.intersection(*terms) if terms else set()
    found = _terms(text, exclude)
    return bool(shared & found) or any(len((t - shared) & found) >= 2 for t in terms)


def _record_sentences(bundle: dict) -> list[str]:
    """Sentences of the organization's approved, current records (draft notes never count)."""
    from deal_prep import company_context
    from deal_prep.selection import _SENTENCE
    return [s for e in company_context.approved_records(bundle)
            for s in _SENTENCE.split(" ".join((e.get("text") or e.get("excerpt") or "").split())) if s]


def _classify(bundle: dict, as_of: date) -> tuple[dict, dict]:
    """(relevant, set aside): the unresolved groups, split by C4.3's relevance rule."""
    found = _unresolved(bundle, as_of)
    if not found:
        return {}, {}
    manifest = {d["document_id"]: d for d in load_manifest()}
    groups, relevant, aside = _groups(bundle), {}, {}
    sentences, exclude = None, None
    for g, docs in found.items():
        statements = [manifest.get(d, {}).get("conflict_statement") for d in docs]
        if not all(statements) or any(passage_with(groups[g], d, s) for d, s in zip(docs, statements)):
            relevant[g] = docs  # no recorded statements (cannot be judged), or a retrieved passage states a side
            continue
        if sentences is None:
            sentences, exclude = _record_sentences(bundle), _exclude(bundle)
        (relevant if any(about(s, statements, exclude) for s in sentences) else aside)[g] = docs
    return relevant, aside


def _unresolved(bundle: dict, as_of: date) -> dict[str, list[str]]:
    """conflict_group -> sorted document IDs, for groups the authority rules leave unresolved (document level)."""
    groups = _groups(bundle)
    out = {}
    for g, evs in groups.items():
        docs = {e["document_id"] for e in evs}
        if len(docs) < 2:
            continue
        origins = {e["info_origin"] for e in evs}
        if origins == {"public_source"}:
            status = authority.real_world_fact(evs)["status"]
        elif origins == {"synthetic_record"}:
            status = authority.policy_statement(evs, as_of)["status"]
        else:
            status = "unresolved"  # mixed origins in one group: never silently pick a side
        if status == "unresolved":
            out[g] = sorted(docs)
    return out


def required_disclosures(bundle: dict, as_of: date | None = None) -> list[dict]:
    as_of = as_of or date.fromisoformat(bundle["created_at"][:10])
    gaps = list(bundle.get("gaps", []))
    news = bundle.get("external") or {}
    news_off = bundle.get("status") == "partial_internal_only" and news.get("status") == "disabled"
    if news_off and news.get("message") in gaps:
        gaps.remove(news["message"])  # explained once, in the partial-research disclosure below
    items = [{"id": f"gap:{i + 1}", "kind": "gap", "text": g} for i, g in enumerate(gaps)]
    if bundle.get("status") in STATUS_TEXT:
        text = STATUS_TEXT[bundle["status"]]
        if news_off:  # a skipped search is not a failed one; say why, once
            reason = (news.get("message") or "").removeprefix("News was not searched: ").rstrip(".")
            text = (f"Incomplete research: news was not searched ({reason}), so this briefing does not include "
                    f"current market intelligence.") if reason else NEWS_OFF_TEXT
        items.append({"id": "status", "kind": "incomplete_research", "text": text})
    groups = _groups(bundle)
    manifest = {d["document_id"]: d for d in load_manifest()}
    for g, docs in sorted(unresolved_conflicts(bundle, as_of).items()):
        items.append(_conflict_disclosure(g, docs, groups, manifest))
    # I4: conflicts derived from the drafting input itself (contested figures; chronological ambiguities). A
    # conflict whose passages already belong to a curated conflict group is disclosed above, not twice.
    curated = {e["evidence_id"] for evs in groups.values() for e in evs}
    for c in derived(bundle):
        if not all(s["evidence_id"] in curated for s in c["sides"]):
            items.append(chronology.disclosure(c))
    from deal_prep import company_context  # I7: what the evidence does not establish (one disclosure)
    return items + company_context.unknowns(bundle, as_of)


def _conflict_disclosure(g: str, docs: list[str], groups: dict, manifest: dict) -> dict:
    sides, evidence_ids = [], []
    for d in docs:
        doc = manifest.get(d, {"document_id": d})
        passage = passage_with(groups[g], d, doc.get("conflict_statement"))
        # Cite the exact passage that contains the quoted statement; never quote without support.
        evidence_ids.append(passage["evidence_id"] if passage
                            else next(e["evidence_id"] for e in groups[g] if e["document_id"] == d))
        sides.append(_describe(doc, quoted=passage is not None))
    text = "; ".join(sides)
    text += " " if text.endswith('."') else ". "  # verbatim quotes may already end with a full stop
    kinds = {manifest.get(d, {}).get("conflict_type", "contradiction") for d in docs}
    if kinds == {"chronological_ambiguity"}:
        kind, text = "chronological_ambiguity", (
            f"Chronological ambiguity: {text}These statements can both be true (they may describe different "
            f"steps), but the sources do not establish a single exact date, so neither date is treated as "
            f"established.")
    else:
        kind, text = "unresolved_conflict", (
            f"Unresolved conflict: {text}These sources contradict each other, so neither is treated as "
            f"established.")
    return {"id": f"conflict:{g}", "kind": kind, "evidence_ids": evidence_ids, "text": text}


def _mentioned_groups(bundle: dict, draft: dict, as_of: date) -> dict[str, list[str]]:
    """Set-aside groups whose subject the briefing mentions (pure)."""
    aside = set_aside_conflicts(bundle, as_of)
    if not aside:
        return {}
    manifest = {d["document_id"]: d for d in load_manifest()}
    exclude = _exclude(bundle)
    texts = [i.get("text") or "" for items in (draft.get("sections") or {}).values() for i in items]
    return {g: docs for g, docs in sorted(aside.items())
            if any(about(t, [manifest[d]["conflict_statement"] for d in docs], exclude) for t in texts)}


def one_sided_claims(bundle: dict, draft: dict, as_of: date | None = None) -> list[tuple[str, int, str]]:
    """D2: (section, item, conflict group) for each FACT that is about the subject of an unresolved conflict that was
    set aside as irrelevant, and that is not stated as a disagreement. It states one disputed side as established,
    whatever it cites (an unrelated passage included). Inferences, recommendations and statements of the
    disagreement itself are not claims."""
    from deal_prep.conflict_guard import CONFLICT_WORDS
    as_of = as_of or date.fromisoformat(bundle["created_at"][:10])
    groups = _mentioned_groups(bundle, draft, as_of)
    if not groups:
        return []
    manifest = {d["document_id"]: d for d in load_manifest()}
    exclude = _exclude(bundle)
    out = []
    for g, docs in groups.items():
        statements = [manifest[d]["conflict_statement"] for d in docs]
        for section, items in (draft.get("sections") or {}).items():
            for i, item in enumerate(items):
                text = item.get("text") or ""
                if item.get("kind") == "fact" and not CONFLICT_WORDS.search(text) and about(text, statements, exclude):
                    out.append((section, i, g))
    return out


def mentioned_conflicts(bundle: dict, draft: dict, as_of: date | None = None) -> list[dict]:
    """C4.3 safety rule: a conflict that was set aside, but whose subject the final briefing mentions, is disclosed
    after all, with both sides (never one side alone). D2: the statement passages kept in reserve at research time
    (bundle['conflict_reserve']) are brought into the bundle's conflict sources first, so both sides are quoted from
    the passages that state them."""
    as_of = as_of or date.fromisoformat(bundle["created_at"][:10])
    mentioned = _mentioned_groups(bundle, draft, as_of)
    if not mentioned:
        return []
    manifest = {d["document_id"]: d for d in load_manifest()}
    docs_needed = {d for docs in mentioned.values() for d in docs}
    have = {e["evidence_id"] for e in kb_evidence(bundle)}
    adopted = [e for e in bundle.get("conflict_reserve") or [] if e["document_id"] in docs_needed
               and e["evidence_id"] not in have]
    if adopted:
        bundle.setdefault("conflict_sources", []).extend(adopted)
    groups = _groups(bundle)
    return [_conflict_disclosure(g, docs, groups, manifest) for g, docs in mentioned.items()]


def derived(bundle: dict) -> list[dict]:
    from deal_prep.evidence import evidence_index
    return chronology.derived_conflicts(list(evidence_index(bundle).values()),
                                        (bundle.get("identity") or {}).get("domain"))


def _normalized(text: str) -> str:
    return " ".join((text or "").split())


def passage_with(evidence: list[dict], doc_id: str, statement: str | None) -> dict | None:
    """The evidence passage of doc_id whose text contains the whole statement (whitespace-normalized)."""
    if not statement:
        return None
    wanted = _normalized(statement)
    return next((e for e in evidence if e["document_id"] == doc_id and wanted in _normalized(e["text"])), None)


def _describe(doc: dict, quoted: bool) -> str:
    """'<ID> "<title>" (<publisher, dates>) states: "<statement>"' for one side of a conflict."""
    if doc.get("info_origin") == "public_source":
        published = doc.get("publication_date")
        when = f"published {published}" if published and published != "unknown" else "publication date unknown"
        source = f"{doc.get('publisher', 'unknown publisher')}, {when}, retrieved {doc.get('retrieved_at', 'unknown')}"
    else:
        source = f"synthetic record, effective from {doc.get('effective_from') or 'an unknown date'}"
    statement = doc.get("conflict_statement")
    if statement and quoted:
        said = f'states: "{statement}"'
    else:
        said = "(the passage containing its statement was not retrieved, so it is not quoted)"
    return f'{doc["document_id"]} "{doc.get("title", "")}" ({source}) {said}'
