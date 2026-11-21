"""Prompt 07 acceptance report: requirements-to-tests matrix and acceptance case set (spec §5, §9).

Usage: python scripts/acceptance_report.py
Runs, offline and with no paid calls:
  1. the full pytest suite, with a JUnit XML record of every executed test case;
  2. scripts/kb_eval.py (AT-07 Recall@5 against the owner-approved thresholds, provenance/authority cases);
  3. offline artifact checks: saved-demo citation integrity, EN/HE PDFs regenerated from the saved demo,
     and a headless Streamlit server start (health endpoint and page);
  4. deterministic checks of the recorded live-run artifacts in runs/ (nothing is re-run live).
Then marks every requirement criterion and every case in eval/acceptance_cases_v1.json PASS / FAIL / NOT TESTED:
  - automated criteria: PASS only if every mapped test case was executed in this run and passed;
    FAIL if any failed, errored or is a strict xfail (a known defect reproduced); NOT TESTED if skipped.
    A mapped test name that matches no executed test stops the script (a typo must never become a PASS);
  - recorded-live criteria: checked from saved artifacts of earlier owner-authorized live runs;
  - manual criteria: read from eval/manual_checks_v1.json (who inspected what, and when);
  - other criteria carry an explicit FAIL or NOT TESTED status with the reason.
Every non-PASS row is classed as a defect, a known deviation, or work that needs live API calls.
Writes docs/ACCEPTANCE_REPORT.md and runs/acceptance_<timestamp>.json (+ the JUnit XML).
"""
import json
import os
import platform
import re
import socket
import subprocess
import sys
import tempfile
import time
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
RUNS = ROOT / "runs"
REPORT = ROOT / "docs" / "ACCEPTANCE_REPORT.md"
OFFLINE_ENV = {"HF_HUB_OFFLINE": "1", "TRANSFORMERS_OFFLINE": "1", "ANONYMIZED_TELEMETRY": "False",
               "DEAL_PREP_NO_DOTENV": "1"}
LIVE_BRIEFING = "live_briefing_20261106T085810Z"  # owner-authorized live run with news (Arup)
LIVE_NO_NEWS = "live_briefing_20261106T082723Z"   # owner-authorized live run, news off (Arup)
LIVE_NEWS_CHECK = "live_news_check_20261106T064805Z"
# Owner-authorized Option B live verification, 2026-11-06 (three briefings with news; not re-run here).
OPTION_B = {"shikun_binui": "live_briefing_20261106T150006Z", "ashtrom": "live_briefing_20261106T150125Z",
            "skanska": "live_briefing_20261106T150217Z"}
OPTION_B_LIMITS = {"usd_per_briefing": 0.10, "usd_total": 0.30, "credits_per_briefing": 5, "credits_total": 15}
KEY_LIKE = re.compile(r"(sk-[A-Za-z0-9_-]{8,}|tvly-[A-Za-z0-9_-]{6,}|Bearer\s+\S{10,})")
SECTIONS = ("company_overview", "recent_developments", "our_relationship", "opportunities",
            "competitive_positioning", "meeting_recommendations")
CASES = ROOT / "eval" / "acceptance_cases_v1.json"
MANUAL = ROOT / "eval" / "manual_checks_v1.json"
# AT-07 thresholds approved by the owner on 2026-11-06 (R8 passage miss kept as a documented limitation).
RECALL_THRESHOLDS = {"doc_recall": 1.00, "passage_recall": 0.90}
BLOCKERS = {"defect": "Actual failure (defect found by the audit)",
            "deviation": "Actual failure (known deviation from the specification)",
            "live": "Requires live API calls (needs owner authorization)"}


def T(*tests):
    return {"kind": "tests", "tests": list(tests)}


def fixed(status, reason, blocker):
    return {"kind": "fixed", "status": status, "reason": reason, "blocker": blocker}


def artifact(check):
    return {"kind": "artifact", "check": check}


def manual(check_id):
    return {"kind": "manual", "id": check_id}


# --- requirement criteria -------------------------------------------------------------------
# Each row: (requirement ID, criterion, evidence). Test selectors are "<file>::<function>".
CRITERIA = [
    # Stage 1 functional requirements (spec §5.1)
    ("FR-01", "Nonblank company name required; meeting purpose validated (default general); EN/HE PDF language",
     T("test_orchestrator::test_invalid_inputs_rejected", "test_app::test_unknown_pdf_language_rejected",
       "test_app::test_streamlit_language_switch_rerenders_pdf_without_new_research",
       "test_app::test_hebrew_pdf_is_one_page_with_hebrew_text")),
    ("FR-02", "Ambiguous company name stops research and asks for clarification",
     T("test_orchestrator::test_ambiguous_company_stops_before_any_search",
       "test_pipeline::test_ambiguous_company_asks_for_clarification_and_runs_nothing",
       "test_web_research::test_ambiguous_name_requires_clarification_and_no_search",
       "test_app::test_ambiguous_name_asks_for_domain",
       "test_app::test_streamlit_page_shows_clarification_for_ambiguous_name")),
    ("FR-02", "Look-alike organizations are never mixed (Arup vs ARUP Laboratories)",
     T("test_web_research::test_arup_laboratories_site_never_counts_as_arup",
       "test_web_research::test_arup_site_never_counts_as_arup_laboratories",
       "test_web_research::test_arup_laboratories_as_target_is_not_swallowed_by_its_lookalike",
       "test_web_research::test_lookalike_result_excluded_and_official_source_marked_primary",
       "test_orchestrator::test_company_profile_evidence_is_public_and_never_the_lookalike")),
    ("FR-03", "Every document carries ID, type, approval, dates, info_origin, creation_method, organizations; "
              "public snapshots keep URL, publisher, dates, verification, excerpts and claim links",
     T("test_kb_corpus::test_whole_corpus_passes_validator_and_chunks",
       "test_kb_corpus::test_every_chunk_has_complete_provenance",
       "test_kb_public::test_public_document_passes_provenance_validator",
       "test_kb_public::test_file_header_matches_manifest_provenance",
       "test_kb_public::test_excerpts_and_claims_appear_verbatim_in_file")),
    ("FR-03", "Corpus contains PDF, DOCX, XLSX, TXT and MD documents",
     T("test_kb_corpus::test_first_tranche_size_and_all_five_formats", "test_kb_extract::test_docx_paragraphs_headings_and_table_rows",
       "test_kb_extract::test_pdf_text_extracted_per_page_with_location", "test_kb_extract::test_text_formats_extract_paragraphs",
       "test_kb_extract::test_xlsx_rows_carry_sheet_and_row_location")),
    ("FR-03", "Corpus size of about 30–50 documents", artifact("corpus_size")),
    ("FR-04", "Local Chroma index returns passages with precise source and provenance metadata",
     T("test_kb_index::test_every_stored_record_has_complete_provenance",
       "test_kb_index::test_evidence_objects_carry_labels_and_resolved_reality",
       "test_kb_index::test_company_scope_excludes_other_companies", "test_kb_index::test_origin_filter",
       "test_retrieval::test_query_returns_metadata")),
    ("FR-04", "Spreadsheet rows keep product, price, unit and term together",
     T("test_price_table::test_each_row_keeps_its_own_price_unit_and_term",
       "test_price_table::test_no_row_contains_another_rows_price", "test_price_table::test_one_chunk_per_price_row",
       "test_kb_extract::test_xlsx_price_rows_keep_product_price_unit_and_term")),
    ("FR-05", "Internal RAG and external news search run for every briefing (traced)",
     T("test_orchestrator::test_trace_records_every_mandatory_step",
       "test_pipeline::test_trace_covers_every_stage_with_run_id")),
    ("FR-05", "48-hour search first, 30-day fallback only without relevant 48-hour results; explicit dates "
              "(simulated provider)",
     T("test_web_research::test_recent_result_found_in_one_call_with_expected_payload",
       "test_web_research::test_fallback_to_30_days_when_no_recent_result_and_labelled_as_older_context",
       "test_web_research::test_window_boundaries", "test_web_research::test_undated_result_is_never_recent_and_triggers_fallback",
       "test_web_research::test_future_date_is_not_recent",
       "test_web_research::test_only_passing_mentions_in_48h_triggers_fallback_not_false_recent",
       "test_web_research::test_publication_and_retrieval_dates_kept_separate_with_provider_estimate_label")),
    ("FR-05", "Live Tavily 48-hour news search (recorded owner-authorized run)", artifact("live_news_check")),
    ("FR-06", "One bounded agent: call cap, identical failed request rejected, unknown actions stop it",
     T("test_agent::test_call_limit_stops_the_agent", "test_agent::test_identical_failed_request_is_rejected_and_counted",
       "test_agent::test_unknown_action_stops_agent_without_side_effects",
       "test_agent::test_tavily_budget_shared_with_mandatory_search",
       "test_agent::test_internal_lookup_adds_only_new_supplemental_evidence")),
    ("FR-06", "Agent cannot skip mandatory searches; agent failure keeps the briefing usable",
     T("test_agent::test_finish_immediately_uses_no_calls_and_keeps_mandatory_evidence",
       "test_agent::test_model_failure_stops_agent_but_keeps_bundle_usable",
       "test_pipeline::test_agent_failure_does_not_block_the_briefing")),
    ("FR-06", "Live agent (gpt-6-luna) stays within 3 optional calls and the $0.10 run cap (recorded runs)",
     artifact("live_agent_bounds")),
    ("FR-07", "Claim-type origin rule enforced deterministically (origin_violation)",
     T("test_citations::test_synthetic_evidence_cannot_support_a_real_world_fact",
       "test_citations::test_public_evidence_cannot_support_vendor_claims",
       "test_citations::test_public_evidence_cannot_support_a_relationship_claim",
       "test_citations::test_synthetic_evidence_cannot_support_public_pricing",
       "test_citations::test_mixed_citation_flags_only_the_wrong_origin",
       "test_citations::test_persistent_origin_violation_produces_no_briefing",
       "test_authority::test_c4_synthetic_note_cannot_prove_a_real_world_fact",
       "test_authority::test_public_source_cannot_prove_vendor_price")),
    ("FR-07", "Claim-dependent authority (current price list, proposal price ≠ list price, drafts are not history)",
     T("test_authority::test_c1_current_price_uses_list_in_force_now",
       "test_authority::test_c1_superseded_list_was_in_force_before_its_end_date",
       "test_authority::test_c3_proposal_price_is_never_the_list_price",
       "test_authority::test_draft_meeting_notes_never_count_as_history",
       "test_authority::test_no_valid_source_when_product_unknown",
       "test_disclosures::test_superseded_price_cannot_support_a_current_price_fact")),
    ("FR-07", "Unresolved discrepancies are disclosed with traceable dated sources",
     T("test_disclosures::test_conflicting_approved_statements_c2_are_disclosed",
       "test_disclosures::test_real_public_conflict_is_a_required_disclosure",
       "test_disclosures::test_conflict_disclosure_explains_the_disagreement_with_traceable_dated_sources",
       "test_disclosures::test_undisclosed_conflict_retried_then_rejected",
       "test_disclosures::test_conflict_detected_when_only_one_side_was_retrieved")),
    ("FR-08", "Six sections; facts vs inference/recommendation; schema enforced",
     T("test_briefing::test_schema_rules_enforced", "test_briefing::test_valid_draft_accepted_in_one_call",
       "test_citations::test_schema_restricts_claim_types_per_section",
       "test_app::test_streamlit_page_selects_a_demo_company_and_shows_six_sections_with_origin_badges")),
    ("FR-08", "No fabricated citations or relationships",
     T("test_citations::test_invented_or_mistyped_citations_rejected",
       "test_citations::test_invented_citation_rejected_even_on_inferences_and_recommendations",
       "test_disclosures::test_cannot_invent_relationship_for_a_new_lead",
       "test_disclosures::test_relationship_fact_must_cite_this_customers_records")),
    ("FR-08", "Origin label on every claim; 'Our relationship' always synthetic",
     T("test_app::test_pdf_tags_items_and_origins", "test_app::test_template_items_read_as_sentences_and_cite_the_right_material",
       "test_live_news_mode::test_synthetic_labels_preserved_alongside_live_news")),
    ("FR-08", "Quoted conflict statements are supported by the exact cited passage (automated)",
     T("test_disclosures::test_quoted_statements_are_supported_by_their_cited_passages",
       "test_disclosures::test_unretrieved_passage_is_never_quoted")),
    ("FR-08", "Claim support reviewed item by item against cited passages (recorded live Arup briefing and "
              "saved demo)", manual("MC-02")),
    ("FR-08", "Claim support reviewed item by item: Option B live briefings (Shikun & Binui, Ashtrom Group, "
              "Skanska)", manual("MC-04")),
    ("FR-08", "Saved demo: every citation exists, fact origins match claim types, relationship facts are "
              "synthetic, SIMULATED label kept", artifact("saved_demo_citations")),
    ("FR-09", "Streamlit shows the briefing and evidence; reruns reuse the result",
     T("test_app::test_streamlit_page_runs_once_and_reruns_do_not_research_again",
       "test_app::test_streamlit_page_selects_a_demo_company_and_shows_six_sections_with_origin_badges")),
    ("FR-09", "One-page PDF with company, purpose, date, sources, origin badges and synthetic disclaimer",
     T("test_app::test_pdf_is_exactly_one_readable_page_with_required_content",
       "test_app::test_long_content_is_shortened_transparently_and_stays_one_page",
       "test_app::test_disclosures_are_never_dropped_so_extreme_content_reports_overflow",
       "test_app::test_pdf_tags_items_and_origins")),
    ("FR-09", "Hebrew RTL PDF with mixed-direction identifiers",
     T("test_app::test_hebrew_pdf_is_one_page_with_hebrew_text", "test_app::test_hebrew_identifiers_are_forced_left_to_right",
       "test_app::test_pdf_handles_non_latin_punctuation", "test_app::test_hebrew_pdf_reports_missing_font_clearly")),
    ("FR-10", "No internal match, web failure, both unavailable and no-news cases are stated, not fabricated",
     T("test_pipeline::test_a_no_internal_match_gives_partial_externally_grounded_briefing",
       "test_pipeline::test_b_web_failure_gives_internal_only_briefing_without_market_intelligence",
       "test_pipeline::test_c_both_unavailable_gives_no_speculative_briefing",
       "test_pipeline::test_no_news_found_is_disclosed_not_hidden",
       "test_web_research::test_no_results_reports_not_found_not_proof_of_absence",
       "test_disclosures::test_incomplete_research_must_be_disclosed")),
    ("FR-11", "Three curated scenarios (Shikun & Binui, Ashtrom Group, Arup) run offline",
     T("test_orchestrator::test_complete_bundle_for_registered_company",
       "test_orchestrator::test_new_lead_has_explicit_no_relationship_gap",
       "test_orchestrator::test_shikun_binui_proposal_found_by_relationship_search",
       "test_app::test_streamlit_page_selects_a_demo_company_and_shows_six_sections_with_origin_badges")),
    ("FR-11", "Arbitrary company outside the registry (simulated news)",
     T("test_orchestrator::test_unknown_company_is_externally_grounded_with_internal_gap",
       "test_web_research::test_unregistered_company_allowed_but_name_only",
       "test_web_research::test_unregistered_company_matches_by_name_only")),
    ("FR-11", "Arbitrary company with live research (Skanska, skanska.com, outside the registry)",
     artifact("live_skanska")),
    # Stage 2 (spec §5.2)
    ("FR-12", "SQLite stores companies, dated briefing snapshots, meetings and tasks with foreign keys",
     T("test_history::test_schema_init_is_idempotent_and_foreign_keys_are_enforced",
       "test_history::test_company_is_unique_by_org_id_and_by_name",
       "test_history::test_saved_briefing_snapshot_reopens_unchanged",
       "test_history::test_full_sequence_later_briefing_uses_approved_history_only")),
    ("FR-13", "Nothing becomes history without explicit approval",
     T("test_history::test_drafts_are_never_indexed_and_approval_indexes_with_labels",
       "test_history::test_full_sequence_later_briefing_uses_approved_history_only",
       "test_authority::test_draft_meeting_notes_never_count_as_history")),
    ("FR-13", "Unknown dates, participants and commitments stay unknown; nothing invented",
     T("test_history::test_proposer_suggests_only_explicit_dates_and_keeps_vague_ones_raw",
       "test_history::test_proposer_lists_missing_participants_as_unknown",
       "test_history::test_proposer_copies_from_notes_and_invents_nothing")),
    ("FR-13", "Structure proposed using AI",
     fixed("FAIL", "Deviation: Prompt 06 implemented a labelled rule-based extractor (no AI model) under the "
                   "deadline. The output contract allows a later LLM proposer behind the same validation.",
           "deviation")),
    ("FR-14", "Approved history enters later briefings for the same company only, dated and labelled synthetic",
     T("test_history::test_full_sequence_later_briefing_uses_approved_history_only",
       "test_history::test_history_search_is_company_scoped",
       "test_history::test_unregistered_company_with_approved_history_has_no_internal_gap",
       "test_history::test_drafts_are_never_indexed_and_approval_indexes_with_labels")),
    ("FR-14", "Live AI drafting phrases meeting history as historical, not current truth",
     fixed("NOT TESTED", "Verified only with the template drafter; no live drafting run with meeting history.",
           "live")),
    ("FR-15", "Tasks: description, optional due date, three statuses, manual updates",
     T("test_history::test_task_status_changes_are_recorded_and_validated",
       "test_history::test_meeting_and_task_creation_are_idempotent",
       "test_history::test_streamlit_history_and_tasks_tabs")),
    ("FR-16", "Three pages: Prepare Meeting, Meeting History, Follow-up Tasks",
     T("test_history::test_streamlit_history_and_tasks_tabs")),
    ("FR-16", "Consistent company context across the three pages",
     T("test_acceptance_failures::test_company_context_is_shared_across_pages")),
    ("FR-16", "Streamlit app starts headless offline and serves the page (health endpoint and HTTP 200)",
     artifact("streamlit_startup")),
    # Acceptance tests (spec §9)
    ("AT-01", "Curated company: six sections, traceable claims, usable PDF (offline)",
     T("test_app::test_streamlit_page_selects_a_demo_company_and_shows_six_sections_with_origin_badges",
       "test_app::test_pdf_is_exactly_one_readable_page_with_required_content",
       "test_pipeline::test_complete_research_gives_ready_briefing_with_canonical_disclosures",
       "test_citations::test_correctly_cited_draft_is_valid")),
    ("AT-01", "Curated company, live: six sections, citations validated, one-page EN and HE PDFs (recorded run)",
     artifact("live_briefing")),
    ("AT-02", "Uncurated company: mandatory research runs; 'no internal history' gap (simulated news)",
     T("test_pipeline::test_a_no_internal_match_gives_partial_externally_grounded_briefing",
       "test_orchestrator::test_unknown_company_is_externally_grounded_with_internal_gap")),
    ("AT-02", "Uncurated company with live search: mandatory research ran; 'no internal records' gap; nothing "
              "invented (Skanska)", artifact("live_skanska")),
    ("AT-03", "30-day fallback with correct dates and window labels (controlled fixture)",
     T("test_web_research::test_fallback_to_30_days_when_no_recent_result_and_labelled_as_older_context",
       "test_web_research::test_only_opaque_redirects_in_48h_triggers_fallback",
       "test_web_research::test_window_boundaries")),
    ("AT-04", "No internal or external material: visible gaps, nothing invented",
     T("test_pipeline::test_c_both_unavailable_gives_no_speculative_briefing",
       "test_app::test_unknown_company_offline_has_no_sources_and_no_briefing",
       "test_disclosures::test_cannot_invent_relationship_for_a_new_lead")),
    ("AT-05", "Synthetic conflicts: C1 resolved by authority, C2 disclosed as unresolved",
     T("test_authority::test_c1_current_price_uses_list_in_force_now",
       "test_authority::test_c2_conflicting_approved_statements_stay_unresolved",
       "test_disclosures::test_resolved_conflict_c1_is_not_a_required_disclosure",
       "test_disclosures::test_synthetic_conflict_c2_disclosure_states_both_sides_and_effective_dates")),
    ("AT-06", "EN and HE PDFs: one page, Hebrew text, LTR-isolated identifiers, size stress (automated)",
     T("test_app::test_pdf_is_exactly_one_readable_page_with_required_content",
       "test_app::test_hebrew_pdf_is_one_page_with_hebrew_text",
       "test_app::test_hebrew_identifiers_are_forced_left_to_right",
       "test_app::test_long_content_is_shortened_transparently_and_stays_one_page")),
    ("AT-06", "EN and HE PDFs regenerated now from the saved demo are one page each", artifact("render_pdfs")),
    ("AT-06", "Visual inspection of rendered EN/HE layout", manual("MC-01")),
    ("AT-07", "Recall@5 measured against documented ground truth (kb_eval)", artifact("kb_eval")),
    ("AT-07", "Approved thresholds: document Recall@5 = 100%, passage Recall@5 ≥ 90% (R8 documented limitation)",
     artifact("kb_eval_threshold")),
    ("AT-08", "Web outage, LLM error, malformed output and missing credential fail gracefully",
     T("test_pipeline::test_b_web_failure_gives_internal_only_briefing_without_market_intelligence",
       "test_pipeline::test_model_outage_gives_clear_error_not_a_crash",
       "test_pipeline::test_d_invalid_model_output_twice_gives_clear_error",
       "test_pipeline::test_d_invalid_then_valid_output_recovers_with_one_retry",
       "test_llm::test_missing_key_gives_clear_error",
       "test_llm::test_spend_refusal_produces_clear_no_briefing_without_calling_the_model")),
    ("AT-09", "Ambiguous names never combine content from different companies",
     T("test_orchestrator::test_ambiguous_company_stops_before_any_search",
       "test_web_research::test_arup_laboratories_as_target_is_not_swallowed_by_its_lookalike",
       "test_kb_index::test_company_scope_excludes_other_companies")),
    ("AT-10", "Real end-to-end latency, calls and cost for the three demonstrations", artifact("live_three_demos")),
    ("AT-10", "Live briefings for Shikun & Binui and Ashtrom Group meet the Option B criteria (research ran, honest "
              "status, time windows, provenance, limits, no keys, one-page PDFs); totals within authorization",
     artifact("live_option_b_registry")),
    ("AT-11", "Malicious instructions in retrieved content do not override rules (simulated model)",
     T("test_kb_corpus::test_prompt_injection_text_is_stored_only_as_labelled_synthetic_evidence",
       "test_agent::test_prompt_injection_in_evidence_cannot_trigger_an_action")),
    ("AT-11", "Prompt-injection fixture against the live model",
     fixed("NOT TESTED", "Not run with a real model.", "live")),
    ("AT-12", "Unapproved notes cannot influence briefings",
     T("test_history::test_full_sequence_later_briefing_uses_approved_history_only",
       "test_history::test_drafts_are_never_indexed_and_approval_indexes_with_labels",
       "test_disclosures::test_draft_meeting_notes_cannot_support_a_fact")),
    ("AT-13", "Approved record influences the same company only, with attribution and date",
     T("test_history::test_full_sequence_later_briefing_uses_approved_history_only",
       "test_history::test_history_search_is_company_scoped")),
    ("AT-14", "Task statuses persist and change manually; omitted due date stays absent",
     T("test_history::test_task_status_changes_are_recorded_and_validated",
       "test_history::test_proposer_lists_missing_participants_as_unknown",
       "test_history::test_edits_and_task_status_resync_the_index",
       "test_history::test_streamlit_history_and_tasks_tabs")),
    ("AT-15", "Saved briefings keep their original timestamps",
     T("test_history::test_saved_briefing_snapshot_reopens_unchanged",
       "test_history::test_full_sequence_later_briefing_uses_approved_history_only",
       "test_app::test_saved_demo_keeps_original_date_and_simulated_label",
       "test_app::test_save_and_load_round_trip_never_redates")),
    ("AT-16", "Baseline and agent compared on the same fixture without declaring a winner (simulated)",
     T("test_pipeline::test_baseline_and_agent_compared_on_the_same_fixture",
       "test_pipeline::test_comparison_reports_differences_without_declaring_a_winner")),
    ("AT-16", "Measured baseline-versus-agent comparison on representative cases",
     fixed("NOT TESTED", "Needs matched live runs of both variants with the real models (Prompt 07 step 6); the "
                         "simulated comparison above tests the mechanics only.", "live")),
    ("AT-17", "At most three optional calls; repeats counted; identical failed calls rejected; caps fail safely",
     T("test_agent::test_call_limit_stops_the_agent", "test_agent::test_identical_failed_request_is_rejected_and_counted",
       "test_web_research::test_per_briefing_cap_blocks_fallback_before_sending",
       "test_web_research::test_daily_cap_refuses_before_any_call",
       "test_live_news_mode::test_failed_news_request_is_not_retried")),
    ("AT-18", "Injected instructions cannot trigger privileged actions, arbitrary queries or record changes",
     T("test_agent::test_prompt_injection_in_evidence_cannot_trigger_an_action",
       "test_agent::test_unknown_action_stops_agent_without_side_effects",
       "test_agent::test_unsafe_or_off_target_web_queries_rejected_before_sending",
       "test_web_research::test_payload_with_unexpected_keys_refused_before_sending",
       "test_orchestrator::test_only_the_company_name_is_sent_to_the_news_provider")),
    ("AT-19", "Redacted step-level trace; no keys or hidden reasoning (offline)",
     T("test_pipeline::test_trace_covers_every_stage_with_run_id", "test_pipeline::test_trace_never_contains_the_api_key",
       "test_pipeline::test_key_like_text_in_agent_query_is_redacted",
       "test_agent::test_context_is_sanitized_and_labels_every_evidence_item",
       "test_live_news_mode::test_no_key_appears_in_the_result")),
    ("AT-19", "Recorded live run artifacts contain no key-like strings", artifact("live_no_keys")),
    ("AT-20", "Versioned 20-case evaluation set with PASS/FAIL/NOT TESTED statuses", artifact("eval_set")),
    ("AT-21", "Same operation ID never duplicates; crash/retry and stale index stay consistent",
     T("test_history::test_meeting_and_task_creation_are_idempotent",
       "test_history::test_crash_after_sqlite_commit_then_retry_leaves_no_duplicates",
       "test_history::test_reconcile_removes_stale_entries_and_restores_missing_ones",
       "test_history::test_edits_and_task_status_resync_the_index")),
    ("AT-22", "Provenance labels survive index, retrieval, evidence, agent context, screen, PDF and history",
     T("test_kb_index::test_every_stored_record_has_complete_provenance",
       "test_kb_index::test_evidence_objects_carry_labels_and_resolved_reality",
       "test_agent::test_context_is_sanitized_and_labels_every_evidence_item",
       "test_app::test_pdf_tags_items_and_origins",
       "test_app::test_streamlit_page_selects_a_demo_company_and_shows_six_sections_with_origin_badges",
       "test_history::test_drafts_are_never_indexed_and_approval_indexes_with_labels",
       "test_history::test_streamlit_history_and_tasks_tabs")),
    ("AT-23", "No synthetic content presented as real fact; wrong origin rejected",
     T("test_citations::test_synthetic_evidence_cannot_support_a_real_world_fact",
       "test_authority::test_c4_synthetic_only_evidence_is_an_origin_violation",
       "test_history::test_meeting_records_are_always_synthetic",
       "test_live_news_mode::test_synthetic_labels_preserved_alongside_live_news")),
    ("AT-24", "Public evidence keeps URL, publisher, publication date (or unknown), retrieval date, verification",
     T("test_web_research::test_evidence_has_full_public_provenance_and_short_excerpt",
       "test_web_research::test_publication_and_retrieval_dates_kept_separate_with_provider_estimate_label",
       "test_kb_public::test_file_header_matches_manifest_provenance",
       "test_provenance::test_publication_date_unknown_is_allowed_but_not_missing")),
    ("AT-25", "Validator rejects invalid provenance; indexing refuses incomplete provenance",
     T("test_provenance::test_broken_sample_rejected", "test_provenance::test_public_text_mentioning_fictional_org_rejected",
       "test_provenance::test_broken_registry_rejected", "test_kb_index::test_chunk_with_missing_origin_refused",
       "test_kb_index::test_invalid_document_blocks_the_whole_build")),
    # Standing rules with direct tests
    ("SR-05", "Spending and credit caps enforced in code before sending",
     T("test_llm::test_call_over_the_per_briefing_cap_is_refused_before_sending",
       "test_llm::test_daily_cap_counts_earlier_spending_from_the_ledger", "test_llm::test_unpriced_model_is_refused",
       "test_live_news_mode::test_daily_credit_cap_persists_across_restarts")),
    ("SR-09", "No unexpected service calls from UI reruns; offline pipeline runs with network blocked",
     T("test_app::test_streamlit_page_runs_once_and_reruns_do_not_research_again",
       "test_app::test_repeated_requests_reuse_the_cached_result", "test_offline::test_pipeline_runs_with_network_blocked")),
    ("SR-17", "Prompt 01 baseline frozen; classroom NexaStream material never indexed",
     T("test_separation::test_no_nexastream_content_in_chunks", "test_separation::test_no_indexed_file_under_classroom",
       "test_retrieval::test_passage_level_hit", "test_corpus_metadata::test_manifest_and_files_match_one_to_one")),
    # Prompt 07 step 3: deliberate failure modes (offline)
    ("P07-3", "Missing API credential: clear error; live modes offered only when keys exist",
     T("test_llm::test_missing_key_gives_clear_error", "test_llm::test_live_mode_offered_only_when_a_key_is_available",
       "test_live_news_mode::test_live_news_mode_offered_only_with_both_keys",
       "test_web_research::test_client_requires_explicit_key_and_never_reads_environment")),
    ("P07-3", "Web-search outage: partial internal-only briefing, labelled; server errors not retried",
     T("test_pipeline::test_b_web_failure_gives_internal_only_briefing_without_market_intelligence",
       "test_web_research::test_server_error_is_not_retried_and_reported_as_partial",
       "test_orchestrator::test_web_failure_gives_partial_internal_only")),
    ("P07-3", "Unknown or ambiguous company: clarification or explicit gaps, never invented content",
     T("test_app::test_unknown_company_offline_has_no_sources_and_no_briefing",
       "test_pipeline::test_ambiguous_company_asks_for_clarification_and_runs_nothing",
       "test_web_research::test_manual_identity_without_registry_still_safe")),
    ("P07-3", "Malformed or corrupted input document: the build stops and the existing index is kept",
     T("test_acceptance_failures::test_corrupted_document_stops_the_build_and_keeps_the_existing_index",
       "test_kb_extract::test_scanned_pdf_without_text_layer_rejected", "test_kb_extract::test_xlsx_with_formula_rejected",
       "test_kb_extract::test_xlsx_with_merged_cells_rejected", "test_kb_extract::test_unknown_format_rejected",
       "test_kb_index::test_invalid_document_blocks_the_whole_build")),
    ("P07-3", "Corrupted document error names the document",
     T("test_acceptance_failures::test_corrupted_document_error_names_the_document")),
    ("P07-3", "PDF generation error: missing Hebrew font and overflow reported clearly; no PDF without a briefing",
     T("test_app::test_hebrew_pdf_reports_missing_font_clearly",
       "test_app::test_disclosures_are_never_dropped_so_extreme_content_reports_overflow",
       "test_app::test_no_pdf_without_a_briefing")),
    ("P07-3", "Inconsistent local index: missing KB index rebuilt; empty KB index gives no invented briefing; stale "
              "history index reconciled",
     T("test_acceptance_failures::test_missing_kb_index_is_rebuilt_and_briefing_recovers",
       "test_acceptance_failures::test_empty_kb_index_never_produces_an_invented_briefing",
       "test_history::test_reconcile_removes_stale_entries_and_restores_missing_ones")),
    ("P07-3", "Inconsistent local index: an empty KB index is reported truthfully as an index problem",
     T("test_acceptance_failures::test_empty_kb_index_is_reported_as_an_index_problem")),
    ("P07-3", "Retrieval gaps are disclosed (new lead, unregistered company, empty sections)",
     T("test_orchestrator::test_new_lead_has_explicit_no_relationship_gap",
       "test_orchestrator::test_unknown_company_is_externally_grounded_with_internal_gap",
       "test_disclosures::test_empty_section_must_be_explained",
       "test_disclosures::test_research_gaps_become_required_disclosures")),
    # Prompt 07 step 4: reproducibility and repository hygiene
    ("P07-4", "Tracked files contain no credentials, personal data, databases or runtime records; .env, runs/, "
              "chroma_db/ and classroom/ are gitignored", artifact("tracked_files_scan")),
    ("P07-4", "Every third-party import in tracked code is pinned in requirements.txt", artifact("requirements_pins")),
    ("P07-4", "Clean checkout follows the README: tests, corpus regeneration, index build, app start, rehearsal",
     manual("MC-03")),
    # Prompt 07 step 5: saved versus live, offline behaviour, demo rehearsal
    ("P07-5", "Offline rehearsal with network blocked: saved SIMULATED demo keeps its date and label; three curated "
              "companies, an arbitrary and an ambiguous company behave as documented; repeat request reuses result",
     artifact("demo_rehearsal")),
    ("P07-5", "Saved demo and cached results are never shown as fresh; history snapshots are never refreshed",
     T("test_app::test_saved_demo_keeps_original_date_and_simulated_label",
       "test_app::test_streamlit_loads_saved_demo_without_research",
       "test_app::test_streamlit_page_runs_once_and_reruns_do_not_research_again",
       "test_history::test_saved_briefing_snapshot_reopens_unchanged")),
]


# --- execution ---------------------------------------------------------------------------------

def run(cmd: list[str]) -> subprocess.CompletedProcess:
    env = {**os.environ, **OFFLINE_ENV}
    return subprocess.run(cmd, cwd=ROOT, env=env, capture_output=True, text=True, encoding="utf-8", errors="replace")


def junit_outcomes(path: Path) -> dict[str, str]:
    """{"<file>::<test name with params>": passed|failed|error|skipped|xfailed}"""
    out = {}
    for case in ET.parse(path).iter("testcase"):
        file = case.get("classname").split(".")[-1]
        status = "passed"
        for child in case:
            if child.tag == "skipped" and child.get("type") == "pytest.xfail":
                status = "xfailed"  # a strict xfail: a known defect reproduced in this run
            elif child.tag in ("failure", "error", "skipped"):
                status = {"failure": "failed"}.get(child.tag, child.tag)
        out[f"{file}::{case.get('name')}"] = status
    return out


def tests_status(hits: dict[str, str]) -> str:
    values = set(hits.values())
    if values & {"failed", "error", "xfailed"}:
        return "FAIL"
    return "NOT TESTED" if values & {"skipped"} or not hits else "PASS"


def tests_detail(selectors: list[str], hits: dict[str, str]) -> str:
    passed = sum(v == "passed" for v in hits.values())
    known = sum(v == "xfailed" for v in hits.values())
    return (f"{passed}/{len(hits)} test cases passed" + (f", {known} known defect(s) reproduced (strict xfail)"
                                                          if known else "")
            + ": " + ", ".join(s.replace("test_", "", 1) for s in selectors))


def match(selector: str, outcomes: dict[str, str]) -> dict[str, str]:
    return {k: v for k, v in outcomes.items() if k == selector or k.startswith(selector + "[")}


def load_run(name: str) -> dict:
    return json.loads((RUNS / f"{name}.json").read_text(encoding="utf-8"))


def pdf_pages(name: str) -> int:
    from pypdf import PdfReader
    return len(PdfReader(RUNS / name).pages)


ARTIFACT_BLOCKERS = {"corpus_size": "deviation", "live_three_demos": "live"}  # otherwise a non-PASS is a defect


def recall(fraction: str) -> float:
    hits, n = fraction.split("/")
    return int(hits) / int(n)


def free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def streamlit_startup(ctx: dict) -> tuple[bool, str]:
    """Start the app headless on a free local port (temporary history DB), check health and page, stop it."""
    port = free_port()
    cmd = [sys.executable, "-m", "streamlit", "run", "app/streamlit_app.py", "--server.headless", "true",
           "--server.address", "127.0.0.1", "--server.port", str(port), "--browser.gatherUsageStats", "false"]
    ctx["commands"].append(" ".join(["python", *cmd[1:]]))
    with tempfile.TemporaryDirectory() as tmp:
        env = {**os.environ, **OFFLINE_ENV, "DEAL_PREP_HISTORY_DB": str(Path(tmp) / "history.sqlite")}
        proc = subprocess.Popen(cmd, cwd=ROOT, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        health, page, started = None, None, time.monotonic()
        try:
            while time.monotonic() - started < 90 and health != "ok":
                try:
                    health = urllib.request.urlopen(f"http://127.0.0.1:{port}/_stcore/health", timeout=2).read().decode()
                except OSError:
                    time.sleep(1)
            if health == "ok":
                page = urllib.request.urlopen(f"http://127.0.0.1:{port}/", timeout=5).status
        finally:
            proc.terminate()
            proc.wait(timeout=30)
    elapsed = time.monotonic() - started
    return health == "ok" and page == 200, (f"health {health!r}, page HTTP {page}, ready after {elapsed:.1f} s, "
                                            "server stopped. Page script execution is covered by the AppTest rows.")


def live_run_criteria(name: str, kind: str) -> tuple[list[str], dict]:
    """Option B acceptance criteria for one recorded live briefing. Returns (failed criteria, measurements)."""
    text = (RUNS / f"{name}.json").read_text(encoding="utf-8")
    d = json.loads(text)
    ev, items = d["evidence"], d.get("briefing") or {}
    stages = {s["stage"] for s in d["trace_stages"]}
    cited = lambda section: [(it, ev.get(i)) for it in items.get(section, []) for i in it["evidence_ids"]]  # noqa: E731
    gaps = " ".join(x["text"] for x in d.get("disclosures") or [])
    pages = {lang: pdf_pages(f"{name}_{lang}.pdf") if (RUNS / f"{name}_{lang}.pdf").exists() else 0
             for lang in ("en", "he")}
    u = d["usage"]
    checks = {
        "mandatory research ran": {"internal_rag", "external_news"} <= stages,
        "honest status, 0 citation issues": d["status"] in ("briefing_ready", "partial_briefing")
                                            and not d["citation_issues"],
        "recent developments cite dated news only": all(
            e and e["evidence_id"].startswith("WEB-") and e["time_window"] in ("last_48h", "last_30_days")
            for it, e in cited("recent_developments") if it["kind"] == "fact"),
        "provenance labels complete": all(e["provenance_label"].startswith(("PUBLIC SOURCE", "SYNTHETIC"))
                                          for e in ev.values())
                                      and all("http" in e["provenance_label"] and "retrieved" in e["provenance_label"]
                                              for e in ev.values() if e["evidence_id"].startswith("WEB-")),
        "real-world facts cite public sources only": all(
            e and e["info_origin"] == "public_source" for s in items for it, e in cited(s)
            if it.get("claim_type") in ("real_world_fact", "public_pricing")),
        "limits held": u.get("openai_actual_usd", 1) <= OPTION_B_LIMITS["usd_per_briefing"]
                       and u["tavily_credits"] <= OPTION_B_LIMITS["credits_per_briefing"]
                       and len(d["agent"]["history"]) <= 3,
        "no key-like strings": not KEY_LIKE.search(text),
        "one-page EN and HE PDFs": pages == {"en": 1, "he": 1},
        "measurements recorded": bool(d.get("total_ms")) and "input_tokens" in u,
    }
    rel = [(e or {}).get("customer_org_id") for it, e in cited("our_relationship")]
    if kind == "shikun_binui":
        checks["relationship cites this customer's synthetic records only"] = bool(rel) and all(
            c == "shikun_binui" for c in rel) and all(e["info_origin"] == "synthetic_record"
                                                      for _, e in cited("our_relationship"))
    elif kind == "ashtrom":
        checks["no invented relationship; gap disclosed"] = not items.get("our_relationship") and \
            "No prior relationship records" in gaps
    elif kind == "skanska":
        ident = d["identity"] or {}
        checks["identified as unregistered, name only"] = ident.get("org_id") is None and \
            ident.get("confidence") == "name_only"
        checks["no internal customer history; gap disclosed"] = not items.get("our_relationship") and \
            not any(e.get("customer_org_id") for e in ev.values()) and "No internal records for 'Skanska'" in gaps
        checks["every news item names Skanska (no ambiguous match)"] = all(
            "skanska" in (e["provenance_label"] + e["excerpt"]).casefold()
            for e in ev.values() if e["evidence_id"].startswith("WEB-"))
    failed = [k for k, ok in checks.items() if not ok]
    return failed, {"company": d["company"], "status": d["status"], "seconds": round(d["total_ms"] / 1000, 1),
                    "usd": u.get("openai_actual_usd"), "credits": u["tavily_credits"],
                    "model_calls": u["model_calls"], "tokens": f"{u['input_tokens']}/{u['output_tokens']}",
                    "agent_calls": len(d["agent"]["history"]), "criteria": len(checks)}


def describe(m: dict, failed: list[str]) -> str:
    return (f"{m['company']}: {m['status']}, {m['criteria'] - len(failed)}/{m['criteria']} criteria met"
            + (f" (failed: {', '.join(failed)})" if failed else "")
            + f"; {m['seconds']} s, OpenAI ${m['usd']}, {m['model_calls']} model calls, tokens in/out {m['tokens']}, "
              f"Tavily {m['credits']} credit(s), agent tool calls {m['agent_calls']}")


def check_artifact(check: str, ctx: dict) -> tuple[str, str, str]:
    """(status, evidence type, detail)"""
    if check == "live_option_b_registry":
        results = {k: live_run_criteria(OPTION_B[k], k) for k in ("shikun_binui", "ashtrom")}
        all_runs = [live_run_criteria(OPTION_B[k], k)[1] for k in OPTION_B]
        usd, credits = sum(m["usd"] for m in all_runs), sum(m["credits"] for m in all_runs)
        within = usd <= OPTION_B_LIMITS["usd_total"] and credits <= OPTION_B_LIMITS["credits_total"]
        ok = within and not any(f for f, _ in results.values())
        return ("PASS" if ok else "FAIL", "recorded live (Option B, not re-run)",
                "; ".join(describe(m, f) for f, m in results.values())
                + f". Option B totals (3 briefings): OpenAI ${usd:.6f} (limit ${OPTION_B_LIMITS['usd_total']:.2f}), "
                  f"Tavily {credits} credits (limit {OPTION_B_LIMITS['credits_total']}).")
    if check == "live_skanska":
        failed, m = live_run_criteria(OPTION_B["skanska"], "skanska")
        return ("PASS" if not failed else "FAIL", "recorded live (Option B, not re-run)",
                f"runs/{OPTION_B['skanska']}.json. " + describe(m, failed))
    if check == "kb_eval_threshold":
        e = ctx["kb_eval"]
        if e is None:
            return "FAIL", "offline run", "scripts/kb_eval.py did not produce a result"
        got = {k: recall(e[k]) for k in RECALL_THRESHOLDS}
        ok = all(got[k] >= v for k, v in RECALL_THRESHOLDS.items())
        return ("PASS" if ok else "FAIL", "offline run",
                f"document {e['doc_recall']} ({got['doc_recall']:.0%}, required 100%); passage {e['passage_recall']} "
                f"({got['passage_recall']:.1%}, required ≥ 90%). Thresholds approved by the owner on 2026-11-06; "
                "R8 passage miss retained as a documented limitation.")
    if check == "saved_demo_citations":
        from deal_prep.app_service import SAVED_MODE_LABEL, load_saved_demo
        from deal_prep.authority import CLAIM_ORIGINS
        d = load_saved_demo()
        problems, cited = [], 0
        for section, items in d["briefing"].items():
            for i, item in enumerate(items):
                for eid in item["evidence_ids"]:
                    cited += 1
                    ev = d["evidence"].get(eid)
                    if ev is None:
                        problems.append(f"{section}[{i}] cites missing {eid}")
                    elif item["kind"] == "fact" and ev["info_origin"] != CLAIM_ORIGINS[item["claim_type"]]:
                        problems.append(f"{section}[{i}] {item['claim_type']} cites {ev['info_origin']} {eid}")
                    elif section == "our_relationship" and ev["info_origin"] != "synthetic_record":
                        problems.append(f"{section}[{i}] relationship cites non-synthetic {eid}")
        if d.get("mode_label") != SAVED_MODE_LABEL or "SIMULATED" not in d["mode_label"]:
            problems.append("SIMULATED saved-demo label missing")
        return ("PASS" if not problems else "FAIL", "offline check of saved data",
                f"data/demo/saved_briefing_shikun_binui.json: {cited} citations checked, created_at "
                f"{d['created_at']}; problems: {'; '.join(problems) or 'none'}")
    if check == "render_pdfs":
        from deal_prep.app_service import load_saved_demo
        from deal_prep.pdf_export import build_pdf
        d = load_saved_demo()
        out = RUNS / "acceptance_pdfs"
        out.mkdir(exist_ok=True)
        pages = {}
        for lang in ("en", "he"):
            data, info = build_pdf(d, d.get("generation_label", ""), lang)
            (out / f"saved_demo_{lang}.pdf").write_bytes(data)
            pages[lang] = pdf_pages(f"acceptance_pdfs/saved_demo_{lang}.pdf")
        return ("PASS" if all(p == 1 for p in pages.values()) else "FAIL", "offline run",
                f"runs/acceptance_pdfs/saved_demo_en.pdf {pages['en']} page, saved_demo_he.pdf {pages['he']} page")
    if check == "streamlit_startup":
        ok, detail = streamlit_startup(ctx)
        return "PASS" if ok else "FAIL", "offline run", detail
    if check == "tracked_files_scan":
        # This script holds the search pattern itself, so it is excluded here and checked separately below
        # for key-shaped values only.
        secrets = run(["git", "grep", "-nIE", r"sk-[A-Za-z0-9_-]{16,}|tvly-[A-Za-z0-9_-]{10,}|sb_secret_|"
                       r"eyJ[A-Za-z0-9_-]{20,}\.|(OPENAI|TAVILY|SUPABASE)[A-Z_]*KEY *= *[^ #\r\n]+",
                       "--", ".", ":(exclude)scripts/acceptance_report.py"]).stdout.splitlines()
        own = re.findall(r"(?:sk|tvly)-[A-Za-z0-9_-]{16,}|eyJ[A-Za-z0-9_-]{20,}\.",
                         Path(__file__).read_text(encoding="utf-8"))
        real = [s for s in secrets if not re.search(r"NOT-REAL|NOT-A-REAL|FAKE|LEAKED|TEST", s)] + own
        emails = run(["git", "grep", "-nIoE", r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[a-z]{2,}"]).stdout.splitlines()
        tracked = [p for p in run(["git", "ls-files"]).stdout.splitlines()
                   if re.search(r"(^|/)\.env$|\.sqlite|\.db$|^runs/|^chroma_db/|^classroom/|\.zip$", p)]
        ignored = run(["git", "check-ignore", ".env", "runs/history.sqlite", "chroma_db", "classroom"]).stdout.split()
        ok = not real and not emails and not tracked and len(ignored) == 4
        return ("PASS" if ok else "FAIL", "offline scan (git grep)",
                f"key-like strings {len(secrets)} (all test fakes: {not real}), email addresses {len(emails)}, "
                f"forbidden tracked paths {len(tracked)}, ignored {len(ignored)}/4 (.env, runs/, chroma_db, classroom)")
    if check == "requirements_pins":
        import ast
        import importlib.metadata as md
        pinned = {re.split(r"[=<>]", line.strip())[0].lower()
                  for line in (ROOT / "requirements.txt").read_text(encoding="utf-8").splitlines()
                  if line.strip() and not line.strip().startswith("#")}
        local = {"deal_prep", "conftest"} | {p.stem for p in (ROOT / "tests").glob("test_*.py")}
        dists, missing, used = md.packages_distributions(), set(), set()
        for f in run(["git", "ls-files", "*.py"]).stdout.split():
            for node in ast.walk(ast.parse((ROOT / f).read_text(encoding="utf-8"))):
                names = ([a.name for a in node.names] if isinstance(node, ast.Import) else
                         [node.module] if isinstance(node, ast.ImportFrom) and node.level == 0 and node.module else [])
                for n in names:
                    top = n.split(".")[0]
                    if top in sys.stdlib_module_names or top in local:
                        continue
                    dist = (dists.get(top) or [top])[0]
                    used.add(dist)
                    if dist.lower() not in pinned:
                        missing.add(dist)
        pip = run([sys.executable, "-m", "pip", "check"]).stdout.strip()
        ok = not missing and "No broken requirements" in pip
        return ("PASS" if ok else "FAIL", "offline audit",
                f"{len(used)} third-party distributions imported; unpinned: {', '.join(sorted(missing)) or 'none'}; "
                f"pip check: {pip}")
    if check == "demo_rehearsal":
        ctx["commands"].append("python scripts/demo_rehearsal.py")
        before = set(RUNS.glob("demo_rehearsal_*.json"))
        proc = run([sys.executable, "scripts/demo_rehearsal.py"])
        new = sorted(set(RUNS.glob("demo_rehearsal_*.json")) - before)
        if not new:
            return "FAIL", "offline run", f"no rehearsal record (exit {proc.returncode})"
        rec = json.loads(new[-1].read_text(encoding="utf-8"))
        statuses = "; ".join(f"{s['scenario']}: {s['status']}" for s in rec["scenarios"])
        return ("PASS" if proc.returncode == 0 and rec["failed"] == 0 else "FAIL", "offline run",
                f"{rec['passed']} checks passed, {rec['failed']} failed, record runs/{new[-1].name}. {statuses}")
    if check == "corpus_size":
        n = ctx["corpus_documents"]
        return ("PASS" if 30 <= n <= 50 else "FAIL", "repository data",
                f"{n} documents in data/kb_v1/manifest.json ({ctx['corpus_breakdown']}). The expansion to about 30 "
                "was deferred by owner decision during Gate 2B.")
    if check == "kb_eval":
        e = ctx["kb_eval"]
        if e is None:
            return "FAIL", "offline run", "scripts/kb_eval.py did not produce a result"
        bad = [k for part in ("provenance", "authority") for k, v in e[part].items() if not v["pass"]]
        misses = [r["id"] for r in e["retrieval"] if r["passage_rank"] is None]
        return ("PASS" if ctx["kb_eval_exit"] == 0 and not bad else "FAIL", "offline run",
                f"Document Recall@{e['k']} {e['doc_recall']}, passage Recall@{e['k']} {e['passage_recall']}"
                f" (passage misses: {', '.join(misses) or 'none'}); provenance/authority cases failing: "
                f"{', '.join(bad) or 'none'}; record {ctx['kb_eval_file']}")
    if check == "live_news_check":
        d = load_run(LIVE_NEWS_CHECK)
        ok = d["status"] == "found_48h" and d.get("evidence")
        return ("PASS" if ok else "FAIL", "recorded live (not re-run)",
                f"runs/{LIVE_NEWS_CHECK}.json: {d['company']}, status {d['status']}, window {d.get('window_used')}, "
                f"{len(d.get('evidence') or [])} evidence items, requests sent {d.get('requests_sent')}")
    if check == "live_agent_bounds":
        rows = []
        ok = True
        for name in (LIVE_NO_NEWS, LIVE_BRIEFING):
            d = load_run(name)
            calls = d["usage"]["model_calls"]["agent"]
            agent = d.get("agent") or {}
            optional = agent.get("calls_used", len(agent.get("history", [])))  # live records keep only history
            spent = d["usage"].get("openai_actual_usd")
            ok &= optional is not None and optional <= 3 and spent is not None and spent <= 0.10
            rows.append(f"{name}: optional tool calls {optional} (agent status {agent.get('status')}), "
                        f"agent decisions {calls}, OpenAI ${spent}")
        return "PASS" if ok else "FAIL", "recorded live (not re-run)", "; ".join(rows)
    if check == "live_briefing":
        d = load_run(LIVE_BRIEFING)
        sections = d.get("briefing") or {}
        pages = {lang: pdf_pages(f"{LIVE_BRIEFING}_{lang}.pdf") for lang in ("en", "he")}
        ok = (d["status"] == "briefing_ready" and all(s in sections for s in SECTIONS)
              and not d.get("citation_issues") and all(p == 1 for p in pages.values()))
        return ("PASS" if ok else "FAIL", "recorded live (not re-run)",
                f"runs/{LIVE_BRIEFING}.json ({d['company']}): status {d['status']}, sections "
                f"{sum(s in sections for s in SECTIONS)}/6, citation issues {len(d.get('citation_issues') or [])}, "
                f"PDF pages EN {pages['en']} / HE {pages['he']}")
    if check == "live_three_demos":
        runs = [load_run(n) for n in (LIVE_BRIEFING, OPTION_B["shikun_binui"], OPTION_B["ashtrom"])]
        companies = sorted({r["company"] for r in runs})
        detail = "; ".join(f"{r['company']} {r['status']}: {r['total_ms'] / 1000:.1f} s, OpenAI "
                           f"${r['usage'].get('openai_actual_usd')}, model calls {r['usage']['model_calls']}, "
                           f"Tavily credits {r['usage']['tavily_credits']}" for r in runs)
        measured = len(companies) == 3 and all(r.get("total_ms") and r["usage"].get("openai_actual_usd") is not None
                                               for r in runs)
        seconds = sorted(r["total_ms"] / 1000 for r in runs)
        return ("PASS" if measured else "NOT TESTED", "recorded live",
                f"All three demonstration companies measured live with news: {detail}. Observed {seconds[0]:.1f}–"
                f"{seconds[-1]:.1f} s per briefing, so the instructor's 'within seconds' aspiration is not met in "
                "live mode; it is reported as a measurement, not a promise.")
    if check == "live_no_keys":
        names = [f"{n}.json" for n in (LIVE_NO_NEWS, LIVE_BRIEFING, LIVE_NEWS_CHECK, *OPTION_B.values())]
        hits = {n: len(KEY_LIKE.findall((RUNS / n).read_text(encoding="utf-8"))) for n in names}
        return ("PASS" if not any(hits.values()) else "FAIL", "recorded live (scanned now)",
                "key-like matches: " + ", ".join(f"{n} {c}" for n, c in hits.items()))
    if check == "eval_set":
        cases = ctx["cases"]
        by = {s: sum(c["status"] == s for c in cases) for s in ("PASS", "FAIL", "NOT TESTED")}
        offline = [c for c in cases if c["mode"] == "offline"]
        executed = all(c["status"] != "NOT TESTED" for c in offline)
        categories = len({c["category"] for c in cases})
        return ("PASS" if len(offline) >= 20 and executed else "FAIL", "offline run",
                f"eval/acceptance_cases_v1.json: {len(cases)} cases in {categories} categories, every offline case "
                f"executed in this run ({by['PASS']} PASS, {by['FAIL']} FAIL, {by['NOT TESTED']} NOT TESTED; any "
                "NOT TESTED case needs live API calls). Plus 25 knowledge-base cases in eval/cases_v1.json (kb_eval).")
    raise ValueError(check)


def evaluate_cases(outcomes: dict[str, str], ctx: dict, unmatched: list[str]) -> list[dict]:
    spec = json.loads(CASES.read_text(encoding="utf-8"))
    rows = []
    for c in spec["cases"]:
        row = {k: c[k] for k in ("id", "category", "mode", "description")}
        if c["mode"] == "live" and c.get("recorded_live"):  # an owner-authorized live run was recorded
            status, _, detail = check_artifact(c["recorded_live"], ctx)
            row.update(status=status, detail=f"Recorded live run: {detail}")
        elif c["mode"] == "live":
            row.update(status="NOT TESTED", detail=f"Requires live API calls ({c['requires']}).", blocker="live")
        elif "kb_eval" in c:
            e = ctx["kb_eval"]
            got = recall(e[c["kb_eval"]]) if e else 0.0
            row.update(status="PASS" if got >= RECALL_THRESHOLDS[c["kb_eval"]] else "FAIL",
                       detail=f"kb_eval {c['kb_eval']} {e[c['kb_eval']] if e else 'missing'} "
                              f"(threshold {RECALL_THRESHOLDS[c['kb_eval']]:.0%})")
        else:
            hits = {}
            for sel in c["tests"]:
                m = match(sel, outcomes)
                if not m:
                    unmatched.append(f"{c['id']}: {sel}")
                hits.update(m)
            row.update(status=tests_status(hits), detail=tests_detail(c["tests"], hits))
        if row["status"] != "PASS":
            row.setdefault("blocker", "defect")
        rows.append(row)
    return rows


def corpus_counts() -> tuple[int, str]:
    manifest = json.loads((ROOT / "data" / "kb_v1" / "manifest.json").read_text(encoding="utf-8"))
    docs = manifest["documents"] if isinstance(manifest, dict) else manifest
    by = {}
    for d in docs:
        by[d["info_origin"]] = by.get(d["info_origin"], 0) + 1
    return len(docs), ", ".join(f"{k} {v}" for k, v in sorted(by.items()))


def main() -> int:
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    RUNS.mkdir(exist_ok=True)
    junit = RUNS / f"acceptance_{ts}_junit.xml"
    py = sys.executable
    commands = []

    cmd = [py, "-m", "pytest", "-q", "-p", "no:cacheprovider", f"--junitxml={junit.relative_to(ROOT)}"]
    commands.append(" ".join(["python", *cmd[1:]]))
    tests = run(cmd)
    summary = tests.stdout.strip().splitlines()[-1] if tests.stdout.strip() else "(no output)"
    outcomes = junit_outcomes(junit)

    before = set(RUNS.glob("kb_eval_*.json"))
    cmd = [py, "scripts/kb_eval.py"]
    commands.append("python scripts/kb_eval.py")
    ev = run(cmd)
    new = sorted(set(RUNS.glob("kb_eval_*.json")) - before)
    kb_eval = json.loads(new[-1].read_text(encoding="utf-8")) if new else None

    n_docs, breakdown = corpus_counts()
    ctx = {"kb_eval": kb_eval, "kb_eval_exit": ev.returncode, "kb_eval_file": new[-1].name if new else None,
           "corpus_documents": n_docs, "corpus_breakdown": breakdown, "commands": commands}
    unmatched = []
    ctx["cases"] = evaluate_cases(outcomes, ctx, unmatched)
    checks = {c["id"]: c for c in json.loads(MANUAL.read_text(encoding="utf-8"))["checks"]}

    rows = []
    for rid, criterion, evidence in CRITERIA:
        row = {"id": rid, "criterion": criterion}
        if evidence["kind"] == "tests":
            hits = {}
            for sel in evidence["tests"]:
                m = match(sel, outcomes)
                if not m:
                    unmatched.append(sel)
                hits.update(m)
            row.update(status=tests_status(hits), evidence_type="automated offline",
                       detail=tests_detail(evidence["tests"], hits), tests=hits)
        elif evidence["kind"] == "artifact":
            status, etype, detail = check_artifact(evidence["check"], ctx)
            row.update(status=status, evidence_type=etype, detail=detail)
            if status != "PASS":
                row["blocker"] = ARTIFACT_BLOCKERS.get(evidence["check"], "defect")
        elif evidence["kind"] == "manual":
            mc = checks[evidence["id"]]
            # The matrix uses PASS / FAIL / NOT TESTED; a qualified manual result is PASS with its limitations stated.
            qualified = mc["result"] == "PASS WITH LIMITATIONS"
            row.update(status="PASS" if qualified else mc["result"], evidence_type=f"manual ({mc['reviewer']})",
                       detail=(f"{mc['id']} on {mc['date']}, eval/manual_checks_v1.json, recorded as {mc['result']}"
                               + (f" ({' '.join(mc['limitations'])})" if qualified else "") + ". "
                               + (f"Owner review: {mc['owner_review']} " if mc.get("owner_review") else "")
                               + " ".join(mc["findings"])))
        else:
            row.update(status=evidence["status"], evidence_type="none", detail=evidence["reason"],
                       blocker=evidence["blocker"])
        if row["status"] != "PASS":
            row.setdefault("blocker", "defect")
        rows.append(row)
    if unmatched:
        print("Mapping error: these selectors matched no executed test:\n  " + "\n  ".join(unmatched))
        return 2

    counts = {s: sum(r["status"] == s for r in rows) for s in ("PASS", "FAIL", "NOT TESTED")}
    case_counts = {s: sum(c["status"] == s for c in ctx["cases"]) for s in ("PASS", "FAIL", "NOT TESTED")}
    suite = {s: sum(v == s for v in outcomes.values()) for s in ("passed", "failed", "error", "skipped", "xfailed")}
    head = run(["git", "rev-parse", "--short", "HEAD"]).stdout.strip()
    dirty = run(["git", "status", "--porcelain"]).stdout.strip().splitlines()
    import chromadb
    import streamlit
    env = {"python": platform.python_version(), "platform": platform.platform(), "chromadb": chromadb.__version__,
           "streamlit": streamlit.__version__}
    record = {"run_at_utc": ts, "git_head": head, "uncommitted_paths": dirty, "environment": env,
              "commands": commands, "pytest_summary": summary, "pytest_counts": suite, "junit": junit.name,
              "kb_eval_exit": ev.returncode, "kb_eval_record": ctx["kb_eval_file"], "status_counts": counts,
              "case_counts": case_counts, "criteria": rows, "cases": ctx["cases"]}
    (RUNS / f"acceptance_{ts}.json").write_text(json.dumps(record, indent=1, ensure_ascii=False), encoding="utf-8")
    REPORT.write_text(render(record), encoding="utf-8")
    print(f"pytest: {summary}")
    print(f"kb_eval exit code: {ev.returncode}")
    print(f"criteria: {counts}")
    print(f"acceptance cases: {case_counts}")
    print(f"Saved: docs/{REPORT.name}, runs/acceptance_{ts}.json, runs/{junit.name}")
    return 0


def render(r: dict) -> str:
    lines = [
        "# Deal-Prep Copilot — Acceptance Test Report (Prompt 07)",
        "",
        f"**Generated:** {r['run_at_utc']} UTC by `scripts/acceptance_report.py` (regenerate it, don't edit it by hand).  ",
        f"**Code:** git `{r['git_head']}`"
        + (f", plus {len(r['uncommitted_paths'])} uncommitted path(s) at run time" if r["uncommitted_paths"] else "")
        + ".  ",
        f"**Environment:** Python {r['environment']['python']}, chromadb {r['environment']['chromadb']}, "
        f"streamlit {r['environment']['streamlit']}, {r['environment']['platform']}.  ",
        "**Paid calls in this run:** none. OpenAI and Tavily were not called and `.env` was not read "
        "(`DEAL_PREP_NO_DOTENV=1`, Hugging Face offline).",
        "",
        "## How statuses are assigned",
        "",
        "- **PASS (automated offline):** every mapped test case was executed in this run and passed. Simulated "
        "models and news are used; these rows do not prove live-provider behaviour.",
        "- **PASS (recorded live):** checked now from the saved output of an earlier owner-authorized live run. "
        "The live run was not repeated.",
        "- **PASS (manual):** an inspection recorded in `eval/manual_checks_v1.json`, with reviewer and date.",
        "- **FAIL:** a mapped test failed, a strict-xfail test reproduced a known defect, an artifact check failed, "
        "or the requirement is knowingly not met.",
        "- **NOT TESTED:** no executed evidence exists yet; the reason is given.",
        "- Existing code or test definitions alone never count as a PASS.",
        "- AT-07 thresholds (owner-approved 2026-11-06): document Recall@5 = 100%, passage Recall@5 ≥ 90%.",
        "",
        "## Commands executed",
        "",
        *[f"- `{c}`" for c in r["commands"]],
        "",
        f"**pytest:** {r['pytest_summary']} (JUnit record `runs/{r['junit']}`: "
        + ", ".join(f"{k} {v}" for k, v in r["pytest_counts"].items()) + ").  ",
        f"**kb_eval:** exit code {r['kb_eval_exit']}, record `runs/{r['kb_eval_record']}`.",
        "",
        "## Summary",
        "",
        "| Status | Requirement criteria | Acceptance cases (AT-20) |\n|---|---|---|\n"
        + "\n".join(f"| {k} | {v} | {r['case_counts'][k]} |" for k, v in r["status_counts"].items()),
        "",
        "## Remaining blockers",
        "",
    ]
    for key, title in BLOCKERS.items():
        items = [x for x in r["criteria"] if x.get("blocker") == key and x["status"] != "PASS"]
        items += [{"id": c["id"], "criterion": c["description"], "status": c["status"], "detail": c["detail"]}
                  for c in r["cases"] if c.get("blocker") == key and c["status"] != "PASS"]
        lines += [f"### {title}: {len(items)}", ""]
        lines += [f"- **{x['id']}** ({x['status']}): {x['criterion']}. {x['detail']}" for x in items] or ["- none"]
        lines.append("")
    lines += [
        "## Requirements matrix",
        "",
        "| Req. | Criterion | Status | Evidence type | Evidence |",
        "|---|---|---|---|---|",
    ]
    for row in r["criteria"]:
        detail = row["detail"].replace("|", "\\|")
        lines.append(f"| {row['id']} | {row['criterion']} | **{row['status']}** | {row['evidence_type']} | {detail} |")
    lines += [
        "",
        "## Acceptance case set (AT-20, `eval/acceptance_cases_v1.json`)",
        "",
        "| Case | Category | Mode | Description | Status | Evidence |",
        "|---|---|---|---|---|---|",
    ]
    for c in r["cases"]:
        lines.append(f"| {c['id']} | {c['category']} | {c['mode']} | {c['description']} | **{c['status']}** | "
                     f"{c['detail'].replace('|', chr(92) + '|')} |")
    lines += [
        "",
        "## Known limitations (full list: `docs/KNOWN_LIMITATIONS.md`)",
        "",
        "- Intermittent Chroma 1.1.1 error \"Error creating hnsw segment reader: Nothing found on disk\": seen on "
        "2026-11-06 (1 test) and 2026-11-08 (2 tests in one full offline run). Confirmed on 2026-11-08: the failing "
        "operation is the knowledge-base query (`dms_kb_v1`) right after a meeting-history write in the same index "
        "folder. The cause is unconfirmed and the knowledge-base search has no retry (limitation 15). A passing run, "
        "such as this one, does not show that the error is gone.",
        "- Live rows are checked from recorded owner-authorized runs (Arup; the Option B runs for Shikun & Binui, "
        "Ashtrom Group and Skanska). Nothing was re-run live for this report.",
        "- Manual checks MC-01 to MC-05 were performed by Claude Code (AI assistant). Owner review (2026-11-09): "
        "MC-01, MC-02 and MC-04 approved with comments, MC-05 approved with limitations; MC-03 reviewed on "
        "2026-11-06. Citation support (MC-02, MC-04) is not proof of good reasoning; the owner's comments are kept "
        "in `eval/manual_checks_v1.json`.",
        "- Owner's manual demo walkthrough (MC-06, 2026-11-09): all six demonstrations in `docs/DEMO_GUIDE.md` passed "
        "their intended workflow checks, offline. In Demo 5 the approved meeting appeared in the new briefing, but "
        "its follow-up tasks and their updated status were cut off before drafting (limitation 24). MC-06 is recorded "
        "evidence only; it is not mapped to a requirement criterion and does not change the counts above.",
        "- The recorded live Arup PDFs predate commit eb066d8, so their conflict line uses the older generic wording.",
        "",
        "Readiness is not assessed here (see `docs/READINESS_ASSESSMENT.md`, written on 2026-11-06).",
        "",
    ]
    return "\n".join(lines)


if __name__ == "__main__":
    sys.exit(main())
