"""Mandatory external news research: Tavily, 48-hour window with 30-day fallback (Prompt 03).

Deterministic orchestration, no LLM. Rules enforced in code:
- Only a public company name (plus the word "news") is ever sent to the provider. Internal or
  synthetic content cannot reach the query (P3-4); queries are checked before sending.
- Credits are reserved BEFORE each attempt; a request over the per-briefing or per-day cap is
  refused, never sent (P3-2). Every attempt, including retries, counts.
- At most one retry, only on HTTP 429 (honouring Retry-After) or a network error/timeout (P3-1).
- Publication date (provider estimate, or "unknown") is kept separate from retrieval time.
  Undated results are never classified as recent (P3-3).
- Results about a look-alike organization are excluded; ambiguous company names stop before
  any search and ask for clarification.
The HTTP transport is injected. Tests use simulated responses; no live call happens here.
"""
import hashlib
import json
import re
import time
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from urllib.parse import parse_qs, urlparse

from deal_prep.evidence_profile import is_data_page
from deal_prep.kb_index import _norm, resolve_company
from deal_prep.provenance import MAX_EXCERPT_WORDS, load_registry

TAVILY_URL = "https://api.tavily.com/search"
ALLOWED_PAYLOAD_KEYS = {"query", "topic", "search_depth", "max_results", "start_date", "end_date",
                        "time_range", "include_raw_content", "filter_by_published_date"}
NOT_FOUND_MESSAGE = ("No relevant news was found in the searched sources for this window. "
                     "This is not proof that no news exists.")


@dataclass
class SearchConfig:
    credits_per_briefing: int = 5
    credits_per_day: int = 50
    timeout_seconds: float = 15.0
    max_retries: int = 1
    max_results: int = 10
    recent_hours: int = 48
    fallback_days: int = 30


class BudgetExceeded(RuntimeError):
    pass


class UnsafeQuery(ValueError):
    pass


class TransportError(RuntimeError):
    """status None means a network error or timeout."""

    def __init__(self, status=None, retry_after=None, message=""):
        super().__init__(message or f"transport error (status={status})")
        self.status, self.retry_after = status, retry_after


class NewsDisabled(TransportError):
    """News search deliberately not attempted (live news is off). Not a failure; any caller that only
    knows TransportError still treats it as "no news"."""


@dataclass
class Budget:
    """Credit ledger. A day ledger can be shared across briefings; reset per briefing."""
    config: SearchConfig
    used_today: dict = field(default_factory=dict)
    used_this_briefing: int = 0

    def reserve(self, credits: int, today: date) -> None:
        day_used = self.used_today.get(today, 0)
        if self.used_this_briefing + credits > self.config.credits_per_briefing:
            raise BudgetExceeded(f"per-briefing cap of {self.config.credits_per_briefing} credits reached")
        if day_used + credits > self.config.credits_per_day:
            raise BudgetExceeded(f"per-day cap of {self.config.credits_per_day} credits reached")
        self.used_this_briefing += credits
        self.used_today[today] = day_used + credits

    def new_briefing(self) -> None:
        self.used_this_briefing = 0


class PersistentBudget(Budget):
    """Budget whose per-day credit count survives restarts (JSON ledger, keyed by ISO date).

    The ledger is re-read before every reservation and written immediately after, so the
    per-day cap also holds across app restarts and separate scripts.
    """

    def __init__(self, config: SearchConfig, ledger_path):
        super().__init__(config)
        self.ledger_path = ledger_path

    def _read(self) -> dict:
        try:
            return json.loads(self.ledger_path.read_text(encoding="utf-8"))
        except (FileNotFoundError, json.JSONDecodeError):
            return {}

    def reserve(self, credits: int, today: date) -> None:
        ledger = self._read()
        self.used_today = {today: ledger.get(today.isoformat(), 0)}
        super().reserve(credits, today)  # raises before anything is written if a cap would be exceeded
        ledger[today.isoformat()] = self.used_today[today]
        self.ledger_path.parent.mkdir(parents=True, exist_ok=True)
        self.ledger_path.write_text(json.dumps(ledger, indent=1), encoding="utf-8")


@dataclass
class CompanyIdentity:
    name: str
    org_id: str | None = None
    aliases: tuple = ()
    domain: str | None = None
    country: str | None = None
    lookalikes: tuple = ()
    lookalike_domains: tuple = ()
    confidence: str = "name_only"


def identify_company(name: str, domain: str | None = None, registry: dict | None = None) -> dict:
    """Return {"status": resolved|unregistered|clarification_required, "identity", "candidates"}.

    A registry match gives a grounded identity (domain, aliases, known look-alikes). An unknown
    name is allowed (FR-11) but marked name_only. An ambiguous name stops before any search.
    """
    registry = load_registry() if registry is None else registry
    r = resolve_company(name, domain=domain, registry=registry)
    if r["status"] == "ambiguous":
        return {"status": "clarification_required", "identity": None, "candidates": r["candidates"]}
    if r["status"] == "unresolved":
        return {"status": "unregistered", "candidates": [],
                "identity": CompanyIdentity(name=name.strip(), domain=domain, confidence="name_only")}
    org = registry[r["org_id"]]
    first = _norm(org["name"]).split()[0]
    others = [o for oid, o in registry.items()
              if oid != r["org_id"] and o["reality"] == "real" and _norm(o["name"]).split()[0] == first]
    return {"status": "resolved", "candidates": [r["org_id"]], "identity": CompanyIdentity(
        name=org["name"], org_id=r["org_id"], aliases=tuple(org.get("aliases", [])),
        domain=org["official_domain"], country=org["country"],
        lookalikes=tuple(o["name"] for o in others),
        lookalike_domains=tuple(o["official_domain"] for o in others if o.get("official_domain")),
        confidence="registry")}


def build_query(identity: CompanyIdentity, registry: dict | None = None) -> str:
    query = f"{identity.name} news"
    assert_query_safe(query, registry)
    return query


def assert_query_safe(query: str, registry: dict | None = None) -> None:
    """P3-4: refuse anything that looks like internal or synthetic content."""
    registry = load_registry() if registry is None else registry
    if len(query) > 120 or "\n" in query:
        raise UnsafeQuery("query too long or multi-line; only a company name and 'news' are allowed")
    if re.search(r"\b(NVQ|DMS)-[A-Z0-9]", query) or "SYNTHETIC" in query.upper():
        raise UnsafeQuery("query contains an internal document ID or synthetic marker")
    lowered = query.casefold()
    for org in registry.values():
        if org["reality"] == "fictional":
            for n in [org["name"], *org.get("aliases", [])]:
                if n.casefold() in lowered:
                    raise UnsafeQuery(f"query mentions fictional organization {n!r}")


class TavilyClient:
    """Thin client. `post(url, json, headers, timeout)` must return a dict or raise TransportError."""

    def __init__(self, api_key: str, post=None, config: SearchConfig | None = None, sleep=time.sleep):
        if not api_key:
            raise ValueError("an API key must be passed explicitly; this module never reads .env")
        self._key, self._post = api_key, post or _httpx_post
        self.config, self._sleep = config or SearchConfig(), sleep

    def search(self, payload: dict, budget: Budget, today: date, trace: list) -> dict:
        unknown = set(payload) - ALLOWED_PAYLOAD_KEYS
        if unknown:
            raise UnsafeQuery(f"payload keys not allowed: {sorted(unknown)}")
        assert_query_safe(payload["query"])
        attempts = 0
        while True:
            budget.reserve(1, today)  # raises BudgetExceeded before anything is sent
            attempts += 1
            started = time.monotonic()
            try:
                response = self._post(TAVILY_URL, json=payload,
                                      headers={"Authorization": f"Bearer {self._key}"},
                                      timeout=self.config.timeout_seconds)
                trace.append(_trace(payload, "ok", started, len(response.get("results", [])), attempts))
                return response
            except TransportError as e:
                retryable = e.status in (None, 429)
                trace.append(_trace(payload, f"error status={e.status}", started, 0, attempts))
                if not retryable or attempts > self.config.max_retries:
                    raise
                if e.status == 429 and e.retry_after:
                    self._sleep(float(e.retry_after))


def _httpx_post(url, json, headers, timeout):  # pragma: no cover - live path, Prompt 03 step 7
    import httpx
    try:
        r = httpx.post(url, json=json, headers=headers, timeout=timeout)
    except httpx.HTTPError as e:
        raise TransportError(None, message=str(e)) from e
    if r.status_code != 200:
        raise TransportError(r.status_code, r.headers.get("Retry-After"))
    return r.json()


def _trace(payload, outcome, started, n_results, attempt):
    window = payload.get("time_range") or f"{payload.get('start_date')}..{payload.get('end_date')}"
    return {"service": "tavily", "query": payload["query"], "window": window, "outcome": outcome,
            "results": n_results, "attempt": attempt, "credits": 1,
            "elapsed_ms": round((time.monotonic() - started) * 1000)}


# --- dates, windows, entity matching ------------------------------------------------

def parse_published(value) -> datetime | None:
    if not value:
        return None
    try:
        dt = parsedate_to_datetime(value)
    except (TypeError, ValueError):
        try:
            dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        except ValueError:
            return None
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def classify_window(published: datetime | None, now: datetime, config: SearchConfig) -> str:
    if published is None:
        return "undated"
    if published > now + timedelta(hours=1):
        return "undated"  # a future date is not a usable publication date
    age = now - published
    if age <= timedelta(hours=config.recent_hours):
        return "last_48h"
    if age <= timedelta(days=config.fallback_days):
        return "last_30_days"
    return "older"


def original_url(url: str) -> str | None:
    """Return the original article URL. A Google redirect link is unwrapped when it carries the
    real address in `url=` or `q=`; an opaque redirect returns None (original source unknown).
    Seen live on 2026-11-06: Tavily news results with google.com/url?q=<opaque token>."""
    parsed = urlparse(url)
    host = (parsed.hostname or "").removeprefix("www.")
    if host != "google.com" and not host.endswith(".google.com"):
        return url
    if parsed.path == "/url":
        params = parse_qs(parsed.query)
        for name in ("url", "q"):
            for value in params.get(name, []):
                if value.startswith(("https://", "http://")) and original_url(value) == value:
                    return value
    return None  # any other Google link (e.g. news.google.com/rss/articles/...) hides the source


QUALIFYING_MATCHES = {"official_source", "headline", "repeated_mention"}


def _mentions_lookalike(text: str, lookalike: str, target_names: list[str]) -> bool:
    """Whole-word look-alike mention, ignoring occurrences that are part of the target's own,
    longer name (target "ARUP Laboratories", look-alike "Arup": "arup laboratories" is masked)."""
    for name in target_names:
        if lookalike in name and len(name) > len(lookalike):
            text = re.sub(rf"\b{re.escape(name)}\b", " ", text)
    return re.search(rf"\b{re.escape(lookalike)}\b", text) is not None


def entity_match(result: dict, identity: CompanyIdentity) -> str:
    """Decide whether a result is about the target company, in this order:
    official_source  - URL on the company's verified official domain (qualifies)
    lookalike        - a look-alike organization is named anywhere (rejected; strict separation)
    headline         - the company name or an alias is in the headline (qualifies)
    repeated_mention - named at least twice in the snippet, not in the headline (qualifies)
    passing_mention  - named exactly once, outside the headline (rejected)
    uncertain        - not named at all (rejected)
    """
    host = (urlparse(result.get("url", "")).hostname or "").removeprefix("www.")

    def on(domain):
        return bool(domain) and (host == domain or host.endswith("." + domain))

    if on(identity.domain):
        return "official_source"
    if any(on(d) for d in identity.lookalike_domains):
        return "lookalike"  # hosted on a look-alike organization's own site
    title, content = result.get("title", "").casefold(), result.get("content", "").casefold()
    names = [n.casefold() for n in [identity.name, *identity.aliases]]
    patterns = [rf"\b{re.escape(n)}\b" for n in names]
    if any(_mentions_lookalike(f"{title} {content}", la.casefold(), names) for la in identity.lookalikes):
        return "lookalike"
    if any(re.search(p, title) for p in patterns):
        return "headline"
    mentions = len({m.start() for p in patterns for m in re.finditer(p, content)})
    if mentions >= 2:
        return "repeated_mention"
    return "passing_mention" if mentions == 1 else "uncertain"


def _excerpt(text: str) -> str:
    from deal_prep import company_context
    if company_context.ENABLED:  # I7: bounded, but whole sentences, the most factual first; omissions marked "…"
        return company_context.bounded_excerpt(company_context.split_dateline(text)[1], MAX_EXCERPT_WORDS)
    words = (text or "").split()
    return " ".join(words[:MAX_EXCERPT_WORDS])


def _dateline(text: str) -> dict:
    """I7: a release's leading place-and-date line, kept as its own short field (it is the item's own text)."""
    from deal_prep import company_context
    line = company_context.split_dateline(text)[0] if company_context.ENABLED else ""
    return {"dateline": line} if line else {}


def to_evidence(result: dict, identity: CompanyIdentity, window: str, match: str,
                retrieved_at: datetime, from_fallback: bool) -> dict:
    published = parse_published(result.get("published_date"))
    host = (urlparse(result["url"]).hostname or "").removeprefix("www.")
    own = match == "official_source"
    pub_text = published.isoformat() if published and window != "undated" else "unknown"
    limitations = []
    if pub_text != "unknown":
        limitations.append("publication date is the provider's estimate and may be a last-updated date")
    else:
        limitations.append("no usable publication date; never treated as recent")
    if own:
        limitations.append("company's own published claim, not independently verified")
    if result.get("redirect_url"):
        limitations.append("original URL recovered from a redirect link returned by the provider")
    label_window = {"last_48h": "last 48 hours", "last_30_days": "last 30 days (older context)",
                    "undated": "undated"}[window]
    return {
        "evidence_id": "WEB-" + hashlib.sha1(result["url"].encode()).hexdigest()[:12],
        "info_origin": "public_source", "creation_method": "live_web_retrieval",
        "organizations": [{"org_id": identity.org_id, "name": identity.name, "role": "subject", "reality": "real"}],
        "source_url": result["url"], "title": result.get("title", ""), "publisher": host,
        "publication_date": pub_text,
        "publication_date_basis": "provider_estimated" if pub_text != "unknown" else "unknown",
        "retrieved_at": retrieved_at.isoformat(), "time_window": window, "from_fallback": from_fallback,
        "entity_match": match, "source_kind": "company_own" if own else "third_party",
        "verification_status": "primary" if own else "single_secondary",
        "relevance_score": result.get("score"), "excerpt": _excerpt(result.get("content", "")),
        **_dateline(result.get("content", "")),
        "limitations": limitations,
        "provenance_label": (f"PUBLIC SOURCE · {host} · {result['url']} · published {pub_text} · "
                             f"retrieved {retrieved_at.date().isoformat()} · window {label_window}"),
    }


def _reason(e: TransportError) -> str:
    """Plain-language reason for a failed news request (no internal codes)."""
    if e.status is None:
        custom = str(e)
        return custom if custom and not custom.startswith("transport error") else "network error or timeout"
    if e.status == 429:
        return "the news service is rate-limiting requests"
    return f"the news service returned an error (HTTP {e.status})"


# --- orchestration ----------------------------------------------------------------

def research_company_news(identity: CompanyIdentity, client: TavilyClient, budget: Budget,
                          now: datetime | None = None) -> dict:
    """Mandatory 48-hour search; 30-day fallback only if no relevant 48-hour result exists."""
    now = now or datetime.now(timezone.utc)
    cfg, trace = client.config, []
    query = build_query(identity)
    base = {"query": query, "topic": "news", "search_depth": "basic", "max_results": cfg.max_results,
            "include_raw_content": False, "filter_by_published_date": False}
    excluded = {"lookalike": 0, "passing_mention": 0, "uncertain": 0, "older": 0, "duplicate": 0,
                "unresolved_redirect": 0, "data_page": 0}
    evidence, seen = [], set()

    def collect(response, from_fallback, wanted):
        for r in response.get("results", []):
            if r.get("url"):
                source = original_url(r["url"])
                if source is None:
                    excluded["unresolved_redirect"] += 1
                    continue
                if source != r["url"]:
                    r = {**r, "url": source, "redirect_url": r["url"]}
            if not r.get("url") or r["url"] in seen:
                excluded["duplicate"] += 1
                continue
            match = entity_match(r, identity)
            if match not in QUALIFYING_MATCHES:
                excluded[match] += 1
                continue
            if is_data_page(r.get("title", ""), r["url"], r.get("content", ""),  # I2: a quote page is not news
                            undated=parse_published(r.get("published_date")) is None):
                excluded["data_page"] += 1
                seen.add(r["url"])
                continue
            window = classify_window(parse_published(r.get("published_date")), now, cfg)
            if window == "older" or (window not in wanted and window != "undated"):
                excluded["older"] += 1
                continue
            seen.add(r["url"])  # only kept results count as seen, so the fallback can still use older ones
            evidence.append(to_evidence(r, identity, window, match, now, from_fallback))

    def result(status, window_used, message=""):
        return {"status": status, "window_used": window_used, "query": query, "evidence": evidence,
                "recent_count": sum(e["time_window"] == "last_48h" for e in evidence),
                "excluded": excluded, "trace": trace, "credits_used": budget.used_this_briefing,
                "retrieved_at": now.isoformat(), "message": message}

    recent_payload = {**base, "start_date": (now - timedelta(days=2)).date().isoformat(),
                      "end_date": now.date().isoformat()}
    try:
        collect(client.search(recent_payload, budget, now.date(), trace), False, {"last_48h"})
    except BudgetExceeded as e:
        return result("budget_exhausted", None, str(e))
    except NewsDisabled as e:  # must precede TransportError: a skipped search is not a failed one
        return result("disabled", None, f"News was not searched: {e}.")
    except TransportError as e:
        return result("provider_error", None, f"News search failed: {_reason(e)}. Results are incomplete.")
    if any(e["time_window"] == "last_48h" for e in evidence):
        return result("found_48h", "last_48h")

    fallback_payload = {**base, "start_date": (now - timedelta(days=cfg.fallback_days)).date().isoformat(),
                        "end_date": now.date().isoformat()}
    try:
        collect(client.search(fallback_payload, budget, now.date(), trace), True, {"last_30_days"})
    except BudgetExceeded as e:
        return result("budget_exhausted", "last_48h", f"No relevant 48-hour news; fallback not run: {e}")
    except TransportError as e:
        return result("provider_error", "last_48h", f"The 30-day news search failed: {_reason(e)}. "
                                                    "Results are incomplete.")
    if any(e["time_window"] == "last_30_days" for e in evidence):
        return result("fallback_30d_found", "last_30_days",
                      "No relevant news in the last 48 hours; showing older context from the last 30 days.")
    return result("not_found", "last_30_days", NOT_FOUND_MESSAGE)
