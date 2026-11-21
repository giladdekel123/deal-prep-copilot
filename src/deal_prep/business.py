"""Phase 4.5 I5: deterministic business analysis for meeting preparation.

The drafter used to receive prices, proposals, policies and records and was left to reason about them (since I3.1 it
was told not to calculate). This module calculates in code, from the drafting input only, what a seller needs before
the meeting, and records every result with its formula, its inputs and the evidence each input came from:

1. Price position: the discount of each proposed price from the current list price of the same product, tier, unit
   and currency; the proposal's value at the proposed and at the list price; days left in its validity.
2. Approval: the approval tier the discount falls into, and the price below which each higher tier is needed, read
   from the discount-approval policy in the evidence. A missing or ambiguous policy gives no tier, only "verify".
3. Requested additions: the list-price cost of what the customer asked for, only when the request's unit matches the
   product's list-price unit. A requested contract term is checked against the minimum term; a price effect of the
   term is never assumed.
4. Deadlines: unresolved tasks and commitments with the days left (overdue, today, tomorrow, within 7 days).
5. Status checks: a task recorded as completed while the correspondence still shows the related request open (or
   the reverse), and commitment dates that differ.
6. Product eligibility: capabilities the product evidence limits to a product or tier.
7. Suggested meeting questions derived from the findings.
Nothing here is a commercial decision. A list price is the published price; a proposed price is an offer whose
recorded status is quoted as written; an approval tier says who may approve a discount, not that anyone did; a
list-price cost of a requested addition is not a quote. ENABLED switches I5 off for the controlled comparison only.
"""
import re
from datetime import date

from deal_prep.evidence import evidence_index, kb_evidence
from deal_prep.selection import first_product

ENABLED = True
_MONTH_NAMES = "January February March April May June July August September October November December".split()
_MONTHS = {m: i + 1 for i, m in enumerate(_MONTH_NAMES)}
_DATE_TEXT = re.compile(rf"\b(\d{{1,2}})\s+({'|'.join(_MONTH_NAMES)})\s+((?:19|20)\d{{2}})\b")
_ISO = re.compile(r"\b(\d{4})-(\d{2})-(\d{2})\b")
_AMOUNT = re.compile(r"^\d[\d,]*(?:\.\d+)?$")
_PRICE_KEY = re.compile(r"^(List|Proposed) price \(([A-Z]{3})\)$", re.I)
_UP_TO = re.compile(r"(?P<who>[A-Za-z][A-Za-z ]*?)\s+(?:may|can)\s+approve\s+discounts?\s+(?:of\s+)?up\s+to\s+"
                    r"(?P<n>\d+(?:\.\d+)?)\s*(?:percent|%)(?:\s+(?:from|of|off)\s+(?:the\s+)?(?P<basis>[a-z ]*?price))?",
                    re.I)
_ABOVE = re.compile(r"Discounts?\s+(?:of\s+)?(?:above|over|more than|exceeding)\s+(?P<n>\d+(?:\.\d+)?)\s*(?:percent|%)"
                    r"\s+requires?\s+(?P<written>written\s+)?approval\s+(?:from|by)\s+(?:the\s+)?(?P<who>[^.;]+)", re.I)
_REQUEST = re.compile(r"\b(?:asked|requested|requests?|would like)\b", re.I)
_QTY = re.compile(r"\b(?P<n>\d+(?:\.\d+)?)\s*(?P<add>additional\s+|more\s+|extra\s+)?"
                  r"(?P<unit>TB|GB|PB|users?|seats?|licen[cs]es?|sites?)\b", re.I)
_TERM = re.compile(r"\b(?P<n>\d+)-month\s+term\b", re.I)
_BY_DATE = re.compile(rf"\bby\s+(\d{{1,2}}\s+(?:{'|'.join(_MONTH_NAMES)})\s+(?:19|20)\d{{2}})\b")
_OPEN = re.compile(r"request|open|pending|not yet|question|awaiting|outstanding", re.I)
_CLOSED = re.compile(r"\b(?:sent|completed|resolved|accepted|signed|delivered)\b", re.I)
_STOP = set("""about after again also because before being between could every first from have into other should
their there these those through under until which while would their customer customers nivarque""".split())
_ELIGIBILITY = [  # (pattern with the qualifier in group "q", kind of qualifier)
    (re.compile(r"(?:available|offered)\s+(?:only\s+)?(?:for|to)\s+(?P<q>[A-Z][\w-]*(?:\s+[A-Z][\w-]*)*)\s+customers"), "customers"),
    (re.compile(r"\b(?P<q>[A-Z][\w-]*(?:\s+[A-Z][\w-]*)*)\s+customers\s+can\b"), "customers"),
    (re.compile(r"\bThe\s+(?P<q>[A-Z]\w+)\s+tier\s+adds\b"), "tier"),
    (re.compile(r"\bavailable\s+on\s+the\s+(?P<q>[A-Z]\w+)\s+tier\s+only\b"), "tier"),
]


# --- small parsers ----------------------------------------------------------------------------------

def parse_date(text) -> date | None:
    text = (text or "").strip()
    m = _ISO.search(text)
    if m:
        return date(int(m[1]), int(m[2]), int(m[3]))
    m = _DATE_TEXT.search(text)
    return date(int(m[3]), _MONTHS[m[2]], int(m[1])) if m else None


def amount(text) -> float | None:
    text = (text or "").strip()
    return float(text.replace(",", "")) if _AMOUNT.match(text) else None


def row_fields(text: str) -> dict:
    """The 'Key: value | Key: value' table row of a passage as a dict (empty when there is none)."""
    line = next((ln for ln in reversed((text or "").splitlines()) if "|" in ln and ":" in ln), "")
    out = {}
    for part in line.split("|"):
        if ":" in part:
            k, v = part.split(":", 1)
            out[k.strip()] = v.strip()
    return out


def _months(text) -> int | None:
    m = re.match(r"\s*(\d+)\s*months?\b", text or "")
    return int(m[1]) if m else None


def _singular(word: str) -> str:
    w = word.casefold()
    return w[:-1] if w.endswith("s") and len(w) > 3 else w


def unit_parts(unit: str) -> tuple[str | None, str | None]:
    """'per user per month' -> ('user', 'month'); 'per TB per month' -> ('tb', 'month'); other units unchanged."""
    m = re.fullmatch(r"per\s+([\w-]+)(?:\s+per\s+(month|year|week|day))?", (unit or "").strip(), re.I)
    if not m:
        return ((unit or "").strip().casefold() or None, None)
    return _singular(m[1]), (m[2].casefold() if m[2] else None)


def money(x: float, currency: str) -> str:
    s = f"{x:,.2f}"
    return f"{currency} {s[:-3] if s.endswith('.00') else s}"


def pct(x: float) -> str:
    return f"{x:.1f}%"


def _sentences(text: str) -> list[str]:
    flat = " ".join((text or "").split())
    return [s.strip() for s in re.split(r"(?<=[.!?])\s+", flat) if s.strip()]


def _body(e: dict) -> str:
    """A passage's text without its section heading (chunks start with the heading of their section)."""
    text = e.get("text") or ""
    section = ((e.get("metadata") or {}).get("section") or "").strip()
    if section and text.startswith(section):
        text = text[len(section):].lstrip(" \n:")
    return text


def _stems(text: str) -> set[str]:
    out = set()
    for w in re.findall(r"[A-Za-z][A-Za-z-]+", text or ""):
        w = w.casefold()
        if len(w) >= 5 and w not in _STOP and w.capitalize() not in _MONTHS:
            out.add(w[:-1] if w.endswith("s") else w)
    return out


def _cite(*ids) -> list[str]:
    return sorted({i for i in ids if i})


def _input(name, value, evidence_id, quote=None):
    out = {"name": name, "value": value, "evidence_id": evidence_id}
    if quote:
        out["quote"] = quote
    return out


# --- evidence in the drafting input -------------------------------------------------------------------

def _evidence(bundle: dict) -> list[dict]:
    """Knowledge-base and meeting-record evidence that is in the drafting input."""
    shown = set(evidence_index(bundle))
    return [e for e in kb_evidence(bundle) if e["evidence_id"] in shown]


def price_row(e: dict) -> dict | None:
    """A list-price or proposed-price table row with its currency, unit, quantity and dates."""
    f = row_fields(e.get("text"))
    for k, v in f.items():
        m = _PRICE_KEY.match(k)
        if m:
            meta = e.get("metadata", {})
            return {"evidence_id": e["evidence_id"], "document_id": e.get("document_id"), "kind": m[1].casefold(),
                    "currency": m[2].upper(), "price": amount(v), "price_text": v, "product": f.get("Product"),
                    "tier": f.get("Tier"), "unit": f.get("Unit") or "", "quantity": amount(f.get("Quantity") or ""),
                    "valid_until": parse_date(f.get("Valid until")), "minimum_term_months": _months(f.get("Minimum term")),
                    "effective_from": parse_date(meta.get("effective_from")), "doc_type": meta.get("doc_type"),
                    "approval_status": meta.get("approval_status")}
    return None


def approval_policy(evidence: list[dict]) -> dict:
    """Discount-approval tiers parsed from the policy evidence. 'parsed' only when the tiers are complete and
    consistent; otherwise 'ambiguous' (with the reason) or 'not_in_evidence'. Never guessed."""
    found = [(e, s) for e in evidence if (e.get("metadata") or {}).get("doc_type") == "policy"
             for s in _sentences(_body(e)) if re.search(r"discount", s, re.I)]
    ups = [(e, m, s) for e, s in found if (m := _UP_TO.search(s))]
    aboves = [(e, m, s) for e, s in found if (m := _ABOVE.search(s))]
    ids = _cite(*(e["evidence_id"] for e, _, _ in ups + aboves))
    quotes = [s for _, _, s in ups + aboves]
    if not ups and not aboves:
        return {"status": "not_in_evidence", "evidence_ids": [],
                "reason": "No discount-approval policy is in the evidence for this briefing."}
    problems = []
    base_limits = {float(m["n"]) for _, m, _ in ups}
    if len(base_limits) > 1:
        problems.append(f"the policy gives different base approval limits ({', '.join(pct(x) for x in sorted(base_limits))})")
    if not ups:
        problems.append("the policy does not say who may approve discounts up to its first threshold")
    thresholds: dict[float, set[str]] = {}
    written: dict[float, bool] = {}
    for _, m, _ in aboves:
        n = float(m["n"])
        thresholds.setdefault(n, set()).add(" ".join(m["who"].split()))
        written[n] = written.get(n, False) or bool(m["written"])
    if any(len(w) > 1 for w in thresholds.values()):
        problems.append("the same threshold names different approvers")
    if ups and thresholds and len(base_limits) == 1 and min(thresholds) != next(iter(base_limits)):
        problems.append(f"the base limit ({pct(next(iter(base_limits)))}) and the first threshold "
                        f"({pct(min(thresholds))}) do not meet")
    bases = {(m["basis"] or "").casefold().strip() for _, m, _ in ups}
    if bases - {"list price"}:
        problems.append("the policy does not measure discounts from the list price")
    if problems:
        return {"status": "ambiguous", "evidence_ids": ids, "quotes": quotes,
                "reason": "The discount-approval policy is ambiguous: " + "; ".join(problems) + "."}
    who = ups[0][1]["who"].split()
    caps = [i for i, t in enumerate(who) if t[0].isupper()]
    base_who = " ".join(who[caps[-1]:] if caps else who)
    tiers = [{"up_to_pct": next(iter(base_limits)), "approver": base_who, "written": False}]
    tiers += [{"above_pct": n, "approver": next(iter(thresholds[n])), "written": written[n]} for n in sorted(thresholds)]
    return {"status": "parsed", "basis": "list price", "tiers": tiers, "evidence_ids": ids, "quotes": quotes}


def _tier_for(discount: float, policy: dict) -> dict:
    tier = policy["tiers"][0]
    for t in policy["tiers"][1:]:
        if discount > t["above_pct"] + 1e-9:
            tier = t
    return tier


def _approver(t: dict) -> str:
    """'written approval from the regional sales director' for a higher tier; 'the authority of account
    executives' for the base tier."""
    if "above_pct" in t:
        return ("written approval from the " if t.get("written") else "approval from the ") + t["approver"]
    return f"the authority of {t['approver'][0].lower() + t['approver'][1:]}"


def _proposal_context(evidence, document_id):
    """Sent date and recorded decision status of a proposal document, quoted from its own passages."""
    sent, status = None, None
    for e in evidence:
        if e.get("document_id") != document_id:
            continue
        for s in _sentences(_body(e)):
            if sent is None and re.search(r"\bsent on\b", s, re.I):
                sent = (parse_date(s), e["evidence_id"], s)
            if status is None and re.search(r"\bdecision\b|\baccepted\b|\bsigned\b|\brejected\b|\bagreed\b", s, re.I):
                status = (s, e["evidence_id"])
    return sent, status


# --- the analysis -----------------------------------------------------------------------------------

def analyse(bundle: dict) -> dict:
    today = date.fromisoformat(bundle["created_at"][:10])
    evidence = _evidence(bundle)
    org = (bundle.get("identity") or {}).get("org_id")
    rows = [r for e in evidence if (r := price_row(e))]
    lists = [r for r in rows if r["kind"] == "list" and r["doc_type"] == "price_list" and r["approval_status"] == "approved"]
    customer = [e for e in evidence if org and (e.get("metadata") or {}).get("customer_org_id") == org
                and (e.get("metadata") or {}).get("approval_status") == "approved"]
    proposals = [r for e in customer if (e.get("metadata") or {}).get("doc_type") == "proposal"
                 and (r := price_row(e)) and r["kind"] == "proposed"]
    policy = approval_policy(evidence)
    validity_rule = next(((s, e["evidence_id"]) for e in evidence if (e.get("metadata") or {}).get("doc_type") == "policy"
                          for s in _sentences(_body(e)) if re.search(r"apply only to the customer", s, re.I)), None)
    vat = next(((s, e["evidence_id"]) for e in evidence if (e.get("metadata") or {}).get("doc_type") in ("price_list", "policy")
                for s in _sentences(_body(e)) if re.search(r"exclude VAT", s, re.I)), None)
    out = {"as_of": today.isoformat(), "price_positions": [], "approval_policy": policy, "requested_additions": [],
           "deadlines": [], "status_checks": [], "eligibility": [], "verification_needed": [], "suggested_questions": []}

    # 1-2. Price position and approval.
    for p in proposals:
        out["price_positions"].append(_price_position(p, lists, policy, today, evidence, validity_rule, vat))

    # 3. Requested additions and terms (customer correspondence).
    correspondence = [e for e in customer if (e.get("metadata") or {}).get("doc_type") == "correspondence"]
    products = sorted({r["product"] for r in lists if r["product"]})
    for e in correspondence:
        text = " ".join((e.get("text") or "").split())
        if re.match(r"(Subject|From|Status|Date):", text) or re.search(r"\breplied\b", text) or not _REQUEST.search(text):
            continue
        out["requested_additions"] += _requests(e, text, products, lists, proposals, evidence)

    # 4-5. Deadlines and status checks.
    tasks, commitments = _tasks_and_commitments(bundle, evidence, customer)
    out["deadlines"] = _deadlines(tasks, commitments, out["price_positions"], today)
    out["status_checks"] = _status_checks(tasks, commitments, correspondence)

    # 6. Eligibility of capabilities (products not in play).
    from deal_prep.disclosures import required_disclosures
    in_play = (bundle.get("selection") or {}).get("products_in_play", [])
    conflicted = {i for d in required_disclosures(bundle) if d["id"].startswith("conflict:")
                  for i in d.get("evidence_ids", [])}
    out["eligibility"] = _eligibility(evidence, in_play, lists, conflicted)

    for section in ("price_positions", "requested_additions"):
        for x in out[section]:
            if x["status"] != "calculated":
                out["verification_needed"].append({"about": x["id"], "reason": x["reason"],
                                                   "evidence_ids": x["evidence_ids"]})
    if proposals and policy["status"] != "parsed":
        out["verification_needed"].append({"about": "approval_policy", "reason": policy["reason"],
                                           "evidence_ids": policy["evidence_ids"]})
    out["suggested_questions"] = _questions(out)
    return out


def _price_position(p, lists, policy, today, evidence, validity_rule, vat) -> dict:
    pid = f"price_position:{p['evidence_id']}"
    base = {"id": pid, "proposal_evidence_id": p["evidence_id"], "product": p["product"], "tier": p["tier"]}
    sent, status = _proposal_context(evidence, p["document_id"])
    status_quote = {"text": status[0], "evidence_id": status[1]} if status else \
        {"text": "No decision status is recorded in the proposal evidence.", "evidence_id": None}

    def fail(reason, ids):
        return {**base, "status": "not_calculable", "reason": reason, "evidence_ids": _cite(p["evidence_id"], *ids),
                "offer_status": status_quote}

    if p["price"] is None:
        return fail(f"The proposed price ({p['price_text']!r}) is not a number.", [])
    same = [r for r in lists if (r["product"] or "").casefold() == (p["product"] or "").casefold()]
    if not same:
        return fail(f"No current list price for {p['product']} is in the evidence, so the discount cannot be "
                    f"calculated; verify the applicable list price.", [])
    tiered = [r for r in same if (r["tier"] or "").casefold() == (p["tier"] or "").casefold()] or \
        (same if len(same) == 1 else [])
    if not tiered:
        return fail(f"The list prices in the evidence are for other tiers of {p['product']}; verify the list price "
                    f"of the {p['tier']} tier.", [r["evidence_id"] for r in same])
    units = [r for r in tiered if unit_parts(r["unit"]) == unit_parts(p["unit"])]
    if not units:
        return fail(f"The proposal is priced {p['unit']}, but the list price is {tiered[0]['unit']}; the units "
                    f"differ, so they cannot be compared.", [r["evidence_id"] for r in tiered])
    cur = [r for r in units if r["currency"] == p["currency"]]
    if not cur:
        return fail(f"The proposal is in {p['currency']}, but the list price is in {units[0]['currency']}; no "
                    f"exchange rate is in the evidence.", [r["evidence_id"] for r in units])
    prices = {r["price"] for r in cur}
    if len(prices) != 1 or None in prices:
        return fail(f"The evidence gives conflicting list prices for {p['product']} ({p['tier']}); verify which "
                    f"applies.", [r["evidence_id"] for r in cur])
    lst = cur[0]
    lp, pp, q, ccy = lst["price"], p["price"], p["quantity"], p["currency"]
    discount = (lp - pp) / lp * 100
    period = unit_parts(p["unit"])[1]
    out = {**base, "status": "calculated", "unit": p["unit"], "currency": ccy, "list_price": lp, "proposed_price": pp,
           "list_evidence_id": lst["evidence_id"], "discount_pct": round(discount, 2), "discount_display": pct(discount),
           "formula": f"discount = (list price - proposed price) / list price = ({lp:g} - {pp:g}) / {lp:g} = "
                      f"{discount:.2f}%",
           "inputs": [_input("list price", f"{money(lp, ccy)} {p['unit']}", lst["evidence_id"]),
                      _input("proposed price", f"{money(pp, ccy)} {p['unit']}", p["evidence_id"])],
           "offer_status": status_quote, "evidence_ids": _cite(p["evidence_id"], lst["evidence_id"]), "caveats": []}
    if q:
        out["quantity"] = q
        out["inputs"].append(_input("quantity", f"{q:g}", p["evidence_id"]))
        if period == "month":
            out["value"] = {"proposed_monthly": round(q * pp, 2), "list_monthly": round(q * lp, 2),
                            "proposed_12_months": round(q * pp * 12, 2), "list_12_months": round(q * lp * 12, 2),
                            "difference_12_months": round(q * (lp - pp) * 12, 2),
                            "display": f"{money(q * pp, ccy)} per month at the proposed price "
                                       f"({money(q * pp * 12, ccy)} for 12 months) against {money(q * lp, ccy)} per "
                                       f"month at list ({money(q * lp * 12, ccy)} for 12 months); the proposal is "
                                       f"{money(q * (lp - pp) * 12, ccy)} below list over 12 months",
                            "formula": f"{q:g} x {pp:g} x 12 and {q:g} x {lp:g} x 12"}
    if discount < 0:
        out["approval"] = {"status": "not_needed", "text": "The proposed price is above the list price; no discount "
                                                           "approval applies."}
    elif policy["status"] == "parsed":
        tier = _tier_for(discount, policy)
        floors = [{"below_price": round(lp * (1 - t["above_pct"] / 100), 2),
                   "display": money(lp * (1 - t["above_pct"] / 100), ccy), "above_pct": t["above_pct"],
                   "meaning": f"a price below {money(lp * (1 - t['above_pct'] / 100), ccy)} (a discount above "
                              f"{pct(t['above_pct'])}) needs {_approver(t)}"} for t in policy["tiers"][1:]]
        nxt = next((f for f in floors if f["above_pct"] >= (tier.get("above_pct") or tier.get("up_to_pct"))
                    and f["above_pct"] > discount), None)
        out["approval"] = {"status": "classified", "required": _approver(tier), "tier": tier,
                           "text": f"A {pct(discount)} discount falls within {_approver(tier)} under the policy. This "
                                   f"says who may approve it; the evidence does not record that it was approved."
                                   + (f" Further concession: {nxt['meaning']}." if nxt else ""),
                           "price_floors": floors, "evidence_ids": policy["evidence_ids"],
                           "formula": "price floor = list price x (1 - threshold / 100)"}
        out["evidence_ids"] = _cite(*out["evidence_ids"], *policy["evidence_ids"])
    else:
        out["approval"] = {"status": policy["status"], "text": policy["reason"] + " Verify who must approve this "
                                                                                  "discount before offering more.",
                           "evidence_ids": policy["evidence_ids"]}
    valid = p["valid_until"]
    if valid:
        out["validity"] = {"valid_until": valid.isoformat(), "days_left": (valid - today).days,
                           "evidence_id": p["evidence_id"]}
        if validity_rule:
            out["caveats"].append({"text": validity_rule[0], "evidence_id": validity_rule[1]})
    if sent and sent[0] and lst["effective_from"] and sent[0] < lst["effective_from"]:
        out["caveats"].append({"text": f"The proposal was sent on {sent[0].isoformat()}, before the current list "
                                       f"price took effect ({lst['effective_from'].isoformat()}); the discount against "
                                       f"the list in force when it was sent cannot be calculated from the evidence.",
                               "evidence_id": sent[1]})
    if vat:
        out["caveats"].append({"text": vat[0], "evidence_id": vat[1]})
    out["caveats"].insert(0, {"text": "The proposed price is an offer, not an agreed price.",
                              "evidence_id": status_quote["evidence_id"]})
    return out


def _requests(e, text, products, lists, proposals, evidence) -> list[dict]:
    out = []
    n_before = 0
    for m in _QTY.finditer(text):
        n_before += 1
        rid = f"requested_addition:{e['evidence_id']}:{n_before}"
        qty, unit = float(m["n"]), _singular(m["unit"])
        product = first_product(text, products)
        per_user = [p for p in proposals if unit_parts(p["unit"])[0] == "user"]
        if product is None and unit == "user" and len({p["product"] for p in per_user}) == 1:
            product = per_user[0]["product"]
        base = {"id": rid, "request_evidence_id": e["evidence_id"], "request": text, "quantity": qty, "unit": unit,
                "product": product}
        if product is None:
            out.append({**base, "status": "not_calculable", "evidence_ids": [e["evidence_id"]],
                        "reason": "The request names no product with a list price in the evidence; verify what is "
                                  "being requested."})
            continue
        rows = [r for r in lists if (r["product"] or "").casefold() == product.casefold()]
        match = [r for r in rows if unit_parts(r["unit"])[0] == unit]
        if not rows:
            out.append({**base, "status": "not_calculable", "evidence_ids": [e["evidence_id"]],
                        "reason": f"No current list price for {product} is in the evidence; verify the price before "
                                  f"quoting the requested {qty:g} {m['unit']}."})
            continue
        if not match:
            out.append({**base, "status": "not_calculable", "evidence_ids": _cite(e["evidence_id"], rows[0]["evidence_id"]),
                        "reason": f"The request is in {m['unit']}, but {product} is priced {rows[0]['unit']}; the "
                                  f"units differ, so no cost can be calculated."})
            continue
        prices = {r["price"] for r in match}
        if len(prices) != 1 or None in prices:
            out.append({**base, "status": "not_calculable", "evidence_ids": _cite(e["evidence_id"], *(r["evidence_id"] for r in match)),
                        "reason": f"The evidence gives conflicting list prices for {product}; verify which applies."})
            continue
        r = match[0]
        lp, ccy, period = r["price"], r["currency"], unit_parts(r["unit"])[1]
        x = {**base, "status": "calculated", "list_price": lp, "currency": ccy, "list_evidence_id": r["evidence_id"],
             "evidence_ids": _cite(e["evidence_id"], r["evidence_id"]),
             "inputs": [_input("requested quantity", f"{qty:g} {m['unit']}", e["evidence_id"]),
                        _input("list price", f"{money(lp, ccy)} {r['unit']}", r["evidence_id"])],
             "basis": "list price; not a quote or an agreed price"}
        if period == "month":
            x["monthly_at_list"] = round(qty * lp, 2)
            x["formula"] = f"{qty:g} x {lp:g} = {qty * lp:g} per month at list"
            x["display"] = f"{money(qty * lp, ccy)} per month at list ({money(qty * lp * 12, ccy)} for 12 months)"
            x["twelve_months_at_list"] = round(qty * lp * 12, 2)
            if r["minimum_term_months"]:
                months = r["minimum_term_months"]
                x["minimum_term_months"] = months
                x["minimum_term_at_list"] = round(qty * lp * months, 2)
                x["display"] += f"; {money(qty * lp * months, ccy)} over the {months}-month minimum term"
                x["inputs"].append(_input("minimum term", f"{months} months", r["evidence_id"]))
        else:
            x["total_at_list"] = round(qty * lp, 2)
            x["formula"] = f"{qty:g} x {lp:g} = {qty * lp:g}"
            x["display"] = f"{money(qty * lp, ccy)} at list"
        same_product = [p for p in proposals if (p["product"] or "").casefold() == product.casefold() and p["quantity"]]
        if m["add"] and same_product:
            total = same_product[0]["quantity"] + qty
            x["quantity_after_addition"] = total
            x["display"] += (f"; {total:g} {m['unit']} in total with the {same_product[0]['quantity']:g} already "
                             f"proposed (no price for the additional {m['unit']} has been quoted)")
            x["evidence_ids"] = _cite(*x["evidence_ids"], same_product[0]["evidence_id"])
        x["display"] += ", excluding VAT" if any("VAT" in (q.get("text") or "") for q in evidence) else ""
        out.append(x)
    for m in _TERM.finditer(text):
        months = int(m["n"])
        rid = f"requested_term:{e['evidence_id']}"
        product_rows = [r for r in lists if any((p["product"] or "").casefold() == (r["product"] or "").casefold()
                                                for p in proposals)]
        minimum = next((r["minimum_term_months"] for r in product_rows if r["minimum_term_months"]), None)
        rule = next((s for q in evidence if (q.get("metadata") or {}).get("doc_type") in ("policy", "price_list")
                     for s in _sentences(_body(q)) if re.search(r"\bterm\b", s, re.I)
                     and re.search(r"discount|lower|reduc|price", s, re.I) and "Minimum term" not in s), None)
        reason = ("No rule in the evidence links a longer contract term to a lower price, so the price effect of a "
                  f"{months}-month term cannot be calculated; any reduction would be a new discount under the "
                  "discount-approval policy.") if not rule else None
        out.append({"id": rid, "request_evidence_id": e["evidence_id"], "request": text, "term_months": months,
                    "status": "not_calculable" if reason else "rule_found", "reason": reason or rule,
                    "minimum_term_months": minimum,
                    "minimum_term_check": (f"A {months}-month term meets the {minimum}-month minimum term."
                                           if minimum and months >= minimum else
                                           f"A {months}-month term is shorter than the {minimum}-month minimum term."
                                           if minimum else "No minimum term for the proposed product is in the "
                                                           "evidence."),
                    "evidence_ids": _cite(e["evidence_id"], *(r["evidence_id"] for r in product_rows))})
    return out


def _tasks_and_commitments(bundle, evidence, customer):
    tasks = []
    for e in (bundle.get("internal", {}).get("meeting_history") or {}).get("evidence", []):
        record = e.get("record") or {}
        for n, t in enumerate(record.get("follow_up_tasks", [])):
            tasks.append({"evidence_id": e["evidence_id"], "n": n, "description": t["description"],
                          "status": t["status"], "due": parse_date(t.get("due_date")), "due_text": t.get("due_date")})
    commitments = []  # dated promises in the customer's correspondence
    for e in customer:
        if (e.get("metadata") or {}).get("doc_type") != "correspondence":
            continue
        for s in _sentences(_body(e)):
            for m in _BY_DATE.finditer(s):
                if re.search(r"\bwill\b|\breplied\b|\bpromised\b", s, re.I):
                    commitments.append({"evidence_id": e["evidence_id"], "document_id": e["document_id"], "text": s,
                                        "due": parse_date(m[1])})
    return tasks, commitments


def _urgency(days: int) -> str:
    return ("overdue" if days < 0 else "due today" if days == 0 else "due tomorrow" if days == 1 else
            "due within 7 days" if days <= 7 else "due within 30 days" if days <= 30 else "later")


def _deadlines(tasks, commitments, positions, today) -> list[dict]:
    out = []
    for t in tasks:
        if t["status"] == "Completed":
            continue
        if not t["due"]:
            out.append({"id": f"deadline:{t['evidence_id']}:{t['n']}", "what": t["description"], "status": t["status"],
                        "due": None, "urgency": "no due date", "evidence_ids": [t["evidence_id"]],
                        "text": f"'{t['description']}' ({t['status']}) has no confirmed due date ({t['due_text']})."})
            continue
        days = (t["due"] - today).days
        linked = [c for c in commitments if c["due"] == t["due"] and len(_stems(c["text"]) & _stems(t["description"])) >= 2]
        out.append({"id": f"deadline:{t['evidence_id']}:{t['n']}", "what": t["description"], "status": t["status"],
                    "due": t["due"].isoformat(), "days_left": days, "urgency": _urgency(days),
                    "evidence_ids": _cite(t["evidence_id"], *(c["evidence_id"] for c in linked)),
                    "text": f"'{t['description']}' ({t['status']}) is {_urgency(days)}: due {t['due'].isoformat()}, "
                            f"{abs(days)} day{'s' if abs(days) != 1 else ''} {'after' if days < 0 else 'from'} the "
                            f"briefing date" + (" (also promised in the correspondence)" if linked else "") + "."})
    for c in commitments:
        if not c["due"] or any(c["due"].isoformat() == d.get("due") and set(d["evidence_ids"]) & {c["evidence_id"]}
                               for d in out):
            continue
        if any(c["due"] == t["due"] and len(_stems(c["text"]) & _stems(t["description"])) >= 2 for t in tasks):
            continue  # the matching task is completed: covered by the status check
        days = (c["due"] - today).days
        out.append({"id": f"commitment:{c['evidence_id']}", "what": c["text"], "status": "promised in correspondence",
                    "due": c["due"].isoformat(), "days_left": days, "urgency": _urgency(days),
                    "evidence_ids": [c["evidence_id"]],
                    "text": f"Commitment '{c['text']}' is {_urgency(days)} ({abs(days)} days)."})
    for p in positions:
        v = p.get("validity")
        if v:
            out.append({"id": f"validity:{p['proposal_evidence_id']}", "what": f"validity of the {p['product']} proposal",
                        "status": "proposal valid until", "due": v["valid_until"], "days_left": v["days_left"],
                        "urgency": _urgency(v["days_left"]), "evidence_ids": [v["evidence_id"]],
                        "text": f"The proposal is valid until {v['valid_until']} ({v['days_left']} days from the "
                                f"briefing date)."})
    return sorted(out, key=lambda d: (d.get("days_left") is None, d.get("days_left") or 0))


def _status_checks(tasks, commitments, correspondence) -> list[dict]:
    status_line = {}
    for e in correspondence:
        for s in _sentences(_body(e)):
            if s.startswith("Status:"):
                status_line[e["document_id"]] = (s, e["evidence_id"])
    out = []
    for c in commitments:
        line = status_line.get(c["document_id"])
        corr_open = bool(line and _OPEN.search(line[0]))
        corr_closed = bool(line and not corr_open and _CLOSED.search(line[0]))
        for t in tasks:
            if len(_stems(c["text"]) & _stems(t["description"])) < 2:
                continue
            corr_ids = _cite(c["evidence_id"], line[1] if line else None)
            ids = _cite(t["evidence_id"], *corr_ids)
            link = {"task_evidence_id": t["evidence_id"], "correspondence_evidence_ids": corr_ids}
            if t["status"] == "Completed" and corr_open:
                out.append({"id": f"status_check:{t['evidence_id']}:{t['n']}", "kind": "status_disagreement",
                            "evidence_ids": ids, **link,
                            "text": f"The meeting record marks '{t['description']}' as Completed, but the latest "
                                    f"correspondence still shows '{line[0]}' after the reply '{c['text']}'. Verify "
                                    f"whether the customer has received it; the correspondence may predate the "
                                    f"completion, or the records may be out of date."})
            elif t["status"] != "Completed" and corr_closed:
                out.append({"id": f"status_check:{t['evidence_id']}:{t['n']}", "kind": "status_disagreement",
                            "evidence_ids": ids, **link,
                            "text": f"The correspondence shows '{line[0]}', but the meeting record still lists "
                                    f"'{t['description']}' as {t['status']}. Verify which is current."})
            if t["due"] and c["due"] and t["due"] != c["due"]:
                out.append({"id": f"date_check:{t['evidence_id']}:{t['n']}", "kind": "date_disagreement",
                            "evidence_ids": ids, **link,
                            "text": f"'{t['description']}' is due {t['due'].isoformat()} in the meeting record, but "
                                    f"the correspondence says '{c['text']}'. Verify the committed date."})
    return out


def _eligibility(evidence, in_play, lists, conflicted: set) -> list[dict]:
    """Capabilities the product evidence limits to a product or tier that is not in play for this customer.
    Passages quoted by a conflict disclosure are left to the conflict rules (their statements are disputed)."""
    out = []
    in_play_names = [p.casefold() for p in in_play]
    in_play_tiers = {(r["tier"] or "").casefold() for r in lists if (r["product"] or "").casefold() in in_play_names}
    for e in evidence:
        meta = e.get("metadata") or {}
        if meta.get("doc_type") not in ("product_overview", "policy") or e["evidence_id"] in conflicted:
            continue
        sentences = _sentences(_body(e))
        for s in sentences:
            for pattern, kind in _ELIGIBILITY:
                m = pattern.search(s)
                if not m:
                    continue
                q = m["q"]
                held = (any(q.casefold() in p for p in in_play_names) if kind == "customers"
                        else q.casefold() in in_play_tiers)
                if held:
                    continue
                triggers = _trigger_words(s, q, " ".join(x for x in sentences if x != s))
                out.append({"id": f"eligibility:{e['evidence_id']}:{len(out) + 1}", "evidence_id": e["evidence_id"],
                            "capability": s, "available_to": f"{q} {kind}" if kind == "customers" else f"{q} tier",
                            "marker": q, "triggers": triggers, "limit": _limit_wording(m.group(0), q, kind)})
                break
    return out


def _limit_wording(matched: str, q: str, kind: str) -> str:
    """Correction (a), owner-approved 2026-11-14: the limit in the source's own terms. "Only" is said only when the
    source says it; "The Business tier adds X" stays "the Business tier adds it" (another product built on that tier
    may include it too)."""
    if kind == "tier":
        return (f"it is available on the {q} tier only" if re.search(r"\bonly\b", matched)
                else f"the source says the {q} tier adds it (do not say 'only')")
    if re.search(r"\bonly\b", matched):
        return f"it is available to {q} customers only"
    return f"the source says it is for {q} customers (do not say 'only')"


_TRIGGER_STOP = {"available", "customer", "customers", "offered", "their", "adds", "with", "only", "tier", "that"}


def _trigger_words(sentence: str, qualifier: str, rest: str) -> list[str]:
    """Words that identify the restricted capability in an item: words of the eligibility sentence (hyphenated
    parts split) that are not the qualifier and do not also occur (by their first six letters) in the rest of the
    passage, so a general statement in the same passage does not trigger the qualification."""
    rest = rest.casefold()
    q = {w.casefold() for w in re.findall(r"[A-Za-z]+", qualifier)}
    words = {w.casefold() for w in re.findall(r"[A-Za-z]+", sentence)}
    out = set()
    for w in words - q - _TRIGGER_STOP:
        stem = w[:-1] if w.endswith("s") and len(w) >= 4 else w
        if len(stem) >= 3 and len(w) >= 4 and stem[:6] not in rest:
            out.add(stem)
    return sorted(out)


def _questions(a: dict) -> list[dict]:
    qs = []
    for p in a["price_positions"]:
        if p["status"] != "calculated":
            qs.append({"text": f"Verify the price basis for the {p['product']} proposal: {p['reason']}",
                       "evidence_ids": p["evidence_ids"]})
            continue
        qs.append({"text": f"The proposed {money(p['proposed_price'], p['currency'])} is {p['discount_display']} below "
                           f"the {money(p['list_price'], p['currency'])} list price ({p['offer_status']['text']}). "
                           f"{p.get('approval', {}).get('text', '')}", "evidence_ids": p["evidence_ids"]})
    for r in a["requested_additions"]:
        if r["status"] == "calculated":
            qs.append({"text": f"Confirm the requested {r['quantity']:g} {r['unit']} of {r['product']}: "
                               f"{r['display']}. This is a list-price cost, not a quote.",
                       "evidence_ids": r["evidence_ids"]})
        elif r.get("term_months"):
            qs.append({"text": f"Ask what the customer expects from a {r['term_months']}-month term. "
                               f"{r['minimum_term_check']} {r['reason']}", "evidence_ids": r["evidence_ids"]})
        else:
            qs.append({"text": f"Verify the request before answering: {r['reason']}", "evidence_ids": r["evidence_ids"]})
    for d in a["deadlines"]:
        if d.get("urgency") in ("overdue", "due today", "due tomorrow", "due within 7 days"):
            qs.append({"text": f"Confirm '{d['what']}': {d['urgency']} ({d['due']}).", "evidence_ids": d["evidence_ids"]})
    for s in a["status_checks"]:
        qs.append({"text": s["text"], "evidence_ids": s["evidence_ids"]})
    return qs


# --- what the drafter sees, and figure tracing -----------------------------------------------------------

def model_view(a: dict) -> dict:
    """The analysis as the drafter receives it (results, formulas, inputs, caveats, evidence IDs; no internals)."""
    def clean(x):  # the policy wording and tier internals repeat the cited evidence and the approval text
        if isinstance(x, dict):
            return {k: clean(v) for k, v in x.items()
                    if k not in ("request", "quotes", "tier") and v not in (None, [], {})}
        if isinstance(x, list):
            return [clean(v) for v in x]
        return x
    view = clean(a)
    view["note"] = ("Calculated by code from the cited evidence. List price = published price; proposed price = an "
                    "offer with its recorded status; approval tier = who may approve, not an approval; list-price "
                    "cost of a request = not a quote.")
    return view


def _numbers(text: str) -> set[float]:
    """Every value the numbers of a text can have (C1: deal_prep.numbers; an ambiguous literal gives all its
    readings)."""
    from deal_prep import numbers
    return numbers.values(text)


def _walk_numbers(x) -> set[float]:
    if isinstance(x, bool):
        return set()
    if isinstance(x, (int, float)):
        return {float(x)}
    if isinstance(x, str):
        return _numbers(x)
    if isinstance(x, dict):
        return set().union(*(_walk_numbers(v) for v in x.values())) if x else set()
    if isinstance(x, list):
        return set().union(*(_walk_numbers(v) for v in x)) if x else set()
    return set()


def _member(x: float, pool: set[float]) -> bool:
    return any(abs(x - a) <= 0.005 + 1e-9 for a in pool)


def figure_check(draft: dict, bundle: dict, analysis: dict) -> dict:
    """Figures in the briefing that appear in no evidence and no analysis result (untraced), figures in FACT items
    that come only from the analysis, not from the fact's own cited evidence (a calculation stated as fact), and (C1)
    figures whose value matches but whose currency, scale, unit, metric, period or reported/expected meaning differs
    from every matching evidence occurrence (mismatched). See deal_prep.figure_verify."""
    from deal_prep import figure_verify

    index = evidence_index(bundle)
    raw = {e["evidence_id"]: e.get("text") or "" for e in kb_evidence(bundle)}
    evidence = {eid: {"text": raw.get(eid) or e.get("excerpt") or "", "document_id": e.get("document_id"),
                      "entry": e} for eid, e in index.items()}
    return figure_verify.verify(draft, evidence, analysis)
