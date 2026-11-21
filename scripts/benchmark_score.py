"""Phase 4.5 I0-a: deterministic benchmark scorer (no AI judge).

score_scenario(record, expected, products, competitors) -> {metric: [unit, ...]}; each unit is
{"ok": bool, "detail": str}. aggregate() turns units into numerator / denominator, a 95% Wilson interval and the
list of failures. The metric definitions follow docs/PORTFOLIO_RELEASE_PLAN.md §6.1 E3. Where the pilot implements
a rule only partly, METRIC_NOTES says so; nothing is reported as measured that is not.
"""
import json
import math
import re

SCORER_VERSION = "1.1"
# Version history. 1.0 (I0) stays selectable so the original B0-offline and B0-live scores remain reproducible.
SCORER_CHANGES = {
    "1.1": [
        "O6a: a required date phrase also matches the same date written in the other standard order "
        "('14 November 2026' = 'November 14, 2026'); the evidence and item rules are unchanged.",
        "O1: for a cited news item, the publication date in its verified source metadata (the provenance label "
        "given to the drafter) counts as part of the cited passage.",
        "O3b is unchanged (formal conflict disclosures only). New O3b_text takes the genuine contradictions that "
        "were NOT formally disclosed and counts those stated inside one briefing item that cites both sides with "
        "disagreement wording; it is reported separately and never merged into O3b.",
        "O2b: a passage on one side of an expected contradiction is not a distractor when every item citing it "
        "also cites the other side (documenting the disagreement). Cited anywhere on its own, it still is.",
    ],
}
PRODUCTS = ["Nivarque Core", "Engineering Vault", "Records Retention"]
COMPETITORS = ["Solquend"]
STATUS_WORDS = ("in progress", "completed", "open")

METRICS = {
    "R1": "must-reach evidence present in the drafting input",
    "R2": "approved meetings and tasks (with current status) present in the drafting input; drafts absent",
    "R3": "out-of-window, look-alike and passing-mention news kept out of the drafting input",
    "O1": "number consistency only: every number in a fact occurs in its cited passages; no citation-validation "
          "failure (NOT a factual-accuracy score)",
    "O2a": "must-cite evidence cited in the briefing",
    "O2b": "distinct cited evidence that is not a listed distractor",
    "O3a": "compatible statement pairs not disclosed as contradictions",
    "O3b": "genuine contradictions disclosed as contradictions",
    "O3b_text": "genuine contradictions WITHOUT a formal disclosure that are at least stated in briefing text (one item "
                "cites both sides); NOT a disclosure",
    "O3c": "undated historical statements omitted or marked as undated",
    "O4": "checkable disclosure statements that are true",
    "O5a": "official, verbatim passage cited instead of a weaker copy or paraphrase",
    "O5b": "data or quote pages kept out of Recent developments",
    "O6a": "required open items present (follow-up and negotiation)",
    "O6b": "existing terms not presented under Opportunities",
    "O7a": "scenarios where at least 2 of 3 recommendations cite customer-specific evidence",
    "O7b": "recommendations without product or competitor advice outside the scenario's evidence",
    "O8": "safety: synthetic relationship items labelled synthetic; no draft content; no error status",
}
# How completely each rule measures what its name suggests. "full": the rule decides the property exactly, given
# the expected outcomes; "approximation": a proxy that can miss cases or depends on wording or format; "partial":
# checks only one part of the property and must never be reported as the whole.
COVERAGE = {"R1": "full", "R2": "approximation", "R3": "full", "O1": "partial", "O2a": "full", "O2b": "full",
            "O3a": "approximation", "O3b": "approximation", "O3b_text": "approximation", "O3c": "approximation", "O4": "partial",
            "O5a": "full", "O5b": "full", "O6a": "approximation", "O6b": "full", "O7a": "approximation",
            "O7b": "approximation", "O8": "partial"}
METRIC_NOTES = {
    "R2": "Format-independent text search: a task counts as present when its description appears in an approved "
          "meeting record given to the drafter (any field or wording order) and the status word nearest to it is the "
          "task's current status. Unusual layouts can still mislead the nearest-word rule.",
    "O1": "Checks only that numbers and date digits in a fact appear somewhere in its cited passages. It does not "
          "check names, the relation between the numbers, whether the source is authoritative, or whether a "
          "contested figure is presented as established (a fact citing a disputed aggregator figure passes). "
          "Since scorer 1.1 a cited news item's publication date from its source metadata counts as cited. "
          "Factual support needs the manual claim-support audit (M2).",
    "O3a": "Detects contradictions only as conflict disclosures; a contradiction stated inside an item's text is not "
           "seen.",
    "O3b": "Detects contradictions only as conflict disclosures; a contradiction stated inside an item's text is "
           "counted separately by O3b_text (scorer 1.1).",
    "O3b_text": "The item must cite both sides and use disagreement wording; it does not check that neither side is "
                "treated as established.",
    "O3c": "Keyword check ('date not stated', 'undated', 'no date'); other wordings are missed.",
    "O4": "Recognises four statement patterns plus required disclosures; all other disclosure text is not checked.",
    "O6a": "Phrase match on the planted value; since scorer 1.1 a date also matches in 'Month D, YYYY' order. Other "
           "correct wordings (for example 'mid-November') are still missed.",
    "O7a": "Counts recommendations that cite customer evidence; it does not judge whether the advice follows from it.",
    "O7b": "Product and competitor names matched as text.",
    "O8": "Checks the word 'synthetic' on relationship items, absence of draft text and status only; not all safety rules.",
}
# Metrics whose passes can be vacuous are always read together with the metric that shows the missing capability.
RELATED = {"O3a": "read with O3b (contradiction detection)", "O3c": "read with R1 (what reached the drafter)",
           "O6b": "read with R1 and O6a (proposal status and open items)"}
NOT_MEASURED = ("overall factual accuracy of each claim", "relevance and usefulness to the meeting",
                "quality of reasoning and inference", "live AI behaviour (offline template layer only)")
UNDATED_MARKERS = ("date not stated", "undated", "no date")
DISAGREEMENT_WORDS = ("disagree", "differ", "conflict", "contradict", "unresolved", "inconsistent", "discrepan",
                      "whereas", " while ")
MONTHS = ("January", "February", "March", "April", "May", "June", "July", "August", "September", "October",
          "November", "December")
_DMY = re.compile(r"^(\d{1,2}) (" + "|".join(MONTHS) + r") (\d{4})$")
_PUBLISHED = re.compile(r"published (\d{4})-(\d{2})-(\d{2})")


def date_variants(phrase: str) -> list[str]:
    """The same date in the other standard order: '14 November 2026' -> 'November 14, 2026' / 'November 14 2026'."""
    m = _DMY.match(phrase)
    return [f"{m[2]} {int(m[1])}, {m[3]}", f"{m[2]} {int(m[1])} {m[3]}"] if m else []


def published_date_forms(label: str) -> list[str]:
    """The publication date of a 'published YYYY-MM-DD' provenance label, written as a whole date in the usual
    forms ('2026-11-08', '8 November 2026', 'November 8, 2026', 'November 8 2026'). Only a whole date is credited,
    never its parts on their own."""
    m = _PUBLISHED.search(label or "")
    if not m:
        return []
    day, month = int(m[3]), MONTHS[int(m[2]) - 1]
    return [f"{m[1]}-{m[2]}-{m[3]}", f"{day} {month} {m[1]}", f"{month} {day}, {m[1]}", f"{month} {day} {m[1]}"]
_NUM = re.compile(r"\d+(?:[.,]\d+)*")


def _numbers(text: str) -> set[str]:
    return {n.replace(",", "") for n in _NUM.findall(text or "")}


def _items(briefing):
    for section, items in (briefing or {}).items():
        for it in items:
            yield section, it


def _norm(text: str) -> str:
    return " " + " ".join(re.findall(r"[a-z0-9]+", (text or "").casefold())) + " "


def task_present(history_text: str, description: str, status: str) -> bool:
    """Description present (first six words) and the nearest status word to it is the given status."""
    h, probe = _norm(history_text), " ".join(_norm(description).split()[:6])
    pos = h.find(f" {probe} ")
    if pos < 0:
        return False
    found = [(abs(m.start() - pos), w) for w in STATUS_WORDS for m in re.finditer(f" {w} ", h)
             if not (pos <= m.start() < pos + len(probe) + 1)]  # a status word inside the description itself is ignored
    return bool(found) and min(found)[1] == status.casefold()


def score_scenario(record: dict, exp: dict | None = None, products: list[str] = PRODUCTS,
                   competitors: list[str] = COMPETITORS, version: str = SCORER_VERSION) -> dict:
    if version not in ("1.0", "1.1"):
        raise ValueError(f"unknown scorer version {version!r}")
    v11 = version == "1.1"
    exp = exp if exp is not None else record["expected"]
    tok = lambda x: record["tokens"].get(x, x)  # noqa: E731
    group = lambda g: {tok(x) for x in g}  # noqa: E731
    inp = record["drafting_input"] or {}
    items = list(_items(record["briefing"]))
    cited = {e for _, it in items for e in it.get("evidence_ids", [])}
    full = record["full_text"]
    out = {m: [] for m in METRICS if v11 or m != "O3b_text"}

    def unit(metric, ok, detail, vacuous=None):
        """vacuous: a reason string when the unit passed only because the evidence or capability it tests was
        absent (nothing could have gone wrong). Such passes are reported separately, never as capability."""
        u = {"ok": bool(ok), "detail": f"{record['scenario']}: {detail}"}
        if ok and vacuous:
            u["vacuous"] = vacuous
        out[metric].append(u)

    # Retrieval
    for g in exp["must_reach_drafter"]:
        unit("R1", group(g) & set(inp), f"must reach drafter: any of {g}")
    for key in exp["history"]["meetings"]:
        unit("R2", tok(f"HIST:{key}") in inp, f"approved meeting {key} in drafting input")
    history_text = " ".join(json.dumps(v, ensure_ascii=False) for k, v in inp.items() if k.startswith("HIST-"))
    for key in exp["history"]["tasks"]:
        t = record["history"]["tasks"].get(key)
        ok = bool(t) and task_present(history_text, t["description"], t["status"])
        unit("R2", ok, f"task {key} with current status {t['status'] if t else '?'} in drafting input")
    for phrase in exp["history"]["draft_phrases"]:
        unit("R2", not any(phrase in (v.get("excerpt") or "") for v in inp.values()), f"draft phrase {phrase!r} absent")
    for x in exp["must_not_reach_drafter"]:
        unit("R3", tok(x) not in inp, f"{x} kept out of drafting input")

    # Output
    ok_status = record["status"] in ("briefing_ready", "partial_briefing")
    unit("O1", ok_status, f"status {record['status']} (no citation-validation failure)")
    for section, it in items:
        if it["kind"] != "fact":
            continue
        source = " ".join(full.get(e, "") for e in it["evidence_ids"])
        claim = it["text"]
        if v11:  # a cited news item's publication date, written as a whole date, is supported by its metadata
            for e in it["evidence_ids"]:
                if e.startswith("WEB-"):
                    for form in published_date_forms((inp.get(e) or {}).get("provenance_label", "")):
                        claim = claim.replace(form, " ")
        missing = _numbers(claim) - _numbers(source)
        unit("O1", not missing, f"{section} fact numbers supported" + (f"; missing {sorted(missing)}" if missing else ""))
    for g in exp["must_cite"]:
        unit("O2a", group(g) & cited, f"must cite: any of {g}")
    distractors = {tok(x) for x in exp["must_not_cite"]} & cited
    if v11:  # one side of a genuine contradiction, cited only together with the other side
        for a, b in exp["temporal"]["contradictions"]:
            for side, other in ((group(b), group(a)), (group(a), group(b))):
                for e in side & distractors:
                    uses = [it for _, it in items if e in it.get("evidence_ids", [])]
                    if uses and all(other & set(it["evidence_ids"]) for it in uses):
                        distractors.discard(e)
    for e in sorted(cited):
        unit("O2b", e not in distractors, f"cited {e}" + (" (distractor)" if e in distractors else ""))

    conflicts = [d for d in record["disclosures"] if d.get("kind") in ("unresolved_conflict",)]
    any_conflict_handling = [d for d in record["disclosures"]
                             if d.get("kind") in ("unresolved_conflict", "chronological_ambiguity")]
    def covers(d, a, b):
        """Does disclosure d present sides a and b as a conflict? Exact passages when the disclosure lists them;
        otherwise the document IDs named in its text (the older wording named documents, not passages)."""
        ev = set(d.get("evidence_ids") or [])
        if ev:
            return bool(group(a) & ev) and bool(group(b) & ev)
        docs = set(re.findall(r"NVQ-[A-Z]+-[A-Za-z0-9-]+", d.get("text", "")))
        side = lambda s: {x.split("#")[0] for x in group(s)} & docs  # noqa: E731
        return bool(side(a)) and bool(side(b)) and side(a) != side(b)
    for a, b in exp["temporal"]["compatible_pairs"]:
        bad = [d["id"] for d in conflicts if covers(d, a, b)]
        reached = (group(a) & set(inp)) and (group(b) & set(inp))
        why = ("no conflict or ambiguity disclosure of any kind was made, so no pair could be misjudged"
               if not any_conflict_handling else None if reached else "the pair did not both reach the drafter")
        unit("O3a", not bad, f"compatible pair {a[0]} / {b[0]} not called a contradiction" + (f" (got {bad})" if bad else ""),
             vacuous=why)
    for a, b in exp["temporal"]["contradictions"]:
        disclosed = any(covers(d, a, b) for d in conflicts)
        unit("O3b", disclosed, f"contradiction {a[0]} / {b[0]} disclosed as such")
        if v11 and not disclosed:  # only contradictions without a formal disclosure: no overlap with O3b
            stated = any(group(a) & set(it.get("evidence_ids", [])) and group(b) & set(it.get("evidence_ids", []))
                         and any(w in f" {it['text'].casefold()} " for w in DISAGREEMENT_WORDS) for _, it in items)
            unit("O3b_text", stated, f"contradiction {a[0]} / {b[0]} stated in briefing text")
    for x in exp["temporal"]["undated"]:
        uses = [it for _, it in items if tok(x) in it.get("evidence_ids", [])]
        ok = all(any(m in it["text"].casefold() for m in UNDATED_MARKERS) for it in uses)
        unit("O3c", ok, f"undated {x} " + ("omitted" if not uses else "marked undated" if ok else "shown without date note"),
             vacuous=None if uses or tok(x) in inp else "the statement did not reach the drafter")

    synthetic_customer = {e for e in cited if e.startswith("HIST-") or re.match(r"NVQ-(PRP|COR|MTG)-", e)}
    for d in record["disclosures"]:
        text = d.get("text", "")
        if "shown with their dates" in text:
            unit("O4", len(re.findall(r"\b(1[89]|20)\d{2}\b", text)) >= 2, f"{d['id']}: 'shown with their dates' holds")
        if "No prior relationship records" in text:
            unit("O4", not synthetic_customer, f"{d['id']}: 'no prior relationship records' holds")
        if "news was not searched" in text:
            unit("O4", not any(e.startswith("WEB-") for e in inp), f"{d['id']}: 'news was not searched' holds")
        if "neither is treated as established" in text:
            ev = set(d.get("evidence_ids") or [])
            facts = {e for _, it in items if it["kind"] == "fact" for e in it["evidence_ids"]}
            unit("O4", not (ev & facts), f"{d['id']}: 'neither is treated as established' holds")
    for need in exp["required_disclosures"]:
        unit("O4", any(need["contains"] in d.get("text", "") for d in record["disclosures"]),
             f"required disclosure containing {need['contains']!r} present")

    for a in exp["authority"]:
        pref, weak = group(a["preferred"]), group(a["weaker"])
        if (pref | weak) & cited:
            unit("O5a", bool(pref & cited) and not (weak & cited),
                 f"preferred {a['preferred']} {'cited' if pref & cited else 'NOT cited'}; "
                 f"weaker cited: {sorted(weak & cited) or 'none'}")
    for x in exp["data_pages"]:
        bad = any(tok(x) in it.get("evidence_ids", []) for s, it in items if s == "recent_developments")
        unit("O5b", not bad, f"data page {x} " + ("shown in Recent developments" if bad else "kept out"))

    for need in exp["required_open_items"]:
        phrases = list(need["phrases_any"]) + ([d for p in need["phrases_any"] for d in date_variants(p)] if v11 else [])
        ok = any(group(need["evidence_any"]) & set(it.get("evidence_ids", []))
                 and any(p in it["text"] for p in phrases) for _, it in items)
        unit("O6a", ok, f"open item: {need['key']}")
    customer_opportunity = any(e.startswith("HIST-") or re.match(r"NVQ-(PRP|COR|MTG)-", e)
                               for s, it in items if s == "opportunities" for e in it.get("evidence_ids", []))
    for x in exp["existing_terms"]:
        bad = any(tok(x) in it.get("evidence_ids", []) for s, it in items if s == "opportunities")
        unit("O6b", not bad, f"existing terms {x} " + ("shown under Opportunities" if bad else "not shown as opportunity"),
             vacuous=None if customer_opportunity else "no customer-specific opportunity was produced at all")

    recs = [it for _, it in items if it["kind"] == "recommendation"]
    custom = lambda e: any(e == tok(p) or e.startswith(tok(p)) for p in exp["customer_evidence"])  # noqa: E731
    grounded = [r for r in recs if any(custom(e) for e in r.get("evidence_ids", []))]
    unit("O7a", recs and len(grounded) * 3 >= 2 * len(recs), f"{len(grounded)} of {len(recs)} recommendations cite customer evidence")
    for r in recs:
        low = r["text"].casefold()
        off = [p for p in products if p.casefold() in low and p not in exp["allowed_products"]]
        off += [c for c in competitors if c.casefold() in low and c not in exp["allowed_competitors"]]
        unit("O7b", not off, f"recommendation '{r['text'][:60]}…'" + (f" mentions {off}" if off else ""))

    for section, it in items:
        if it.get("claim_type") in ("relationship", "meeting_history"):
            unit("O8", "synthetic" in it["text"].casefold(), f"{section} synthetic item labelled")
    for phrase in exp["history"]["draft_phrases"]:
        unit("O8", not any(phrase in it["text"] for _, it in items), f"draft phrase {phrase!r} not in briefing")
    unit("O8", ok_status, f"no error status ({record['status']})")
    return out


def wilson(k: int, n: int, z: float = 1.96) -> tuple[float, float] | None:
    if n == 0:
        return None
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return round(max(0.0, c - h), 3), round(min(1.0, c + h), 3)


def aggregate(per_scenario: list[dict]) -> dict:
    out = {}
    for m in [m for m in METRICS if not per_scenario or m in per_scenario[0]]:  # scorer 1.0 has no O3b_text
        units = [u for s in per_scenario for u in s[m]]
        k, n = sum(u["ok"] for u in units), len(units)
        vac = [u for u in units if u.get("vacuous")]
        out[m] = {"description": METRICS[m], "coverage": COVERAGE[m], "passed": k, "applicable": n,
                  "vacuous_passes": len(vac), "substantive_passes": k - len(vac),
                  "related": RELATED.get(m, ""), "wilson95": wilson(k, n),
                  "failures": [u["detail"] for u in units if not u["ok"]],
                  "vacuous": [f"{u['detail']} — {u['vacuous']}" for u in vac], "note": METRIC_NOTES.get(m, "")}
    return out
