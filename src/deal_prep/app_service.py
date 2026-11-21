"""UI-independent service behind the Streamlit page (Prompt 05; standing rules 6 and 9).

Explicit-submit semantics: a briefing runs only when `get` is called for a request that is not
already cached. Streamlit reruns, language changes and downloads reuse the cached result and the
cached PDFs, so they can never trigger new research or model calls.

A saved demonstration briefing can be loaded from data/demo/. It keeps its original creation date,
is labelled SIMULATED everywhere, and never triggers research.
"""
import copy
import functools
import json
import os
from pathlib import Path

from deal_prep import config, demo
from deal_prep.public_demo import SAVED_DEMO_PATH, load_saved_demo, require_not_public  # noqa: F401
from deal_prep.index import _client
from deal_prep.kb_index import KB_COLLECTION, build_kb_index, load_kb_chunks
from deal_prep.pdf_export import build_pdf
from deal_prep.pipeline import prepare_briefing
from deal_prep.history import DB_PATH as HISTORY_DB_PATH
from deal_prep.history import HistoryStore
from deal_prep.history_index import company_history, reconcile, sync_meeting
from deal_prep.notes import propose_structure
from deal_prep.web_research import Budget, PersistentBudget, SearchConfig, identify_company

MODES = {"offline_demo": "Offline demo (internal knowledge base only; live news off; template drafting)",
         "live_ai": "Live AI drafting (OpenAI gpt-6.1-terra, agent gpt-6-luna; live news off; "
                    "max $0.10 per briefing, $1 per day)",
         "live_ai_news": "Live AI + live news (OpenAI as above; Tavily news, max 5 credits per briefing, "
                         "50 per day)"}
LIVE_RUN_CAP_USD, LIVE_DAILY_CAP_USD = 0.10, 1.00
TAVILY_LEDGER_PATH = config.PROJECT_ROOT / "runs" / "tavily_credit_ledger.json"


def tavily_available() -> bool:
    from deal_prep.public_demo import enabled
    if enabled():
        return False
    from deal_prep.llm import _load_env
    _load_env()
    return bool(os.environ.get("TAVILY_API_KEY"))


def load_tavily_client(search_config: SearchConfig):
    """Real Tavily client from TAVILY_API_KEY in .env or the environment (never echoed)."""
    from deal_prep.public_demo import require_not_public
    require_not_public("Tavily")
    from deal_prep.llm import _load_env
    from deal_prep.web_research import TavilyClient
    _load_env()
    key = os.environ.get("TAVILY_API_KEY", "")
    if not key:
        raise RuntimeError("TAVILY_API_KEY is not set in .env or the environment")
    return TavilyClient(key, config=search_config)


def live_news_config() -> SearchConfig:
    """Owner-approved limits (P3-2); no automatic retry of a failed news request."""
    return SearchConfig(credits_per_briefing=5, credits_per_day=50, max_retries=0)


def available_modes() -> dict:
    from deal_prep.llm import openai_available
    has_openai = openai_available()
    has_news = has_openai and tavily_available()
    return {k: v for k, v in MODES.items()
            if k == "offline_demo" or (k == "live_ai" and has_openai) or (k == "live_ai_news" and has_news)}
DEMO_COMPANIES = {"Shikun & Binui": None, "Ashtrom Group": None, "Arup": "arup.com"}  # name -> domain
SAVED_MODE_LABEL = "SIMULATED saved demonstration (offline template output; not newly researched)"


@functools.cache
def kb_passage_count() -> int:
    """Passages a complete dms_kb_v1 index holds (the corpus is fixed and versioned; counted once per process)."""
    return len(load_kb_chunks())


def request_key(company: str, domain: str | None, purpose: str, mode: str) -> tuple:
    return (" ".join(company.casefold().split()), (domain or "").strip().casefold(), purpose, mode)


class BriefingService:
    def __init__(self, chroma_dir: Path | None = None, history_path: Path | None = None):
        require_not_public("The full briefing service (history database, research and drafting)")
        env_chroma = os.environ.get("DEAL_PREP_APP_CHROMA_DIR")
        self.chroma_dir = Path(chroma_dir or env_chroma or config.CHROMA_DIR)
        if history_path is None:  # an explicit/test index directory keeps its history database beside it
            explicit = chroma_dir or env_chroma
            history_path = os.environ.get("DEAL_PREP_HISTORY_DB") or (
                Path(explicit) / "history.sqlite" if explicit else HISTORY_DB_PATH)
        self.store = HistoryStore(history_path)
        self.cache, self.pdf_cache, self.runs = {}, {}, 0

    # --- Stage 2: companies, meeting notes, tasks (SQLite is authoritative; index re-synced after writes) ---

    def company_id_for(self, company: str, domain: str | None = None) -> str | None:
        ident = identify_company(company, domain=domain or None)
        if ident["status"] == "clarification_required":
            return None
        return self.store.get_or_create_company(ident["identity"].name, ident["identity"].org_id)

    def history_search(self, company_id: str):
        """I1: approved meeting records of this company straight from SQLite, newest first (not a semantic top-k).
        The Chroma history index is still kept in sync for search by meaning, but it no longer decides inclusion."""
        def search(identity: dict) -> list[dict]:
            return company_history(self.store, company_id)
        return search

    def add_meeting_draft(self, company_id: str, notes: str, op_id: str, meeting_date: str | None = None) -> str:
        return self.store.create_meeting_draft(company_id, notes, propose_structure(notes), op_id, meeting_date)

    def approve_meeting(self, meeting_id: str, approved: dict, tasks: list[dict] = ()) -> list[str]:
        """Explicit approval; create the confirmed tasks (each with its own operation ID); then re-sync the index."""
        self.store.approve_meeting(meeting_id, approved)
        company_id = self.store.meeting(meeting_id)["company_id"]
        task_ids = [self.store.create_task(company_id, t["description"], t["op_id"], meeting_id=meeting_id,
                                           due_date=t.get("due_date"), due_raw=t.get("due_raw")) for t in tasks]
        sync_meeting(self.store, meeting_id, self.chroma_dir)
        return task_ids

    def add_task(self, company_id: str, description: str, op_id: str, due_date: str | None = None) -> str:
        return self.store.create_task(company_id, description, op_id, due_date=due_date)

    def set_task_status(self, task_id: str, status: str) -> None:
        self.store.set_task_status(task_id, status)
        meeting_id = next(t["meeting_id"] for t in self.store.tasks() if t["task_id"] == task_id)
        if meeting_id:
            sync_meeting(self.store, meeting_id, self.chroma_dir)  # the meeting's index entry shows task status

    def reconcile_history(self) -> dict:
        return reconcile(self.store, self.chroma_dir)

    def ensure_index(self) -> str | None:
        """Build the knowledge-base index if it is missing; rebuild it if its passage count differs from the
        corpus (e.g. an empty or partial index). Returns a user-facing notice when it had to be repaired."""
        client = _client(self.chroma_dir)
        if KB_COLLECTION not in [c.name for c in client.list_collections()]:
            build_kb_index(chroma_dir=self.chroma_dir)
            return None
        found, expected = client.get_collection(KB_COLLECTION).count(), kb_passage_count()
        if found == expected:
            return None
        build_kb_index(chroma_dir=self.chroma_dir)
        return (f"The local knowledge-base index was incomplete ({found} of {expected} passages) and was rebuilt "
                "before this briefing.")

    def get(self, company: str, domain: str | None, purpose: str, mode: str = "offline_demo") -> tuple[dict, bool]:
        """Return (result, ran_now). Cached requests are never re-run (so reruns never re-spend)."""
        require_not_public("Generating a new briefing")
        if mode not in MODES:
            raise ValueError(f"mode {mode!r} is not available")
        company_id = self.company_id_for(company, domain)
        # The key includes the company's approved-history version: new approvals or task changes give a
        # fresh briefing; ordinary reruns still reuse the saved result.
        version = self.store.version(company_id) if company_id else ""
        key = request_key(company, domain, purpose, mode) + (version,)
        if key in self.cache:
            return self.cache[key], False
        notice = self.ensure_index()
        history = self.history_search(company_id) if company_id else None
        if mode == "live_ai":
            result = self._run_live(company, domain, purpose, history_search=history)
        elif mode == "live_ai_news":
            cfg = live_news_config()
            self._news = getattr(self, "_news", None) or load_tavily_client(cfg)
            result = self._run_live(company, domain, purpose, news_client=self._news,
                                    budget=PersistentBudget(cfg, TAVILY_LEDGER_PATH), history_search=history)
        else:
            result = prepare_briefing(company.strip(), news_client=demo.OfflineNewsClient(),
                                      budget=Budget(SearchConfig()), generate=demo.TemplateDrafter(), decide=None,
                                      domain=(domain or None), purpose=purpose, chroma_dir=self.chroma_dir,
                                      history_search=history)
            result["generation_label"] = demo.GENERATION_LABEL
        result["mode_label"] = MODES[mode]
        if notice:  # an index repair is reported, never silent
            result["message"] = f"{notice} {result.get('message', '')}".strip()
        if company_id and result["status"] in ("briefing_ready", "partial_briefing"):
            self.store.save_briefing(company_id, result)  # dated snapshot; reopening never re-researches
            result["company_id"] = company_id
        self.cache[key] = result
        self.runs += 1
        return result, True

    def _run_live(self, company, domain, purpose, client=None, guard=None, news_client=None, budget=None,
                  history_search=None):
        """Real OpenAI drafting + agent, guarded by the approved caps. News is off unless a news client
        (real Tavily, with its own credit budget) is passed in."""
        require_not_public("Live AI drafting")
        from deal_prep.llm import AGENT_MODEL, DRAFT_MODEL, OpenAIAgentDecider, OpenAIDrafter, load_openai_client
        from deal_prep.spend import PRICES, SpendGuard

        if client is None:
            self._client = getattr(self, "_client", None) or load_openai_client()
            client = self._client
        guard = guard or SpendGuard(run_cap_usd=LIVE_RUN_CAP_USD, daily_cap_usd=LIVE_DAILY_CAP_USD)
        news = news_client or demo.OfflineNewsClient(reason=demo.LIVE_AI_NEWS_OFF)  # news off in this mode
        budget = budget or Budget(SearchConfig())
        result = prepare_briefing(company.strip(), news_client=news, budget=budget,
                                  generate=OpenAIDrafter(client, guard), decide=OpenAIAgentDecider(client, guard),
                                  domain=(domain or None), purpose=purpose, chroma_dir=self.chroma_dir,
                                  prices={"draft": PRICES[DRAFT_MODEL], "agent": PRICES[AGENT_MODEL]},
                                  history_search=history_search, repair_coverage=True)  # I3.1 contract
        result["generation_label"] = (f"Drafted by {DRAFT_MODEL} from the cited evidence; research gaps reviewed by "
                                      f"{AGENT_MODEL}. Checked by code for citations, origin and disclosures.")
        result["usage"]["openai_actual_usd"] = round(guard.run_spent_usd, 6)
        result["usage"]["openai_calls"] = guard.calls
        return result

    def pdf(self, result: dict, language: str = "en") -> tuple[bytes, dict]:
        key = (result["run_id"], language)
        if key not in self.pdf_cache:
            self.pdf_cache[key] = build_pdf(result, result.get("generation_label", ""), language)
        return self.pdf_cache[key]


def save_demo(result: dict, path: Path = SAVED_DEMO_PATH) -> Path:
    """Store a briefing as the saved demonstration. Its original created_at is kept unchanged."""
    if result.get("status") not in ("briefing_ready", "partial_briefing"):
        raise ValueError("only a produced briefing can be saved as a demonstration")
    data = {**copy.deepcopy(result), "saved_demo": True, "mode_label": SAVED_MODE_LABEL}
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=1, ensure_ascii=False), encoding="utf-8")
    return path


