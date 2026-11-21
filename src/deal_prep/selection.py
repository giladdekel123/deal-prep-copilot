"""Phase 4.5 I3: customer correspondence and purpose-aware evidence selection.

Runs in code after the mandatory ranked searches (orchestrator.gather_research) and before the conflict and
comparison sources are added. Ranked top-k retrieval alone used to decide what reached the drafter, and the CP-2
audit traced most omissions to it: correspondence bodies, the proposed product's list price, and product evidence
for demonstrations ranked out, while superseded price rows, unrelated tiers and competitor material ranked in.

Rules (company-independent; read from document metadata and text, never from company names):
1. Customer records: every passage of each approved, current record of this customer (proposal, correspondence,
   meeting notes) is included, not only the passages that ranked. Records are short; caps apply.
2. Products in play: products of the current price list named in this customer's approved records (knowledge-base
   records and approved meeting records). Draft notes never count.
3. Pricing: only rows of a price list in force on the briefing date. With products in play, only their rows (the
   tier the records name, when a product has several); with none (a new lead), the current list's rows as a whole.
   The list's notes (status, effective period, billing basis) come with its rows.
4. Purpose documents: negotiation -> the commercial policy; product_demo -> the product overview and the security
   and integration FAQ, whole; introduction -> the product descriptions of the product overview (what is sold and
   for whom, not configuration detail). Each document is found by one ranked search within its document type, so
   its passages do not compete with each other for a top-k slot.
   Validation correction (owner-approved 2026-11-14): the commercial policy also comes with ANY purpose when this
   customer has a current proposal (an offer, a revised quote or a concession can come up in any meeting about it);
   a general meeting with a new lead (no customer records) gets the product descriptions an introduction gets.
   C4.1 (owner-approved 2026-11-17): the commercial policy also comes with any purpose when this customer's approved
   records (knowledge-base records and approved meeting records; never a draft note) ask for commercial terms: a
   sentence in request form (a question, "requested", "asked for", "would like", "possible" ...) about a discount,
   price reduction, better price, concession, rebate, special pricing or payment terms. The triggering passage is
   recorded as the reason.
4b. C4.2 (owner-approved 2026-11-17): vendor capability statements chosen by the customer's own questions. For each
   capability question or requirement in this customer's approved records and approved meeting records (a question,
   "need", "require", "asked for", "would like", an open question; at most MAX_CAPABILITY_QUESTIONS), one ranked
   search within the vendor's product-overview and policy documents in force; the best passage of each document is
   kept when it is within CAPABILITY_MAX_DISTANCE and shares a content term with the question (product, tier and
   generic words do not count). Deterministic: the research agent's own lookups are unchanged. The conflict-source
   step (orchestrator.add_conflict_sources) then adds the other side of any conflict a kept passage states.
5. Product-overview passages about a product in play (the first product they name) are included for any purpose.
6. Competitor material is kept only when the competitor (name or registered alias) is named in this customer's or
   company's evidence (records, public profile, news); otherwise no passage naming a competitor reaches the drafter.
   A battlecard passage naming no competitor is kept, as vendor evidence, only when it covers a product in play
   (select_competition, after news; owner decision at the I3 review).
7. Public sources already retrieved for the company contribute every verbatim excerpt (the official source's own
   statements), not only the excerpts that ranked; headers, claims summaries and limitations are not added.
The same exclusion rules screen the research agent's internal lookups (screen()).
Every passage records why it was selected, and every passage left out records why (bundle["selection"]; report()),
so a missing item can be traced to selection or to drafting. Nothing here changes provenance labels, approval
status, conflict handling or citation rules.
"""
import re
import time
from datetime import date

from deal_prep.kb_index import passages_where, search

MAX_CUSTOMER_DOCUMENTS = 8
MAX_PASSAGES_PER_DOCUMENT = 12
MAX_PRICE_ROWS = 12
# (document type, what the meeting needs from it, which passages): "all" = the whole document; "products" = only
# passages describing a priced product (an introduction needs what is sold and for whom, not configuration detail).
PURPOSE_DOCUMENTS = {
    "negotiation": [("policy", "discount approval thresholds, proposal validity and billing terms", "all")],
    "product_demo": [("product_overview", "product capabilities, retention and legal hold, sign-on and deployment",
                      "all"),
                     ("policy", "where customer data is stored, encryption, single sign-on and integrations", "all")],
    "introduction": [("product_overview", "product family and the organizations each product serves", "products")],
}
# Validation correction (owner-approved 2026-11-14): documents chosen by the customer's context, not the meeting label.
COMMERCIAL_CONTEXT = ("policy", "discount approval thresholds, proposal validity and billing terms", "all")
NEW_LEAD_GENERAL = ("product_overview", "product family and the organizations each product serves", "products")
# C4.1: a request for commercial terms in the customer's approved records ("discounted cash flow" is not "discount").
_COMMERCIAL_TERMS = re.compile(
    r"\b(?:discounts?|price reductions?|(?:reduced|lower|better)(?: [\w-]+)? (?:prices?|rates?|pricing|terms)|"
    r"concessions?|rebates?|special (?:pricing|prices?|terms|rates?)|payment terms|(?:extended|deferred) payment)\b",
    re.I)
_REQUEST_FORM = re.compile(r"\?|\b(?:request(?:s|ed|ing)?|ask(?:s|ed|ing)? (?:for|whether|if|about)|would like|"
                           r"possible|could you|can you|seek(?:s|ing)?|want(?:s|ed)? (?:a|an|to)|please (?:offer|"
                           r"consider|confirm))\b", re.I)
_SENTENCE = re.compile(r"(?<=[.!?])\s+")
# C4.2: capability questions in the customer's approved records.
CAPABILITY_DOCUMENTS = ("product_overview", "policy")
MAX_CAPABILITY_QUESTIONS = 4
CAPABILITY_K = 12
CAPABILITY_MAX_DISTANCE = 0.80  # cosine distance; in the development cases relevant passages were 0.52-0.75
_CAPABILITY_REQUEST = re.compile(r"\?|\b(?:needs?|needed|requires?|required|requirements?|must|ask(?:s|ed)? (?:for|"
                                 r"about|whether|if)|would like|wants?|whether|(?:question|issue|point) (?:is |remains "
                                 r")?(?:still )?open|open (?:question|issue|point)s?)\b", re.I)
_GENERIC = frozenset("""
    the and for with from that this these those what which when where who whom whose why how are was were has have had
    does did can could would should will shall may might must not any all also only our ours your their them they its
    you she him her his one two three per via into onto than then there here about after before over under more most
    other such each both able please send sent need needs needed require requires required requirement requirements ask
    asks asked whether like want wants question questions issue issues point points open still remain remains include
    includes included including cover covers covered option options available availability support supports supported
    provide provides offer offers user users document documents customer customers price prices pricing list quote
    quotes quotation revised proposal proposals discount discounts cost costs term terms month months year years
    meeting meetings follow-up thank thanks regards dear team possible better lower reduced reduction special
    rebate rebates concession concessions payment commitment exchange""".split())


def _terms(text: str, exclude: frozenset = frozenset()) -> set[str]:
    """Content terms (lower-case, crude stem): no generic, product or tier words; a hyphenated word also gives its
    parts."""
    out = set()
    for w in re.findall(r"[^\W\d_]\w*(?:-\w+)*", text or ""):
        for t in ({w, *w.split("-")} if "-" in w else {w}):
            t = t.casefold()
            if len(t) < 3 or t in _GENERIC or t in exclude:
                continue
            for suffix in ("ing", "ed", "es", "s"):
                if t.endswith(suffix) and len(t) - len(suffix) >= 3:
                    t = t[:-len(suffix)]
                    break
            if t not in _GENERIC and t not in exclude:
                out.add(t)
    return out


def capability_questions(passages: list[dict], exclude: frozenset = frozenset()) -> list[tuple[str, str, set]]:
    """(evidence ID, sentence, content terms) of the first MAX_CAPABILITY_QUESTIONS capability questions or
    requirements: a sentence in question or requirement form with at least one content term."""
    out = []
    for e in passages:
        for sentence in _SENTENCE.split(" ".join((e.get("text") or "").split())):
            terms = _terms(sentence, exclude)
            if terms and _CAPABILITY_REQUEST.search(sentence):
                out.append((e.get("evidence_id"), sentence, terms))
                if len(out) == MAX_CAPABILITY_QUESTIONS:
                    return out
    return out


def capability_passages(passages: list[dict], today: date, chroma_dir,
                        exclude: frozenset = frozenset()) -> list[tuple[str, dict]]:
    """(the asking passage's evidence ID, vendor passage): for each capability question, the best passage of each
    vendor product-overview or policy document in force, kept within CAPABILITY_MAX_DISTANCE and when it shares a
    content term with the question."""
    out, seen = [], set()
    for asked, sentence, terms in capability_questions(passages, exclude):
        best: dict[str, dict] = {}
        for p in search(sentence, k=CAPABILITY_K, global_only=True, origin="synthetic_record", chroma_dir=chroma_dir):
            meta = p.get("metadata") or {}
            if meta.get("doc_type") in CAPABILITY_DOCUMENTS and in_force(meta, today):
                best.setdefault(p["document_id"], p)
        for p in best.values():
            distance = p.get("distance")
            if distance is not None and distance <= CAPABILITY_MAX_DISTANCE and p["evidence_id"] not in seen \
                    and terms & _terms(p.get("text"), exclude):
                seen.add(p["evidence_id"])
                out.append((asked, p))
    return out


def commercial_request_sentence(passages: list[dict]) -> tuple[str, str] | None:
    """(evidence ID, sentence) of the first sentence that asks for commercial terms in request form, or None."""
    for e in passages:
        for sentence in _SENTENCE.split(" ".join((e.get("text") or "").split())):
            if _COMMERCIAL_TERMS.search(sentence) and _REQUEST_FORM.search(sentence):
                return e.get("evidence_id"), sentence
    return None


def commercial_request(passages: list[dict]) -> str | None:
    """The first passage (evidence ID) that asks for commercial terms in request form, or None."""
    found = commercial_request_sentence(passages)
    return found[0] if found else None


_PERCENT = re.compile(r"(\d+(?:[.,]\d+)?)\s*(?:%|per ?cent\b)", re.I)
_DISCOUNT_WORD = re.compile(r"discount|reduction|rebate|concession|off\b", re.I)


def requested_percent(sentence: str) -> float | None:
    """The discount a request names: the percentage next to a discount word, else the only percentage; None when the
    sentence names none (or several that cannot be told apart)."""
    found = [(m, float(m.group(1).replace(",", "."))) for m in _PERCENT.finditer(sentence)]
    near = [v for m, v in found if _DISCOUNT_WORD.search(sentence[m.end():m.end() + 18])
            or _DISCOUNT_WORD.search(sentence[max(0, m.start() - 14):m.start()])]
    pool = near or [v for _, v in found]
    return pool[0] if len(set(pool)) == 1 else None


def context_documents(purpose: str, records: list[dict], approved_meetings: list[dict]) -> list[tuple[str, tuple]]:
    """(label, document spec) added to the purpose documents: the commercial policy whenever this customer has a
    current proposal or (C4.1) its approved records ask for commercial terms (unless the purpose already brings it),
    and product descriptions for a general meeting with a new lead (no customer records or approved meetings).
    records: the customer's approved, current knowledge-base records; approved_meetings: approved meeting records."""
    out = []
    has_proposal = any((p.get("metadata") or {}).get("doc_type") == "proposal" for p in records)
    if has_proposal and purpose != "negotiation":
        out.append(("commercial_context", COMMERCIAL_CONTEXT))
    elif purpose != "negotiation" and (asked := commercial_request(list(records) + list(approved_meetings))):
        out.append((f"commercial_request:{asked}", COMMERCIAL_CONTEXT))
    if purpose == "general" and not records and not approved_meetings:
        out.append(("general", NEW_LEAD_GENERAL))
    return out
_ROW = re.compile(r"Product:\s*([^|]+?)\s*\|\s*Tier:\s*([^|]+?)\s*\|")


# --- small rules -------------------------------------------------------------------------------------

def current(meta: dict) -> bool:
    """Approved and not replaced by a newer version."""
    return meta.get("approval_status") == "approved" and not meta.get("superseded_by")


def in_force(meta: dict, today: date) -> bool:
    """Current, and its effective period (when stated) includes the briefing date."""
    start, end, day = (meta.get("effective_from") or "")[:10], (meta.get("effective_to") or "")[:10], today.isoformat()
    return current(meta) and (not start or start <= day) and (not end or end >= day)


def row_product(text: str) -> tuple[str, str] | None:
    m = _ROW.search(text or "")
    return (m.group(1), m.group(2)) if m else None


def _mentions(text: str, name: str) -> bool:
    return name.casefold() in (text or "").casefold()


def first_product(text: str, products: list[str]) -> str | None:
    """The product a passage is about: the first of the known products it names."""
    low = (text or "").casefold()
    hits = [(low.find(p.casefold()), p) for p in products if p.casefold() in low]
    return min(hits)[1] if hits else None


def _text(e: dict) -> str:
    return e.get("text") or e.get("excerpt") or ""


class Selection:
    """Selected and excluded passages with one reason each (first reason wins)."""

    def __init__(self, bundle: dict, today: date):
        self.data = bundle.setdefault("selection", {"as_of": today.isoformat(), "purpose": bundle.get("purpose"),
                                                    "products_in_play": [], "competition": None,
                                                    "selected": {}, "excluded": []})

    def take(self, e: dict, reason: str) -> dict:
        self.data["selected"].setdefault(e["evidence_id"], reason)
        return e

    def drop(self, e: dict, reason: str, stage: str) -> None:
        self.data["excluded"].append({"evidence_id": e["evidence_id"], "reason": reason, "stage": stage})


def _merge(*groups: list[dict]) -> list[dict]:
    seen, out = set(), []
    for g in groups:
        for e in g:
            if e["evidence_id"] not in seen:
                seen.add(e["evidence_id"])
                out.append(e)
    return out


# --- the selection step ------------------------------------------------------------------------------

def customer_records(org_id: str | None, chroma_dir) -> list[dict]:
    """Every passage of this customer's approved, current knowledge-base records (newest documents first)."""
    if not org_id:
        return []
    found = [p for p in passages_where({"$and": [{"customer_org_id": org_id}, {"info_origin": "synthetic_record"}]},
                                       chroma_dir) if current(p["metadata"])]
    docs: dict[str, list[dict]] = {}
    for p in found:
        docs.setdefault(p["document_id"], []).append(p)
    newest = sorted(docs, key=lambda d: (docs[d][0]["metadata"].get("issued_at") or "", d), reverse=True)
    return [p for d in newest[:MAX_CUSTOMER_DOCUMENTS] for p in docs[d][:MAX_PASSAGES_PER_DOCUMENT]]


def price_lists_in_force(today: date, chroma_dir) -> list[dict]:
    return [p for p in passages_where({"$and": [{"scope": "global"}, {"doc_type": "price_list"}]}, chroma_dir)
            if in_force(p["metadata"], today)]


def rows_in_play(customer_text: str, price_passages: list[dict]) -> list[dict]:
    """Current price rows of the products named in the customer's records; when a product has several tiers, the
    tier the records name (all tiers when none is named)."""
    by_product: dict[str, list[tuple[str, dict]]] = {}
    for p in price_passages:
        pt = row_product(p["text"])
        if pt and _mentions(customer_text, pt[0]):
            by_product.setdefault(pt[0], []).append((pt[1], p))
    out = []
    for tiers in by_product.values():
        named = [p for tier, p in tiers if re.search(rf"\b{re.escape(tier)}\b", customer_text)]
        out += named or [p for _, p in tiers]
    return out


def purpose_document(doc_type: str, query: str, today: date, chroma_dir) -> list[dict]:
    """The vendor-wide document of this type that best matches what the meeting needs, whole."""
    ranked = [e for e in search(query, k=10, global_only=True, origin="synthetic_record", chroma_dir=chroma_dir)
              if e["metadata"]["doc_type"] == doc_type and in_force(e["metadata"], today)]
    if not ranked:
        return []
    passages = [p for p in passages_where({"document_id": ranked[0]["document_id"]}, chroma_dir)]
    return passages[:MAX_PASSAGES_PER_DOCUMENT]


def select_for_purpose(bundle: dict, chroma_dir, today: date) -> None:
    started = time.monotonic()
    sel = Selection(bundle, today)
    purpose = bundle.get("purpose", "general")
    internal = bundle["internal"]
    org = (bundle.get("identity") or {}).get("org_id")

    # 1. Customer records, whole.
    rel = internal.get("relationship_history")
    records = customer_records(org, chroma_dir)
    if rel is not None:
        ranked_ids = {e["evidence_id"] for e in rel["evidence"]}
        rel["evidence"] = _merge(rel["evidence"],
                                 [sel.take(p, f"customer_record:{p['document_id']}") for p in records
                                  if p["evidence_id"] not in ranked_ids])
    approved_meetings = (internal.get("meeting_history") or {}).get("evidence", [])
    customer_text = "\n".join(_text(e) for e in records + approved_meetings)

    # 2-3. Pricing in force; products in play.
    vendor = internal.get("vendor_products_pricing")
    price_passages = price_lists_in_force(today, chroma_dir)
    in_play_rows = rows_in_play(customer_text, price_passages)
    products = sorted({row_product(p["text"])[0] for p in in_play_rows})
    sel.data["products_in_play"] = products
    all_products = sorted({pt[0] for p in price_passages if (pt := row_product(p["text"]))})
    if vendor is not None:
        if products:
            rows = [sel.take(p, f"price_row_in_play:{row_product(p['text'])[0]}") for p in in_play_rows]
        else:  # nothing in play yet (a new lead): the current list as a whole, not a ranked subset of its rows
            rows = [sel.take(p, "current_price_row:no_product_in_play") for p in price_passages
                    if row_product(p["text"])][:MAX_PRICE_ROWS]
        row_ids = {p["evidence_id"] for p in rows}
        kept = []
        for e in vendor["evidence"]:
            meta = e["metadata"]
            if not in_force(meta, today):
                sel.drop(e, f"not_in_force: {meta.get('approval_status') or 'unknown'}"
                            + (f", superseded by {meta['superseded_by']}" if meta.get("superseded_by") else ""),
                         "vendor_products_pricing")
            elif row_product(e["text"]) and meta["doc_type"] == "price_list" and e["evidence_id"] not in row_ids:
                sel.drop(e, f"price_row_not_in_play: {row_product(e['text'])[0]} {row_product(e['text'])[1]}",
                         "vendor_products_pricing")
            else:
                kept.append(e)
        lists = {p["document_id"] for p in rows + kept if p["metadata"]["doc_type"] == "price_list"}
        notes = [sel.take(p, "price_list_notes") for p in price_passages
                 if p["document_id"] in lists and not row_product(p["text"])]
        # 4. Purpose documents.
        specs = [(purpose, d) for d in PURPOSE_DOCUMENTS.get(purpose, [])]
        specs += context_documents(purpose, records, approved_meetings)
        purpose_docs = [sel.take(p, f"purpose_document:{label}:{doc_type}")
                        for label, (doc_type, query, part) in specs
                        for p in purpose_document(doc_type, query, today, chroma_dir)
                        if part == "all" or first_product(p["text"], all_products)]
        # 5. Product-overview passages about a product in play.
        about = []
        if products:
            overview = [p for p in passages_where({"$and": [{"scope": "global"}, {"doc_type": "product_overview"}]},
                                                  chroma_dir) if in_force(p["metadata"], today)]
            about = [sel.take(p, f"product_in_play:{first_product(p['text'], all_products)}") for p in overview
                     if first_product(p["text"], all_products) in products]
        # 4b (C4.2, after the other rules, so a passage they already selected keeps its reason): vendor capability
        # statements chosen by the customer's own questions.
        have = {e["evidence_id"] for e in rows + notes + kept + purpose_docs + about}
        name_text = " ".join([(bundle.get("identity") or {}).get("name") or ""]
                             + [f"{pt[0]} {pt[1]}" for p in price_passages if (pt := row_product(p["text"]))])
        names = frozenset(w.casefold() for w in re.findall(r"\w+", name_text))  # not content terms
        capability = [sel.take(p, f"capability_request:{asked}")
                      for asked, p in capability_passages(records + approved_meetings, today, chroma_dir, names)
                      if p["evidence_id"] not in have]
        vendor["evidence"] = _merge(rows, notes, kept, purpose_docs, about, capability)

    # 7. Public sources already retrieved for this company: every verbatim excerpt, not only the ones that ranked.
    profile_block = internal.get("company_profile")
    if profile_block is not None and profile_block["evidence"]:
        from deal_prep import evidence_profile as ep
        from deal_prep.evidence import normalize
        have = {e["evidence_id"] for e in profile_block["evidence"]}
        docs = sorted({e["document_id"] for e in profile_block["evidence"] if e["info_origin"] == "public_source"})
        extra = [sel.take(p, f"public_source_excerpt:{d}") for d in docs
                 for p in passages_where({"document_id": d}, chroma_dir)[:MAX_PASSAGES_PER_DOCUMENT]
                 if p["evidence_id"] not in have
                 and ep.statement_form(normalize(p, "internal:company_profile")) == "verbatim_excerpt"]
        profile_block["evidence"] = _merge(profile_block["evidence"], extra)
    sel.data["customer_text"] = customer_text  # in memory only, for select_competition (never sent to a model)

    bundle["trace"].append({"stage": "purpose_selection", "purpose": purpose, "products_in_play": products,
                            "results": len(sel.data["selected"]),
                            "evidence_ids": sorted(sel.data["selected"]),
                            "excluded_ids": [x["evidence_id"] for x in sel.data["excluded"]],
                            "elapsed_ms": round((time.monotonic() - started) * 1000), "outcome": "ok"})


def select_competition(bundle: dict, chroma_dir) -> None:
    """6. Competitor material only when this customer's or company's evidence names that competitor (by name or
    registered alias). Owner decision (I3 review): otherwise every passage that names a competitor is left out, so no
    briefing implies an unmentioned competitor is involved. A battlecard passage that names no competitor (neutral
    guidance) is kept only when it covers a product in play, and then as vendor evidence, never as competition.
    Runs after the news search, so news naming a competitor counts."""
    internal, data = bundle["internal"], bundle.get("selection")
    if data is None:
        return
    customer_text = data.pop("customer_text", "")
    data["competition_context"] = "\n".join(  # in memory only, for screen(); never sent to a model or reported
        [customer_text] + [_text(e) for e in (internal.get("company_profile") or {}).get("evidence", [])]
        + [_text(e) for e in (bundle.get("external") or {}).get("evidence", [])])
    comp = internal.get("competition")
    if comp is None or not comp["evidence"]:
        return
    named = sorted({c for e in comp["evidence"] for c in named_competitors(e, data["competition_context"])})
    products = data["products_in_play"]
    if named:
        data["competition"] = {"relevant": True,
                               "reason": f"competitor named in customer or company evidence: {', '.join(named)}"}
    else:
        data["competition"] = {"relevant": False, "reason": "no competitor named in customer or company evidence"}
        neutral = []
        for e in comp["evidence"]:
            reason = battlecard_exclusion(e, data["competition_context"], products)
            if reason:
                data["excluded"].append({"evidence_id": e["evidence_id"], "stage": "competition", "reason": reason})
            else:
                data["selected"].setdefault(e["evidence_id"], f"neutral_guidance:product_in_play:"
                                            f"{first_product(_text(e), products)}")
                neutral.append(e)
        comp["evidence"] = []
        vendor = internal.get("vendor_products_pricing")
        if vendor is not None and neutral:
            vendor["evidence"] = _merge(vendor["evidence"], neutral)
    bundle["trace"].append({"stage": "competition_selection", "relevant": data["competition"]["relevant"],
                            "reason": data["competition"]["reason"], "elapsed_ms": 0, "outcome": "ok",
                            "evidence_ids": [e["evidence_id"] for e in comp["evidence"]]})


def competitor_terms(e: dict) -> dict[str, list[str]]:
    """{competitor name: [name, registered aliases]} for the competitors a battlecard passage is about."""
    from deal_prep import kb_index
    registry = kb_index.load_registry()
    return {o["name"]: [o["name"], *registry.get(o["org_id"], {}).get("aliases", [])]
            for o in e.get("organizations", []) if o.get("role") == "competitor"}


def _names(text: str, term: str) -> bool:
    return bool(re.search(rf"(?<!\w){re.escape(term)}(?!\w)", text or "", re.I))


def named_competitors(e: dict, context: str) -> list[str]:
    return [name for name, terms in competitor_terms(e).items() if any(_names(context, t) for t in terms)]


def battlecard_exclusion(e: dict, context: str, products: list[str]) -> str | None:
    """None when a battlecard passage may be used without a named competitor in the evidence: it names no
    competitor itself and covers a product in play. Otherwise the reason it is left out."""
    if named_competitors(e, context):
        return None
    if any(_names(_text(e), t) for terms in competitor_terms(e).values() for t in terms):
        return "competitor_not_named_in_evidence: passage names a competitor the customer's evidence does not"
    if not any(_mentions(_text(e), p) for p in products):
        return "neutral_guidance_not_grounded: covers no product in play"
    return None


# --- agent lookups -----------------------------------------------------------------------------------

def screen(found: list[dict], bundle: dict) -> list[dict]:
    """Apply the selection's exclusion rules to the research agent's internal results: price lists not in force,
    price rows of products not in play (when products are in play) and competitor material judged not relevant.
    Excluded passages are recorded with their reason; everything else passes unchanged."""
    data = bundle.get("selection")
    if not data:
        return found
    today = date.fromisoformat(data["as_of"])
    products = data.get("products_in_play") or []
    kept = []
    for e in found:
        meta = e.get("metadata") or {}
        reason = None
        if meta.get("scope") == "global" and not in_force(meta, today) and meta.get("doc_type") == "price_list":
            reason = f"not_in_force: {meta.get('approval_status') or 'unknown'}"
        elif products and meta.get("doc_type") == "price_list" and (pt := row_product(e.get("text"))) \
                and pt[0] not in products:
            reason = f"price_row_not_in_play: {pt[0]} {pt[1]}"
        elif meta.get("doc_type") == "battlecard":
            reason = battlecard_exclusion(e, data.get("competition_context", ""), products)
        if reason:
            data["excluded"].append({"evidence_id": e["evidence_id"], "reason": reason, "stage": "agent"})
        else:
            kept.append(e)
    return kept


# --- explanation -------------------------------------------------------------------------------------

def report(bundle: dict) -> dict:
    """Why each passage of the drafting input is there, and what was left out and why."""
    from deal_prep.evidence import evidence_index

    data = bundle.get("selection") or {}
    why: dict[str, str] = {}
    for t in bundle.get("trace", []):
        if t.get("stage") == "internal_rag":
            label = "approved_meeting_record" if t["topic"] == "meeting_history" else f"ranked_search:{t['topic']}"
            for i in t.get("evidence_ids", []):
                why.setdefault(i, label)
        elif t.get("stage") in ("comparison_sources", "conflict_sources"):
            for i in t.get("evidence_ids", []):
                why.setdefault(i, t["stage"].removesuffix("s"))
    why.update(data.get("selected", {}))
    out = {}
    for eid, e in evidence_index(bundle).items():
        if e["source"] == "external_news":
            out[eid] = f"news:{e.get('time_window')}"
        elif e["source"].startswith("supplemental:"):
            out[eid] = "agent:" + e["source"].split(":", 1)[1]
        else:
            out[eid] = why.get(eid, e["source"])
    return {"purpose": data.get("purpose", bundle.get("purpose")), "as_of": data.get("as_of"),
            "products_in_play": data.get("products_in_play", []), "competition": data.get("competition"),
            "evidence": out, "excluded": data.get("excluded", [])}
