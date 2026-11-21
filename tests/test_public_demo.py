"""Phase 9B: the restricted public demonstration (DEAL_PREP_PUBLIC_DEMO).

Offline, no credentials, no paid calls. These tests cover the server-side switch, the service-boundary gates (OpenAI,
Tavily, history database, new briefings), the saved demo and its approved English PDF, the absence of heavy imports in
a fresh process, and that the normal (non-public) mode is unchanged. They are new tests; they are not part of the
frozen benchmark.
"""
import io
import json
import subprocess
import sys
import textwrap
from pathlib import Path

import pytest
from pypdf import PdfReader

from deal_prep import public_demo
from deal_prep.public_demo import (APPROVED_PDF_PATH, ENV_VAR, PublicDemoRestricted, PublicDemoService, enabled,
                                   load_saved_demo)

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def public(monkeypatch):
    monkeypatch.setenv(ENV_VAR, "1")
    monkeypatch.setenv("DEAL_PREP_NO_DOTENV", "1")


# --- the switch -----------------------------------------------------------------------------------------------

@pytest.mark.parametrize("value,expected", [("1", True), ("true", True), ("YES", True), ("on", True), ("anything", True),
                                            ("", False), ("0", False), ("false", False), ("no", False), ("off", False)])
def test_switch_values_fail_safe(monkeypatch, value, expected):
    monkeypatch.setenv(ENV_VAR, value)
    assert enabled() is expected


def test_switch_off_when_unset(monkeypatch):
    monkeypatch.delenv(ENV_VAR, raising=False)
    assert enabled() is False
    public_demo.require_not_public("anything")  # no error when the switch is off


# --- no external AI / research calls (service boundary, not only the interface) ----------------------------------

def test_openai_unavailable_even_with_a_key(public, monkeypatch):
    from deal_prep import llm
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test-NOT-A-REAL-KEY")
    assert llm.openai_available() is False
    with pytest.raises(PublicDemoRestricted):
        llm.load_openai_client()


def test_tavily_unavailable_even_with_a_key(public, monkeypatch):
    from deal_prep import app_service
    monkeypatch.setenv("TAVILY_API_KEY", "tvly-FAKEKEY-not-real")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test-NOT-A-REAL-KEY")
    assert app_service.tavily_available() is False
    assert list(app_service.available_modes()) == ["offline_demo"]  # no live mode is offered
    with pytest.raises(PublicDemoRestricted):
        app_service.load_tavily_client(app_service.live_news_config())


def test_tavily_search_never_calls_the_transport(public):
    from datetime import date
    from deal_prep.web_research import Budget, SearchConfig, TavilyClient, _httpx_post
    calls = []
    client = TavilyClient("tvly-FAKEKEY-not-real", post=lambda *a, **k: calls.append(a), config=SearchConfig())
    with pytest.raises(PublicDemoRestricted):
        client.search({"query": "x"}, Budget(SearchConfig()), date(2026, 11, 21), [])
    with pytest.raises(PublicDemoRestricted):
        _httpx_post("https://api.tavily.com/search", {}, {}, 5)
    assert calls == []


def test_openai_adapter_never_sends(public):
    from deal_prep.llm import OpenAIDrafter

    class Boom:
        class responses:
            @staticmethod
            def create(**kw):
                raise AssertionError("a request was sent")

    class Guard:
        def check(self, *a): raise AssertionError("guard reached")

    drafter = OpenAIDrafter(Boom(), Guard())
    with pytest.raises(PublicDemoRestricted):
        drafter([{"role": "user", "content": "hi"}])


def test_service_refuses_new_briefings_even_if_modes_are_forced(monkeypatch, tmp_path):
    from deal_prep.app_service import BriefingService
    monkeypatch.delenv(ENV_VAR, raising=False)
    service = BriefingService(chroma_dir=tmp_path / "c", history_path=tmp_path / "h.sqlite")  # built in normal mode
    monkeypatch.setenv(ENV_VAR, "1")
    for mode in ("offline_demo", "live_ai", "live_ai_news"):  # a manipulated request cannot select any mode
        with pytest.raises(PublicDemoRestricted):
            service.get("Arup", "arup.com", "general", mode)
    with pytest.raises(PublicDemoRestricted):
        service._run_live("Arup", "arup.com", "general")


# --- no shared persistent state ---------------------------------------------------------------------------------

def test_history_database_cannot_be_created_or_opened(public, tmp_path):
    from deal_prep.app_service import BriefingService
    from deal_prep.history import HistoryStore
    db = tmp_path / "sub" / "h.sqlite"
    with pytest.raises(PublicDemoRestricted):
        HistoryStore(db)
    with pytest.raises(PublicDemoRestricted):
        BriefingService(chroma_dir=tmp_path / "c", history_path=db)
    assert not db.exists() and not db.parent.exists()  # nothing was created on disk


def test_existing_store_cannot_be_written_in_public_mode(monkeypatch, tmp_path):
    from deal_prep.history import HistoryStore
    monkeypatch.delenv(ENV_VAR, raising=False)
    store = HistoryStore(tmp_path / "h.sqlite")
    monkeypatch.setenv(ENV_VAR, "1")
    with pytest.raises(PublicDemoRestricted):
        store.get_or_create_company("Arup", "arup")


# --- the saved demonstration and its approved English PDF -----------------------------------------------------------

def test_saved_demo_loads_in_public_mode(public):
    demo = load_saved_demo()
    assert demo["saved_demo"] is True and demo["identity"]["name"] == "Shikun & Binui"
    assert demo["evidence"] and demo["briefing"]  # its evidence and recommendations are present
    assert any(item["kind"] == "recommendation" for items in demo["briefing"].values() for item in items)


def test_loader_is_shared_with_the_normal_service():
    from deal_prep import app_service
    assert app_service.load_saved_demo is load_saved_demo and app_service.SAVED_DEMO_PATH == public_demo.SAVED_DEMO_PATH


def test_approved_english_pdf_is_served_as_stored(public):
    demo = load_saved_demo()
    data, info = PublicDemoService().pdf(demo, "en")
    assert data == APPROVED_PDF_PATH.read_bytes() and data.startswith(b"%PDF")
    text = " ".join(p.extract_text() for p in PdfReader(io.BytesIO(data)).pages)
    assert demo["run_id"] in text and "SIMULATED" in text  # it is the PDF of this saved demonstration


def test_hebrew_and_other_pdfs_are_refused(public):
    service, demo = PublicDemoService(), load_saved_demo()
    with pytest.raises(PublicDemoRestricted):
        service.pdf(demo, "he")
    with pytest.raises(PublicDemoRestricted):
        service.pdf({**demo, "saved_demo": False}, "en")


# --- fresh process: page content, no heavy imports, no state -----------------------------------------------------------

SMOKE = textwrap.dedent('''
    import json, sys
    from pathlib import Path
    BLOCKED = ("torch", "sentence_transformers", "transformers", "chromadb", "openai", "httpx", "dotenv", "pydantic")

    class Blocker:
        def find_spec(self, name, path=None, target=None):
            if name.split(".")[0] in BLOCKED:
                raise ImportError("blocked in the public demo: " + name)
    sys.meta_path.insert(0, Blocker())

    from streamlit.testing.v1 import AppTest
    at = AppTest.from_file(sys.argv[1], default_timeout=120).run()
    heavy = sorted(m for m in sys.modules if m.split(".")[0] in BLOCKED)
    out = {"exception": [str(e.value) for e in at.exception],
           "info": [i.value for i in at.info],
           "tabs": len(at.tabs),
           "buttons": [b.label for b in at.button],
           "forms": len(at.get("form")) if hasattr(at, "get") else 0,
           "radio": [list(r.options) for r in at.radio],
           "text": " ".join([m.value for m in at.markdown] + [h.value for h in at.header] + [w.value for w in at.warning]),
           "heavy": heavy}
    print("RESULT" + json.dumps(out))
''')


@pytest.fixture(scope="module")
def cloud_run(tmp_path_factory):
    tmp = tmp_path_factory.mktemp("cloud")
    script = tmp / "smoke.py"
    script.write_text(SMOKE, encoding="utf-8")
    import os
    env = {k: v for k, v in os.environ.items() if k not in ("OPENAI_API_KEY", "TAVILY_API_KEY")}
    env.update({"PYTHONPATH": str(ROOT / "src"), ENV_VAR: "0",  # the cloud entry point must force the mode on
                "OPENAI_API_KEY": "sk-test-NOT-A-REAL-KEY", "DEAL_PREP_HISTORY_DB": str(tmp / "no" / "h.sqlite"),
                "DEAL_PREP_APP_CHROMA_DIR": str(tmp / "no_chroma")})
    proc = subprocess.run([sys.executable, "-B", str(script), str(ROOT / "app" / "streamlit_cloud.py")],
                          capture_output=True, text=True, env=env, timeout=300)
    line = next((ln for ln in proc.stdout.splitlines() if ln.startswith("RESULT")), None)
    assert line, proc.stdout[-2000:] + proc.stderr[-2000:]
    return json.loads(line[len("RESULT"):]), tmp


def test_cloud_entry_renders_the_saved_demo_without_errors(cloud_run):
    out, _ = cloud_run
    assert out["exception"] == []
    assert any("Public demonstration: simulated data" in i for i in out["info"])
    assert "Briefing: Shikun & Binui" in out["text"]
    assert "SIMULATED saved demonstration" in out["text"]


def test_cloud_entry_offers_only_viewing_and_the_english_pdf(cloud_run):
    out, _ = cloud_run
    assert out["tabs"] == 0  # no history or task tabs
    assert "Prepare briefing" not in out["buttons"]  # no request form
    assert out["radio"] == [["English"]]  # no Hebrew option
    assert out["forms"] == 0


def test_cloud_entry_imports_no_heavy_modules_and_writes_nothing(cloud_run):
    out, tmp = cloud_run
    assert out["heavy"] == []
    assert not (tmp / "no").exists() and not (tmp / "no_chroma").exists()


def test_cloud_requirements_are_light():
    names = {ln.split("==")[0].strip().lower() for ln in
             (ROOT / "requirements-cloud.txt").read_text(encoding="utf-8").splitlines()
             if ln.strip() and not ln.lstrip().startswith("#")}
    assert names == {"streamlit", "fpdf2"}
    pinned = (ROOT / "requirements.txt").read_text(encoding="utf-8")
    for name in names:
        line = next(ln for ln in (ROOT / "requirements-cloud.txt").read_text(encoding="utf-8").splitlines()
                    if ln.lower().startswith(name))
        assert line.split("#")[0].strip() in pinned  # same pinned version as the full requirements


def test_app_requirements_match_the_cloud_requirements():
    """Cloud reads the file beside the entrypoint (app/requirements.txt) before the root file; the pins must agree."""
    def pins(path):
        return sorted(ln.split("#")[0].strip() for ln in path.read_text(encoding="utf-8").splitlines()
                      if ln.strip() and not ln.lstrip().startswith("#"))
    assert pins(ROOT / "app" / "requirements.txt") == pins(ROOT / "requirements-cloud.txt") ==         ["fpdf2==2.9.0", "streamlit==1.67.0"]


def test_normal_mode_still_offers_the_form_and_history(monkeypatch, tmp_path):
    """The Windows offline application is unchanged when the switch is off."""
    from streamlit.testing.v1 import AppTest
    monkeypatch.delenv(ENV_VAR, raising=False)
    monkeypatch.setenv("DEAL_PREP_NO_DOTENV", "1")
    monkeypatch.setenv("DEAL_PREP_APP_CHROMA_DIR", str(tmp_path / "chroma"))  # its history DB sits beside it
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("TAVILY_API_KEY", raising=False)
    at = AppTest.from_file(str(ROOT / "app" / "streamlit_app.py"), default_timeout=120).run()
    assert not at.exception
    assert len(at.tabs) == 3
    assert not any("Public demonstration" in i.value for i in at.info)
