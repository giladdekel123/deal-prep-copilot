"""Deal-Prep Copilot: Prepare Meeting, Meeting History and Follow-up Tasks (Prompts 05–06).

Run: streamlit run app/streamlit_app.py
UI only. Research, validation and PDF generation live in src/deal_prep (app_service).
"""
import sys
import uuid
from pathlib import Path

import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from deal_prep.app_service import DEMO_COMPANIES, BriefingService, available_modes, load_saved_demo  # noqa: E402
from deal_prep.history import TASK_STATUSES  # noqa: E402
from deal_prep.orchestrator import MEETING_PURPOSES  # noqa: E402
from deal_prep.pdf_export import (KIND_TAG, ORIGIN_TAG, SECTION_TITLES, HebrewFontMissing, PdfOverflow,  # noqa: E402
                                  reader_disclosures)
from deal_prep.pipeline import STATUS_TEXT  # noqa: E402

OTHER = "Other company (enter name below)"  # plain text: typing "Other company" in the searchable box finds it
KIND_COLOR = {"fact": "violet", "inference": "gray", "recommendation": "green"}
ORIGIN_BADGE = {"public_source": ":blue-background[PUBLIC SOURCE]", "synthetic_record": ":orange-background[SYNTHETIC]"}

st.set_page_config(page_title="Deal-Prep Copilot", page_icon="📄", layout="wide")

if "service" not in st.session_state:
    st.session_state.service = BriefingService()
service: BriefingService = st.session_state.service


def news_outcome(outcome: str) -> tuple[str, str]:
    if outcome.startswith("skipped"):
        reason = outcome.partition(": ")[2] or "live news is off"  # the reason recorded for this mode
        return "⏭️", f"not run ({reason})"
    if outcome == "ok":
        return "✅", "completed"
    return "⚠️", "could not be completed"


tab_prepare, tab_history, tab_tasks = st.tabs(["Prepare Meeting", "Meeting History", "Follow-up Tasks"])

with tab_prepare:
    st.title("Prepare Meeting")
    st.caption("Briefings for Nivarque Document Systems, a fictional vendor. Relationship histories, proposals and "
               "prices are SYNTHETIC demonstration records, never real business facts.")

    with st.form("request"):
        c1, c2 = st.columns([2, 1])
        choice = c1.selectbox("Company", [*DEMO_COMPANIES, OTHER])
        purposes = sorted(MEETING_PURPOSES, key=lambda p: p != "general")
        purpose = c2.selectbox("Meeting purpose", purposes, format_func=lambda p: p.replace("_", " ").capitalize())
        c3, c4 = st.columns([2, 1])
        other_name = c3.text_input("Company name (only with “Other company”)", placeholder="e.g. Teva Pharmaceutical")
        other_domain = c4.text_input("Official domain (optional)", placeholder="e.g. arup.com")
        modes = available_modes()
        mode = st.selectbox("Mode", list(modes), format_func=modes.get,
                            help="Live AI drafting uses paid OpenAI calls within the approved caps; each request runs "
                                 "once and is then reused, so reruns never spend again.")
        submitted = st.form_submit_button("Prepare briefing", type="primary")

    if st.button("Load saved demonstration briefing (SIMULATED)"):
        st.session_state.current = load_saved_demo()
        st.session_state.ran_now = False
        demo = st.session_state.current
        demo_id = service.company_id_for(demo["company_input"], (demo.get("identity") or {}).get("domain"))
        if demo_id:
            st.session_state.company_context = demo_id  # shared company context for all three pages

    if submitted:
        typed = (other_name or "").strip()  # whitespace only counts as empty
        company, domain = (other_name, other_domain) if choice == OTHER else (choice, DEMO_COMPANIES[choice])
        if choice != OTHER and typed:
            # Conflicting input: a listed company is selected, but a different-looking request was typed. Never
            # guess which one was meant, never research, and never show an earlier (cached) briefing as if it
            # answered this request.
            st.session_state.current = None
            st.warning(f"Company is set to “{choice}”, but a company name was also entered (“{typed}”). "
                       f"To use the entered name, choose “{OTHER}” in the Company list; otherwise clear the "
                       "Company name box. No research was run.")
        elif not (company or "").strip():
            st.error("Please enter a company name.")
        else:
            with st.spinner("Running research and checks…"):
                result, ran = service.get(company, domain, purpose, mode)
            st.session_state.current = result
            st.session_state.ran_now = ran
            if result.get("company_id"):
                st.session_state.company_context = result["company_id"]  # shared by all three pages

    result = st.session_state.get("current")
    if result:
        st.divider()
        created = result["created_at"][:16].replace("T", " ")
        if result.get("saved_demo"):
            st.warning(f"**SIMULATED saved demonstration**, created {created} UTC. It was not newly researched and "
                       f"may be out of date. {result.get('reformatted_note', '')}".rstrip())
        elif not st.session_state.get("ran_now", True):
            st.info(f"Showing the saved result for this request (not re-researched). Created {created} UTC.")

        # Real, stage-derived status (from the run trace; nothing is simulated with timers).
        trace = result.get("trace", [])
        internal = [t for t in trace if t["stage"] == "internal_rag"]
        news = [t for t in trace if t["stage"] == "external_news"]
        drafts = [t for t in trace if t["stage"] == "llm_draft"]
        with st.expander("Research status", expanded=False):
            if result["status"] == "clarification_required":
                st.write("Stopped before research: the company name is ambiguous.")
            else:
                st.write(f"✅ Internal knowledge search: {len(internal)} searches, "
                         f"{sum(t['results'] for t in internal)} passages")
                for t in news:
                    icon, text = news_outcome(t["outcome"])
                    st.write(f"{icon} News search: {text}")
                st.write(f"{'✅' if drafts else '⏭️'} Drafting: {len(drafts)} call(s). {result.get('generation_label', '')}")
                ok = result["status"] in ("briefing_ready", "partial_briefing")
                st.write(f"{'✅' if ok else '⚠️'} Citation, origin and disclosure checks: "
                         f"{'passed' if ok else 'not passed'}")
                cost = result["usage"].get("openai_actual_usd")
                st.caption(f"Run {result['run_id']} · {result['total_ms']} ms · news credits used: "
                           f"{result['usage']['tavily_credits']}"
                           + (f" · OpenAI cost: ${cost:.4f} ({result['usage']['input_tokens']} input / "
                              f"{result['usage']['output_tokens']} output tokens)" if cost is not None else "")
                           + f" · {result.get('mode_label', '')}")

        status = result["status"]
        if status == "clarification_required":
            st.warning(result["message"])
        elif status in ("no_briefing", "error"):
            st.error(f"{STATUS_TEXT[status]}. {result['message']}")
        else:
            st.header(f"Briefing: {result['identity']['name']}")
            if result.get("message"):  # e.g. the local index was repaired before research
                st.info(result["message"])
            labels = result["labels"]
            (st.success if status == "briefing_ready" else st.warning)(
                f"{STATUS_TEXT[status]} · Research: {labels['completeness']} · News: {labels['market_intelligence']}")
            shown = reader_disclosures(result)  # the same reader-facing disclosures as the PDF (2026-11-15)
            if shown:
                with st.container(border=True):
                    st.markdown("**Gaps, conflicts and limitations**")
                    for d in shown:
                        st.markdown(f"- {d['text']}")
                        for eid in d.get("evidence_ids", []):
                            e = result.get("evidence", {}).get(eid)
                            if e:
                                st.caption(f"{eid} — {e['provenance_label']}")

            evidence = result.get("evidence", {})
            for key, title in SECTION_TITLES.items():
                st.subheader(title)
                items = result["briefing"].get(key, [])
                if not items:
                    note = (result.get("section_notes") or {}).get(key)  # I6: the drafter's reason, when it gave one
                    st.caption(f"No supported content for this section: {note}" if note
                               else "No supported content for this section (see gaps above).")
                for item in items:
                    origins = sorted({evidence[e]["info_origin"] for e in item["evidence_ids"] if e in evidence})
                    badges = f":{KIND_COLOR[item['kind']]}-background[{KIND_TAG[item['kind']]}]"
                    if item["kind"] == "fact":
                        badges += " " + " ".join(ORIGIN_BADGE[o] for o in origins)
                    st.markdown(f"{badges} {item['text']}")
                    if item["evidence_ids"]:
                        with st.expander(f"Evidence ({len(item['evidence_ids'])})"):
                            for eid in item["evidence_ids"]:
                                e = evidence.get(eid)
                                if e:
                                    st.markdown(f"{ORIGIN_BADGE[e['info_origin']]} **{eid}** — {e['provenance_label']}")
                                    st.caption(e["excerpt"])

            st.divider()
            language = st.radio("PDF language", ["en", "he"], horizontal=True,
                                format_func={"en": "English", "he": "עברית (Hebrew)"}.get,
                                help="Changing the language only re-renders the PDF; it never re-runs research.")
            try:
                pdf_bytes, info = service.pdf(result, language)
                st.download_button(f"Download PDF ({'Hebrew' if language == 'he' else 'English'})",
                                   data=pdf_bytes, mime="application/pdf",
                                   file_name=f"briefing_{result['run_id']}_{language}.pdf")
                if info["pages"] > 1:
                    st.caption(f"Printed on {info['pages']} pages to keep all text at 9 pt or larger; "
                               "nothing was shortened.")
                if language == "he":
                    st.caption("Headings and notices are in Hebrew; section content stays in its source language "
                               "(English) because Hebrew drafting is not enabled yet.")
            except (PdfOverflow, HebrewFontMissing) as e:
                st.error(f"The PDF could not be produced: {e}")


# --- Stage 2: meeting history and follow-up tasks (SQLite is the source of truth) ---------------------------

SYNTHETIC_RECORD = ("SYNTHETIC — user-entered demonstration record; not a verified real-world fact.")


def company_picker(key: str):
    """Demo companies plus any company already in the history database. Returns (company_id, name).
    All pages share one company context: the picker follows it, and a choice here updates it."""
    options = {name: service.company_id_for(name, domain) for name, domain in DEMO_COMPANIES.items()}
    options |= {c["input_name"]: c["company_id"] for c in service.store.companies()
                if c["company_id"] not in options.values()}
    context = st.session_state.get("company_context")
    if context in options.values():
        st.session_state[key] = next(n for n, cid in options.items() if cid == context)

    def follow():
        st.session_state.company_context = options[st.session_state[key]]
    name = st.selectbox("Company", list(options), key=key, on_change=follow)
    return options[name], name


def op_id(key: str) -> str:
    """One stable operation ID per form instance, so a double submit or retry cannot create a duplicate."""
    if key not in st.session_state:
        st.session_state[key] = uuid.uuid4().hex
    return st.session_state[key]


def lines(text: str) -> list[str]:
    return [line.strip() for line in (text or "").splitlines() if line.strip()]


with tab_history:
    st.header("Meeting History")
    st.caption(SYNTHETIC_RECORD + " Only APPROVED records are used in later briefings; drafts never are.")
    company_id, company_name = company_picker("history_company")

    st.markdown("#### Saved briefings")
    saved = service.store.briefings(company_id)
    if not saved:
        st.caption("No saved briefings yet. Briefings are saved automatically when produced.")
    for b in saved:
        with st.expander(f"Briefing of {b['created_at'][:16].replace('T', ' ')} UTC · {b['status']} · {b['mode']}"):
            snap = service.store.open_briefing(b["briefing_id"])
            st.caption("Saved snapshot, shown exactly as produced on that date; it is not refreshed.")
            for key, title in SECTION_TITLES.items():
                for item in (snap.get("briefing") or {}).get(key, []):
                    st.markdown(f"**{title}** · `{KIND_TAG[item['kind']]}` {item['text']}")

    st.markdown("#### Add meeting notes")
    with st.form("notes_form", clear_on_submit=True):
        meeting_date = st.text_input("Meeting date (YYYY-MM-DD, optional)")
        notes = st.text_area("Free-text notes", height=150,
                             placeholder="Participants: … What was discussed, decided and promised …")
        propose = st.form_submit_button("Propose structure (saved as DRAFT)")
    if propose:
        try:
            service.add_meeting_draft(company_id, notes, op_id("notes_op"), meeting_date or None)
            st.session_state.pop("notes_op")  # next submission is a new operation
            st.success("Draft saved. Review and approve it below.")
        except ValueError as e:
            st.error(f"Could not save the notes: {e}")

    st.markdown("#### Meeting records")
    meetings = service.store.meetings(company_id)
    if not meetings:
        st.caption("No meeting records for this company yet.")
    for m in meetings:
        label = f"{m['meeting_date'] or 'date not recorded'} · {m['status']} · {m['meeting_id']}"
        with st.expander(label, expanded=m["status"] == "DRAFT"):
            st.markdown(":orange-background[SYNTHETIC] user-entered demonstration record "
                        f"({m['creation_method']}); not a verified real-world fact.")
            if m["status"] == "APPROVED":
                a = m["approved"]
                st.caption(f"Approved {m['approved_at'][:16].replace('T', ' ')} UTC")
                st.markdown(f"**Summary:** {a.get('summary') or '—'}")
                for k in ("participants", "concerns", "decisions", "commitments"):
                    st.markdown(f"**{k.capitalize()}:** " + ("; ".join(a.get(k) or []) or "not recorded"))
                continue
            p = m["proposed"]
            st.caption(p.get("proposer", ""))
            with st.form(f"review_{m['meeting_id']}"):
                summary = st.text_area("Summary", p["summary"], key=f"sum_{m['meeting_id']}")
                fields = {k: st.text_area(f"{k.capitalize()} (one per line)", "\n".join(p[k]),
                                          key=f"{k}_{m['meeting_id']}")
                          for k in ("participants", "concerns", "decisions", "commitments")}
                if p["unknowns"]:
                    st.caption("Unknown or unconfirmed: " + "; ".join(p["unknowns"]))
                chosen = []
                for i, t in enumerate(p["tasks"]):
                    st.markdown(f"**Proposed task {i + 1}:** {t['description']}")
                    make = st.checkbox("Create this follow-up task", key=f"mk_{m['meeting_id']}_{i}")
                    due = st.text_input("Confirmed due date (YYYY-MM-DD; leave empty if not agreed)",
                                        t["suggested_due_date"] or "", key=f"due_{m['meeting_id']}_{i}")
                    if t["due_raw"]:
                        st.caption(f"Wording in the notes: “{t['due_raw']}” (never converted automatically)")
                    if make:
                        chosen.append({"description": t["description"], "due_date": due.strip() or None,
                                       "due_raw": t["due_raw"], "op_id": f"{m['meeting_id']}:task:{i}"})
                approve = st.form_submit_button("Approve this record")
            if approve:
                approved = {"summary": summary.strip(), **{k: lines(v) for k, v in fields.items()}}
                try:
                    service.approve_meeting(m["meeting_id"], approved, chosen)
                    st.success("Approved. It will be used in later briefings for this company.")
                    st.rerun()
                except ValueError as e:
                    st.error(f"Not approved: {e}")

with tab_tasks:
    st.header("Follow-up Tasks")
    st.caption("Statuses are changed manually; there are no reminders. A due date is set only when confirmed.")
    task_company_id, _ = company_picker("tasks_company")
    tasks = service.store.tasks(company_id=task_company_id)
    if not tasks:
        st.caption("No follow-up tasks for this company yet.")
    for t in tasks:
        c1, c2 = st.columns([3, 1])
        due = t["due_date"] or (f"not set (notes said “{t['due_raw']}”)" if t["due_raw"] else "not set")
        c1.markdown(f"**{t['description']}**  \nDue: {due} · {t['task_id']}"
                    + (f" · from meeting {t['meeting_id']}" if t["meeting_id"] else ""))
        new_status = c2.selectbox("Status", TASK_STATUSES, index=TASK_STATUSES.index(t["status"]),
                                  key=f"status_{t['task_id']}")
        if new_status != t["status"]:
            service.set_task_status(t["task_id"], new_status)
            st.rerun()

    with st.form("task_form", clear_on_submit=True):
        description = st.text_input("New task")
        due = st.text_input("Confirmed due date (YYYY-MM-DD, optional)")
        add = st.form_submit_button("Add task")
    if add:
        try:
            service.add_task(task_company_id, description, op_id("task_op"), due or None)
            st.session_state.pop("task_op")
            st.success("Task added.")
            st.rerun()
        except ValueError as e:
            st.error(f"Could not add the task: {e}")
