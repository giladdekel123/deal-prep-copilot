"""Organization registry and deterministic provenance validator (spec v1.2 §6B).

Reality (real/fictional) is recorded per organization in the registry only.
Origin (public_source/synthetic_record) and creation_method are recorded per document.
Validation returns a list of error strings; an empty list means valid. Indexing
(Gate 2B step 7) must call assert_valid and refuse anything that fails.
"""
import json
import re
from datetime import date
from pathlib import Path

from deal_prep import config

KB_DIR = config.PROJECT_ROOT / "data" / "kb_v1"
REGISTRY_PATH = KB_DIR / "organizations.json"

REALITIES = {"real", "fictional"}
ROLES = {"vendor", "customer", "competitor", "subject"}
CREATION_METHODS = {
    "public_source": {"curated_snapshot", "live_web_retrieval"},
    "synthetic_record": {"authored_fixture", "generated_fixture",
                         "user_entered_demo", "ai_proposed_from_user_notes"},
}
SYNTHETIC_CATEGORIES = {"meeting_history", "proposal", "price",
                        "customer_relationship", "correspondence"}
VERIFICATION_STATUSES = {"primary", "corroborated", "single_secondary", "unverified"}
MAX_EXCERPT_WORDS = 50
SYNTHETIC_BANNER = ("SYNTHETIC RECORD — fictional relationship with a real company. "
                    "Not a real business fact.")
DOC_ID = re.compile(r"^NVQ-(PRD|PRC|POL|CMP|PRP|COR|MTG|PUB)-[A-Za-z0-9-]+$")


class ProvenanceError(ValueError):
    pass


# --- registry ---------------------------------------------------------------

def load_registry(path: Path = REGISTRY_PATH) -> dict[str, dict]:
    with open(path, encoding="utf-8") as f:
        orgs = json.load(f)["organizations"]
    return {o["org_id"]: o for o in orgs}


def validate_registry(orgs: list[dict]) -> list[str]:
    errors = []
    ids = [o.get("org_id") for o in orgs]
    for dup in {i for i in ids if ids.count(i) > 1}:
        errors.append(f"registry: duplicate org_id {dup!r}")
    for o in orgs:
        oid = o.get("org_id")
        if o.get("reality") not in REALITIES:
            errors.append(f"registry {oid}: reality must be one of {sorted(REALITIES)}")
        if not o.get("name"):
            errors.append(f"registry {oid}: missing name")
        sources = o.get("identity_sources") or []
        if o.get("reality") == "real":
            if not o.get("official_domain"):
                errors.append(f"registry {oid}: real organization needs official_domain")
            if not sources or not all(_is_https(u) for u in sources):
                errors.append(f"registry {oid}: real organization needs https identity_sources")
        if o.get("reality") == "fictional":
            if sources or o.get("official_domain"):
                errors.append(f"registry {oid}: fictional organization must not cite identity sources or a domain")
            if o.get("public_only"):
                errors.append(f"registry {oid}: fictional organization cannot be public_only")
    return errors


# --- documents --------------------------------------------------------------

def validate_document(doc: dict, text: str, registry: dict[str, dict]) -> list[str]:
    did = doc.get("document_id", "<missing id>")
    errors = []

    def err(msg):
        errors.append(f"{did}: {msg}")

    if not DOC_ID.match(str(doc.get("document_id", ""))):
        err("document_id must match NVQ-<TYPE>-<id> (DMS-* is reserved for the frozen Prompt 01 baseline)")

    origin = doc.get("info_origin")
    if origin not in CREATION_METHODS:
        err(f"info_origin must be one of {sorted(CREATION_METHODS)}, got {origin!r}")
        return errors
    if doc.get("creation_method") not in CREATION_METHODS[origin]:
        err(f"creation_method {doc.get('creation_method')!r} not allowed for {origin}")

    is_pub_type = str(doc.get("document_id", "")).startswith("NVQ-PUB-")
    if is_pub_type != (origin == "public_source"):
        err("PUB documents must be public_source, and only PUB documents may be public_source")

    orgs = doc.get("organizations") or []
    if not orgs:
        err("organizations must list at least one {org_id, role}")
    resolved = []
    for ref in orgs:
        org = registry.get(ref.get("org_id"))
        if org is None:
            err(f"unknown org_id {ref.get('org_id')!r}")
            continue
        if ref.get("role") not in ROLES:
            err(f"invalid role {ref.get('role')!r} for {ref['org_id']}")
        resolved.append(org)

    if origin == "public_source":
        errors.extend(f"{did}: {m}" for m in _public_errors(doc, text, resolved, registry))
    else:
        errors.extend(f"{did}: {m}" for m in _synthetic_errors(doc, text, resolved))
    return errors


def _public_errors(doc, text, resolved, registry):
    errors = []
    for org in resolved:
        if org["reality"] == "fictional":
            errors.append(f"public_source references fictional organization {org['org_id']!r}")
    lowered = text.lower()
    for org in registry.values():
        if org["reality"] == "fictional":
            for name in [org["name"], *org.get("aliases", [])]:
                if name.lower() in lowered:
                    errors.append(f"public_source text mentions fictional organization {name!r}")

    if not _is_https(doc.get("source_url")):
        errors.append("source_url must be an https URL")
    if not doc.get("publisher"):
        errors.append("publisher is required")
    pub = doc.get("publication_date")
    if pub != "unknown" and not _is_iso_date(pub):
        errors.append("publication_date must be an ISO date or 'unknown' (never the retrieval date by default)")
    if not _is_iso_date(doc.get("retrieved_at")):
        errors.append("retrieved_at must be an ISO date")
    if doc.get("verification_status") not in VERIFICATION_STATUSES:
        errors.append(f"verification_status must be one of {sorted(VERIFICATION_STATUSES)}")

    excerpts = doc.get("excerpts") or []
    if not excerpts:
        errors.append("at least one supporting excerpt is required")
    excerpt_ids = set()
    for ex in excerpts:
        excerpt_ids.add(ex.get("excerpt_id"))
        if not ex.get("text"):
            errors.append(f"excerpt {ex.get('excerpt_id')!r} is empty")
        elif len(ex["text"].split()) > MAX_EXCERPT_WORDS:
            errors.append(f"excerpt {ex.get('excerpt_id')!r} exceeds {MAX_EXCERPT_WORDS} words")
    claims = doc.get("claims") or []
    if not claims:
        errors.append("at least one claim is required")
    for claim in claims:
        if claim.get("excerpt_id") not in excerpt_ids:
            errors.append(f"claim {claim.get('text', '')[:40]!r} is not linked to a stored excerpt")
    return errors


def _synthetic_errors(doc, text, resolved):
    errors = []
    for org in resolved:
        if org.get("public_only"):
            errors.append(f"synthetic_record references public-only organization {org['org_id']!r}")
    if any(org["reality"] == "real" for org in resolved):
        if doc.get("synthetic_relationship") is not True:
            errors.append("synthetic record about a real organization needs synthetic_relationship: true")
        cats = doc.get("synthetic_categories") or []
        if not cats or not set(cats) <= SYNTHETIC_CATEGORIES:
            errors.append(f"synthetic_categories must be a non-empty subset of {sorted(SYNTHETIC_CATEGORIES)}")
        if SYNTHETIC_BANNER not in text:
            errors.append("synthetic record about a real organization is missing the mandatory banner")
    return errors


def assert_valid(doc: dict, text: str, registry: dict[str, dict]) -> None:
    errors = validate_document(doc, text, registry)
    if errors:
        raise ProvenanceError("; ".join(errors))


def _is_https(url) -> bool:
    return isinstance(url, str) and url.startswith("https://") and len(url) > len("https://")


def _is_iso_date(value) -> bool:
    try:
        date.fromisoformat(value)
        return True
    except (TypeError, ValueError):
        return False
