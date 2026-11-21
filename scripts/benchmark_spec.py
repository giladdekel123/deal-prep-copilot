"""Phase 4.5 I0-b: compile fictional benchmark company specifications. FICTIONAL TEST DATA only.

A company specification (eval/benchmark_v1/<split>/companies/*.json) describes one fictional company with named
values ("knobs"), for example {{OFFICIAL_COUNT}}. compile_company(spec, values) renders:
  - the registry entry (plus an optional look-alike), the corpus files and manifest entries,
  - the news fixtures, the meeting-history seed, and the scenarios,
  - the expected outcomes, DERIVED by fixed general rules from the structure and the values (never hand-written
    per scenario). Changing a value therefore changes the expected outcomes consistently.
Evidence is named by stable references: "<document ID>:E1" (the passage holding excerpt E1), "<document ID>:CLAIMS"
(the claims passage), "<document ID>~<text>" (the passage of that document containing the text), "NEWS:<key>",
"HIST:<key>". The harness resolves them to passage IDs after chunking, so they survive chunking changes.

Held-out values come from the owner's plain-text forms (heldout/forms/*.txt). check_forms() and review pages never
print a value to the console.
"""
import copy
import json
import re
from datetime import date, datetime, timedelta
from pathlib import Path

MONTHS = "January February March April May June July August September October November December".split()
STATUSES = ("Open", "In Progress", "Completed")
PRODUCTS = {"Nivarque Core": "Business", "Nivarque Engineering Vault": "Enterprise"}
# Vendor price list 2026 rows (data/kb_v1, unchanged), by stable text reference, keyed by the product names the
# scorer recognises. The Starter tier is never the product discussed in a benchmark relationship.
PRICE_ROWS = {"Starter": "NVQ-PRC-2026-v1~Tier: Starter", "Nivarque Core": "NVQ-PRC-2026-v1~Tier: Business",
              "Engineering Vault": "NVQ-PRC-2026-v1~Nivarque Engineering Vault",
              "Records Retention": "NVQ-PRC-2026-v1~Records Retention Add-on"}
SCORER_NAME = {"Nivarque Core": "Nivarque Core", "Nivarque Engineering Vault": "Engineering Vault"}
SUPERSEDED = ["NVQ-PRC-2025-v1~Tier: Starter", "NVQ-PRC-2025-v1~Tier: Business"]
NEWS_AGE = {"fresh": timedelta(hours=20), "recent": timedelta(days=15), "stale": timedelta(days=120)}
LABEL = "FICTIONAL TEST DATA"
BANNER = ("SYNTHETIC RECORD — fictional relationship with a real company. Not a real business fact. "
          "FICTIONAL BENCHMARK RECORD (FICTIONAL TEST DATA): {name} is a fictional benchmark company.")


# --- values ------------------------------------------------------------------------------------------

def long_date(iso: str) -> str:
    d = date.fromisoformat(iso)
    return f"{d.day} {MONTHS[d.month - 1]} {d.year}"


def validate_value(kind: str, v: str) -> str | None:
    """None if the value is valid for its kind, else a short reason (never echoing the value)."""
    try:
        if kind == "int":
            return None if 1 <= int(v) <= 100000 else "must be a whole number from 1 to 100000"
        if kind == "year":
            return None if 1900 <= int(v) <= 2026 else "must be a year from 1900 to 2026"
        if kind == "date":
            return None if date(2026, 1, 1) <= date.fromisoformat(v) <= date(2027, 12, 31) else \
                "must be a date in 2026 or 2027, written YYYY-MM-DD"
        if kind == "status":
            return None if v in STATUSES else f"must be one of: {', '.join(STATUSES)}"
        if kind == "news":
            return None if v in NEWS_AGE else "must be one of: fresh, recent, stale"
        if kind == "product":
            return None if v in PRODUCTS else f"must be one of: {', '.join(PRODUCTS)}"
    except ValueError:
        return "has the wrong format"
    return f"unknown kind {kind}"


def defaults(spec: dict) -> dict:
    return {k: str(v["default"]) for k, v in spec["values"].items()}


def parse_form(text: str) -> dict:
    """KEY = value   [format]   explanation   ->   {KEY: value}. Lines starting with # are comments."""
    out = {}
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, rest = line.split("=", 1)
        out[key.strip()] = rest.split("[", 1)[0].strip()
    return out


def write_form(spec: dict, number: int, total: int) -> str:
    lines = [f"# Held-out company {number} of {total}: {spec['name']} ({spec['industry']}) — {LABEL}",
             "# Change any value to the right of '='. Keep the format shown in [brackets]. Save the file.",
             "# Your values decide the expected answers automatically; you never edit the answers themselves.",
             "# Do not paste these values into the chat with Claude Code.", ""]
    for key, v in spec["values"].items():
        lines += [f"# {v['explain']}", f"{key} = {v['default']}   [{v['kind']}{': ' + v['hint'] if v.get('hint') else ''}]", ""]
    return "\n".join(lines)


def consistency_problems(spec: dict, values: dict) -> list[str]:
    """Problems by KEY name only (values are never echoed)."""
    probs = [f"{k} is missing" for k in spec["values"] if k not in values]
    probs += [f"{k} is not a known value for this company" for k in values if k not in spec["values"]]
    for k, v in spec["values"].items():
        if k in values:
            why = validate_value(v["kind"], values[k])
            if why:
                probs.append(f"{k} {why}")
    rel = spec.get("relationship")
    if rel and not probs:  # dates must make sense against the fixed record dates (checked without echoing values)
        if values["VALID_UNTIL"] <= rel["sent_iso"]:
            probs.append("VALID_UNTIL must be after the date the proposal was sent")
        if values["QUOTE_DUE"] <= rel["email"]["date_iso"]:
            probs.append("QUOTE_DUE must be after the date of the customer's email")
    return probs


# --- substitution ------------------------------------------------------------------------------------

def _fill(obj, values: dict):
    if isinstance(obj, str):
        def rep(m):
            key, fmt = m.group(1), m.group(2)
            v = values[key]
            return long_date(v) if fmt == "long" else v
        return re.sub(r"\{\{(\w+)(?::(\w+))?\}\}", rep, obj)
    if isinstance(obj, list):
        return [_fill(x, values) for x in obj]
    if isinstance(obj, dict):
        return {k: _fill(v, values) for k, v in obj.items()}
    return obj


# --- rendering -----------------------------------------------------------------------------------------

def _public_md(title, name, publisher, url, published, verification, excerpts: dict, limitations: list) -> str:
    lines = [f"# PUBLIC SOURCE — FICTIONAL BENCHMARK SOURCE ({LABEL}) — {title}", "",
             f"- **Subject organization:** {name} (FICTIONAL BENCHMARK organization; not a real company)",
             f"- **Source:** {publisher} — {url}", f"- **Publication date:** {published}", "- **Retrieved:** 2026-11-02",
             f"- **Verification:** {verification}", "", "## Excerpts", ""]
    for eid, text in excerpts.items():
        lines += [f'> [{eid}] "{text}"', ""]
    lines += ["## Claims", ""] + [f"- [C{eid[1:]}] {text} ({eid})" for eid, text in excerpts.items()]
    lines += ["", "## Limitations", ""] + [f"- {x}" for x in limitations + [
        "This is a fictional benchmark source written for evaluation (FICTIONAL TEST DATA)."]] + [""]
    return "\n".join(lines)


def _public_doc(doc_id, path, title, org_id, url, publisher, published, verification, excerpts: dict) -> dict:
    return {"document_id": doc_id, "title": f"{title} ({LABEL})", "file_path": path, "file_type": "md",
            "doc_type": "public_profile", "info_origin": "public_source", "creation_method": "curated_snapshot",
            "organizations": [{"org_id": org_id, "role": "subject"}], "document_version": "1.0",
            "approval_status": "approved", "scope": "company", "language": "en", "source_url": url,
            "publisher": publisher, "publication_date": published, "retrieved_at": "2026-11-02",
            "verification_status": verification,
            "excerpts": [{"excerpt_id": e, "text": t} for e, t in excerpts.items()],
            "claims": [{"claim_id": f"C{e[1:]}", "text": t, "excerpt_id": e} for e, t in excerpts.items()]}


def _synthetic_doc(doc_id, path, ftype, doc_type, title, org_id, cats, issued, effective_to=None) -> dict:
    return {"document_id": doc_id, "title": f"{title} ({LABEL})", "file_path": path, "file_type": ftype,
            "doc_type": doc_type, "info_origin": "synthetic_record", "creation_method": "authored_fixture",
            "organizations": [{"org_id": "nivarque", "role": "vendor"}, {"org_id": org_id, "role": "customer"}],
            "synthetic_relationship": True, "synthetic_categories": cats, "document_version": "1.0",
            "issued_at": issued, "effective_from": issued, "effective_to": effective_to, "approval_status": "approved",
            "scope": "company", "language": "en"}


def compile_company(spec: dict, values: dict, clock: datetime) -> dict:
    """Render one company. Returns registry entries, documents {manifest, path, text}, news, seed, scenarios and
    expected outcomes per (scenario, news mode)."""
    v = dict(values)
    s = _fill(copy.deepcopy({k: x for k, x in spec.items() if k != "values"}), v)
    name, code, org = s["name"], s["code"], s["org_id"]
    registry = [{"org_id": org, "name": name, "aliases": s.get("aliases", []), "reality": "real",
                 "benchmark_fictional": True, "industry": s["industry"], "country": "Fictional (benchmark)",
                 "official_domain": s["domain"], "identity_sources": [f"https://{s['domain']}/about"]}]
    if s.get("lookalike"):
        la = s["lookalike"]
        registry.append({"org_id": la["org_id"], "name": la["name"], "aliases": [], "reality": "real",
                         "benchmark_fictional": True, "industry": la["industry"], "country": "Fictional (benchmark)",
                         "official_domain": la["domain"], "identity_sources": [f"https://{la['domain']}/"],
                         "public_only": True, "note": f"Look-alike of {name}; no records of any kind."})
    docs = []
    p = s["profile"]
    pid, aid = f"NVQ-PUB-{code}-001", f"NVQ-PUB-{code}-002"
    url = f"https://{s['domain']}{p['path']}"
    ex = {"E1": p["count"], "E2": p["decision"], "E3": p["state"], "E4": p["undated"]}
    docs.append({"manifest": _public_doc(pid, f"public/{pid}.md", f"{name}: {p['title']}", org, url,
                                         f"{name} [FICTIONAL BENCHMARK]", p["published"], "primary", ex),
                 "text": _public_md(f"{name}: {p['title']}", name, f"{name} [FICTIONAL BENCHMARK]", url,
                                    p["published"], "primary (company's own website)", ex,
                                    ["E4 gives no date."])})
    a = s["aggregator"]
    docs.append({"manifest": _public_doc(aid, f"public/{aid}.md", f"{a['publisher']}: {name}", org, a["url"],
                                         f"{a['publisher']} [FICTIONAL BENCHMARK aggregator]", "unknown",
                                         "single_secondary", {"E1": a["count"]}),
                 "text": _public_md(f"{a['publisher']}: {name}", name, f"{a['publisher']} (fictional aggregator)",
                                    a["url"], "unknown", "single_secondary (aggregator profile)", {"E1": a["count"]},
                                    ["An undated aggregator profile."])})
    rel = s.get("relationship")
    prp, cor = f"NVQ-PRP-{code}-001", f"NVQ-COR-{code}-001"
    if rel:
        product, tier = v["PRODUCT"], PRODUCTS[v["PRODUCT"]]
        valid = long_date(v["VALID_UNTIL"])
        text = "\n".join([f"# Proposal: {product} for {name} ({LABEL})", "", f"> {BANNER.format(name=name)}", "",
                          "## Scope", "", f"Nivarque proposes {product} ({tier} tier) for {rel['users']} users {rel['scope']}.",
                          "", f"This proposal was sent on {rel['sent']}. No decision has been recorded.", "",
                          "## Proposed pricing", "", "| Product | Tier | Quantity | Unit | Proposed price (USD) | Valid until |",
                          "|---|---|---|---|---|---|",
                          f"| {product} | {tier} | {rel['users']} | per user per month | {rel['price']} | {valid} |", ""])
        docs.append({"manifest": _synthetic_doc(prp, f"synthetic/{prp}.md", "md", "proposal",
                                                f"Proposal: {product} for {name}", org,
                                                ["proposal", "price", "customer_relationship"], rel["sent_iso"],
                                                v["VALID_UNTIL"]), "text": text})
        e = rel["email"]
        text = "\n".join([f"> {BANNER.format(name=name)}", "", f"Subject: {e['subject']} ({prp})", "",
                          f"From: {e['from']}. To: Nivarque account executive. Date: {e['date']}.", "", e["request"], "",
                          f"Nivarque replied that the revised quote will be sent by {long_date(v['QUOTE_DUE'])}.", "",
                          f"Status: {e['status']}", ""])
        docs.append({"manifest": _synthetic_doc(cor, f"synthetic/{cor}.txt", "txt", "correspondence",
                                                f"Email: {e['subject']}", org, ["correspondence", "customer_relationship"],
                                                e["date_iso"]), "text": text})
    news = []
    for n in s["news"]:
        when = n["when"]
        published = None if when == "undated" else (clock - NEWS_AGE[when]).strftime("%Y-%m-%dT%H:%M:%SZ")
        news.append({"key": n["key"], "role": n["role"], "when": when, "title": n["title"], "url": n["url"],
                     "published_date": published, "score": n.get("score", 0.8),
                     "content": f"FICTIONAL BENCHMARK {'DATA PAGE' if n['role'] == 'data_page' else 'NEWS'} "
                                f"({LABEL}). {n['content']}"})
    seed = []
    h = s.get("history")
    if h:
        tasks = [{"key": t["key"], "description": filled["description"], "due_date": v.get(t["due"], t["due"]),
                  "final_status": v.get(t["status"], t["status"])}
                 for t, filled in zip(spec["history"]["tasks"], h["tasks"])]
        seed.append({"key": f"{code}-meeting", "approve": True, "meeting_date": h["meeting_date"], "notes": h["summary"],
                     "approved": {k: h[k] for k in ("summary", "participants", "concerns", "decisions", "commitments")},
                     "tasks": tasks})
        seed.append({"key": f"{code}-draft", "approve": False, "meeting_date": h["draft_date"], "notes": h["draft"]})
    out = {"registry": registry, "documents": docs, "news": news, "seed": seed, "scenarios": [], "expected": {}}
    for sc in s["scenarios"]:
        scenario = {"id": sc["id"], "company": name, "domain": None, "purpose": sc["purpose"]}
        out["scenarios"].append(scenario)
        for mode in ("news_fixture", "news_off"):
            out["expected"][(sc["id"], mode)] = derive_expected(s, v, sc["purpose"], mode, news, seed)
    return out


# --- expected outcomes (general rules, no per-scenario answers) ---------------------------------------

def derive_expected(s: dict, v: dict, purpose: str, mode: str, news: list, seed: list) -> dict:
    code, org = s["code"], s["org_id"]
    pid, aid, prp, cor = (f"NVQ-PUB-{code}-001", f"NVQ-PUB-{code}-002", f"NVQ-PRP-{code}-001", f"NVQ-COR-{code}-001")
    rel, hist = s.get("relationship"), bool(seed)
    news_on = mode == "news_fixture"
    count_fact = [f"{pid}:E1", f"{pid}:CLAIMS"]
    main = [n for n in news if n["role"] == "main"]
    reachable_main = [f"NEWS:{n['key']}" for n in main if n["when"] in ("fresh", "recent")] if news_on else []
    e = {"must_reach_drafter": [count_fact], "must_not_reach_drafter": [], "must_cite": [count_fact],
         "must_not_cite": list(SUPERSEDED), "history": {"meetings": [], "tasks": [], "draft_phrases": []},
         "temporal": {"compatible_pairs": [], "contradictions": [], "undated": [f"{pid}:E4"]},
         "authority": [], "data_pages": [], "required_open_items": [], "existing_terms": [],
         "customer_evidence": [pid, f"NVQ-PRP-{code}-", f"NVQ-COR-{code}-"], "allowed_products": [],
         "allowed_competitors": [], "required_disclosures": []}
    for r in reachable_main:
        e["must_reach_drafter"].append([r])
        e["must_cite"].append([r])
        e["customer_evidence"].append(r)
    if news_on:
        e["must_not_reach_drafter"] += [f"NEWS:{n['key']}" for n in news
                                        if n["role"] in ("passing", "lookalike") or n["when"] == "stale"]
        e["data_pages"] = [f"NEWS:{n['key']}" for n in news if n["role"] == "data_page"]
        e["must_not_cite"] += e["data_pages"]
    else:
        e["required_disclosures"].append({"contains": "news was not searched"})
    # Counts: equal = the aggregator copies the official figure; different = a genuine contradiction.
    if int(v["OFFICIAL_COUNT"]) == int(v["AGG_COUNT"]):  # compared as numbers, not text
        e["authority"].append({"preferred": [f"{pid}:E1"], "weaker": [f"{pid}:CLAIMS", f"{aid}:E1", f"{aid}:CLAIMS"]})
        e["must_not_cite"] += [f"{aid}:E1", f"{aid}:CLAIMS"]
    else:
        e["temporal"]["contradictions"].append([count_fact, [f"{aid}:E1", f"{aid}:CLAIMS"]])
        e["authority"].append({"preferred": [f"{pid}:E1"], "weaker": [f"{pid}:CLAIMS"]})
        e["must_not_cite"] += [f"{aid}:E1", f"{aid}:CLAIMS"]
    # A decision and the resulting state: compatible when the state follows the decision, else a contradiction.
    pair = [[f"{pid}:E2"], [f"{pid}:E3"]]
    (e["temporal"]["compatible_pairs"] if int(v["DECISION_YEAR"]) <= int(v["STATE_YEAR"])
     else e["temporal"]["contradictions"]).append(pair)
    if rel:
        e["allowed_products"] = sorted({SCORER_NAME[v["PRODUCT"]],
                                        *(["Records Retention"] if "Records Retention" in rel["email"]["request"] else [])})
        e["must_not_cite"] += [ref for name_, ref in PRICE_ROWS.items() if name_ not in e["allowed_products"]]
        terms = f"{prp}~Proposed price"
        e["must_reach_drafter"] += [[terms], [f"{prp}~This proposal was sent"], [f"{cor}~{rel['email']['request_key']}"],
                                    [f"{cor}~replied that"]]
        e["must_cite"] += [[terms], [f"{cor}~{rel['email']['request_key']}", f"{cor}~replied that"]]
        e["existing_terms"] = [terms]
    else:
        e["required_disclosures"].append({"contains": "No prior relationship records"})
    if hist:
        meet = seed[0]
        e["must_reach_drafter"].append([f"HIST:{meet['key']}"])
        e["must_cite"].append([f"HIST:{meet['key']}"])
        e["customer_evidence"].append(f"HIST:{meet['key']}")
        e["history"] = {"meetings": [meet["key"]], "tasks": [t["key"] for t in meet["tasks"]],
                        "draft_phrases": [s["history"]["draft_phrase"]]}
    if purpose in ("follow_up", "negotiation") and rel:
        for t in (seed[0]["tasks"] if hist else []):
            if t["final_status"] != "Completed":
                ev = [f"HIST:{seed[0]['key']}"] + ([f"{cor}~replied that"] if t["due_date"] == v["QUOTE_DUE"] else [])
                e["required_open_items"].append({"key": f"open task: {t['description']}", "evidence_any": ev,
                                                 "phrases_any": [long_date(t["due_date"]), t["due_date"]]})
        if purpose == "follow_up":
            em = rel["email"]
            e["required_open_items"].append({"key": "latest contact", "evidence_any": [f"{cor}~From:", f"{cor}~Status:",
                                             f"{cor}~{em['request_key']}", f"{cor}~replied that"],
                                             "phrases_any": [em["date"]]})
        else:
            e["required_open_items"] += [
                {"key": "requested term", "evidence_any": [f"{cor}~{rel['email']['request_key']}"],
                 "phrases_any": [rel["email"]["term_phrase"]]},
                {"key": "validity deadline", "evidence_any": [f"{prp}~Proposed price"],
                 "phrases_any": [long_date(v["VALID_UNTIL"])]}]
    return e


def load_specs(folder: Path) -> list[dict]:
    return [json.loads(p.read_text(encoding="utf-8")) for p in sorted(folder.glob("*.json"))]
