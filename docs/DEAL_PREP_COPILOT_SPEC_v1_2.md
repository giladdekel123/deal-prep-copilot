# Deal-Prep Copilot — Consolidated Project Specification

**Version:** 1.2: approved interview baseline, agent-design safeguards (v1.1), plus a provenance-separated knowledge base and owner decisions from 5 November 2026 (v1.2)  
**Date:** 5 November 2026  
**Project:** Separate classroom exercise; **not** a replacement for the AI Developers Course final project  
**Current stage:** Gate 01 approved and frozen as local commit `3de0be9`; Prompt 02 not started  
**Owner:** Student/project owner; implementation assistance via Claude Code after specification approval

## 1. Executive summary

Build a **working, professionally demonstrable** AI application to help a fictional B2B document-management software (DMS) vendor prepare for meetings with prospective or existing customers. A user enters a real company's name and optionally selects a meeting purpose. The application combines relevant internal knowledge retrieved with RAG, live web research, and (when available) approved meeting history into a **source-supported, one-page strategic briefing** available on screen and as a PDF.

A single AI agent can commission bounded supplementary research after the application has performed required internal and external searches. The application is built locally using Python and Streamlit, with Chroma for internal vector retrieval and SQLite for meeting history. An OpenAI-first model strategy is chosen, subject to validating current API compatibility and costs; Tavily is the instructor-provided web-search provider for classroom development; production suitability remains subject to implementation testing.

The first deliverable is the briefing engine; a lightweight meeting-history and follow-up module comes later. The knowledge base holds two kinds of documents, and every document, passage and evidence item states which kind it is (§6B):
- about 30–50 **synthetic records**: the fictional vendor *Nivarque Document Systems*, its fictional competitor *Solquend Archive Systems*, and invented relationship histories with the demo companies;
- **verified, dated public-source snapshots** about three selected real companies (two Israeli, one international).

Users can also enter any real company name. **Synthetic information is never presented as a real business fact.**

## 2. Sources and requirement provenance

**Instructor-provided material:** `deal_prep_copilot_class1_en.html` and `deal_prep_copilot_class1_he.html`, supplied with the class announcement.

The instructor's brief describes a fast-growing B2B vendor and requests:
- Internal RAG over proprietary-style documents (e.g., pricing sheets, competitor battle cards, historical proposals).
- An AI agent capable of invoking web search for news and press releases from the last **48 hours**.
- A **customized one-page strategic briefing** combining internal and external information.
- An **optional** machine-learning win-probability prediction bonus.
- Class 1 planning: RAG architecture, agent tool calling, roadmap, data schemas, initial prompts; not final implementation code.

**Our additional project decisions**, including company scenario, PDF download, structured evaluation, bilingual support, history, task tracking, and three-page UI, are **not** instructor-mandated features. The instructor's aspirational “within seconds” expectation is preserved as an objective to measure, not a verified service-level promise.

**Separate project boundary:** Do not merge this exercise with the independent E-Commerce Churn Intelligence final-project specification, repository, code, or deliverables.

**Additional design guidance (not a new instructor requirement):** *AI Agents Made Simple — Cheat Sheet*, Nir Diamant, 2 pp., supplied 4 November 2026. Its central heuristic is to prefer plain code, a single model call or fixed workflow where those suffice; employ an agent only for genuinely result-dependent next actions, with externally checked outcomes and bounded consequences. The source lists 28 decision patterns, not 28 mandatory components.

**Instructor classroom update (3 November 2026):** The instructor distributed a NexaStream sample corpus, an example `.env`, and setup directions for OpenAI, Tavily and Supabase. The project owner chose **NexaStream for classroom learning** and **DMS as the preferred final application scenario**, with reassessment later. Do not mix NexaStream product/pricing data into DMS answers. OpenAI/Tavily/Supabase authenticated connectivity and a dedicated Python 3.11 environment have been verified locally; this does **not** prove real search, generation, vector indexing, or RAG works. Existing approved Decision 29 (Chroma) remains in force for the DMS design unless the owner explicitly authorizes changing it; Supabase may be used for the instructor-aligned classroom slice.

**Owner decisions of 5 November 2026 (v1.2):**

| ID | Decision |
|---|---|
| D1 | The fictional vendor is **Nivarque Document Systems**, and its fictional competitor is **Solquend Archive Systems**. The names "Ledgerline" and "Archivon" survive only in the frozen Prompt 01 baseline. |
| D3 | Public facts about the real demo companies are researched with Claude Code's built-in web research. This uses no project API keys and is not the production search path, which is set in Prompt 03. |
| D10 | Decision 07 is amended (see §3), and this v1.2 is adopted. |
| D11 | **One** Chroma collection (`dms_kb_v1`) with mandatory provenance metadata, checked at insert time, plus filtering. |
| D12–D14 | The verification levels, the short-excerpt storage rule and the label wording in §6B. These are approved. |
| D15 | The Gate 01 baseline is frozen as local commit `3de0be9`. It has no remote. |
| D16 | The `creation_method` vocabulary in §6B. |

**Pending for Gate 2A:**

| ID | Decision |
|---|---|
| D2 | Currency and pricing model |
| D4 | The three demo companies and their synthetic relationship states |
| D5 | How similarly named companies are tested |
| D6 | Corpus size in Prompt 02 |

**Recommended defaults (the owner has not objected):** D7 commits the generated corpus files with their generator; D8 uses `pypdf`, `python-docx`, `openpyxl` and `fpdf2`; D9 keeps the corpus in English.


## 3. Confirmed interview decisions (1–32)

| ID | Topic | Confirmed decision |
|---|---|---|
| 01 | Ambition | Genuine functional, professionally demonstrable prototype; not a production enterprise deployment. |
| 02 | Company type | Fictional B2B business-software vendor. |
| 03 | Product | Document Management Software (DMS). |
| 04 | Customers | General corporations plus engineering/infrastructure, with engineering/infrastructure primary in demos. |
| 05 | Target-company entry | Accept any real company; prepare three reliable demonstration cases. |
| 06 | Briefing content | Six sections: company overview; recent developments; our relationship; opportunities; competitive positioning; meeting recommendations. Cite sources and flag gaps; supporting evidence separate. |
| 07 | Internal repository | **Amended v1.2 (D10):** a fixed, curated corpus of **synthetic records plus verified, dated public-source snapshots**, each labelled by origin; no document-upload UI. *(v1.1: fixed synthetic document corpus.)* |
| 08 | User input | Company name and optional meeting purpose; default general briefing. |
| 09 | Research | Hybrid: mandatory internal RAG and external search; agent may conduct bounded additional research. |
| 10 | News fallback | Search 48 hours first; if nothing relevant is found, search the last 30 days and label dates/age. |
| 11 | Presentation | On-screen one-page briefing plus downloadable PDF; supporting evidence inspectable. |
| 12 | Conflicts | Apply type-specific source authority, currency/validity, and disclose unresolved contradictions. |
| 13 | Evaluation | Structured, repeatable tests of retrieval, factual grounding, and functional operation. |
| 14 | Agent architecture | One AI agent using specialized tools, not a multi-agent crew. |
| 15 | Language | English and Hebrew selectable; English default; proper RTL and bilingual PDF handling. |
| 16 | Demo mix | Two Israeli companies and one international engineering/technology company. |
| 17 | Demo identity timing | Choose actual companies during dataset preparation using explicit selection criteria. |
| 18 | Corpus size | Approximately 30–50 coherent synthetic documents, built progressively. |
| 19 | File formats | PDF, DOCX, XLSX, TXT, MD; exclude scanned/OCR PDFs and highly complex Excel. Preserve table associations. |
| 20 | Deployment | Local-first, cloud-ready architecture; no mandatory cloud launch. |
| 21 | Persistent history | Company profiles, generated briefings, meeting notes and follow-up actions. |
| 22 | History retrieval | Relevant, approved historical meeting information automatically informs new briefings. |
| 23 | Notes workflow | Free-form input → AI-suggested structured record → human review/approval → storage. |
| 24 | Follow-up tasks | Description, optional due date, status Open/In Progress/Completed; manual updates; no reminders. |
| 25 | UX | Three Streamlit pages: Prepare Meeting, Meeting History, Follow-up Tasks. |
| 26 | Build priority | Stage 1: briefing engine first; Stage 2: meeting history and tasks. |
| 27 | API spend | Controlled paid usage; provisional $10–20 total planning ceiling; verify provider costs before paid use. |
| 28 | UI framework | Streamlit, with AI/business logic separated from UI. |
| 29 | Vector storage | Local Chroma. |
| 30 | Structured persistent storage | SQLite for company, meeting, briefing, task records. |
| 31 | AI strategy | OpenAI-first, plus an appropriate web-search service; exact models/search provider unselected. |
| 32 | Acceptance approach | Balanced: meaningful source-supported output, fallback, conflicts, PDFs, repeatable tests; measure, don't guarantee, latency. |

## 4. Users, scenarios, and boundaries

**Primary user:** Sales representative or partnership manager at the fictional DMS provider.  
**Demonstration user:** Project owner/instructor or another reviewer running the local application.

**Core scenario:** Prepare for an introductory meeting, product demo, commercial negotiation or follow-up with a real prospect. The meeting purpose changes research emphasis and recommended questions, but it does not relax source evidence requirements.

**Three stable demo cases:** Two Israeli firms and one international firm, selected later for their accessible public information and plausible DMS needs. Assign distinct fictional relationship states (e.g., new lead, proposal already sent, negotiation), explicitly labeled synthetic.

**Out of scope for initial release:** Corporate SSO/identity integration, live SharePoint/CRM integration, role-based enterprise access, multiuser tenancy, document uploads, automated email/calendar/reminders, full CRM pipeline, OCR, complex spreadsheet computation, enterprise production guarantees and optional predictive win score. Optional ML bonus can be revisited only after core acceptance and an explicit new decision.

## 5. Functional requirements

### 5.1 Stage 1 — Briefing engine (priority)

**FR-01 Inputs.** Require a nonblank company name. Offer an optional meeting-purpose selection, defaulting to general preparation; language selection EN/HE.

**FR-02 Entity disambiguation.** When a name maps to multiple companies or confidence is insufficient, avoid mixing entities; request clarification or display a clear ambiguity warning. Do not claim a company identity that is not supported.

**FR-03 Curated knowledge base (amended v1.2).** Read a fixed, versioned local corpus of ~30–50 documents in PDF, DOCX, XLSX, TXT and MD. It contains **synthetic records** and **public-source snapshots**.

Every document must carry:
- document ID, title, type and approval status
- effective or publication date, where known
- `info_origin` and `creation_method`
- the organizations involved, each with a role; reality is resolved per organization from the registry

Public-source snapshots must also preserve:
- source URL and publisher
- original publication date, or an explicit `unknown`
- retrieval timestamp and verification status
- supporting excerpts and claim-to-excerpt links

All of these rules are defined in §6B.

**FR-04 RAG.** Extract, chunk, embed, index and retrieve documents/passages in local Chroma, returning text and precise source metadata. Preserve meaningful row/column associations from spreadsheets. Prefer retrieval quality over arbitrary chunk volume.

**FR-05 Mandatory research.** For each briefing, run an internal RAG search and an external search. Search 48-hour news first, expanding to 30 days *if no relevant 48-hour results are found*. Give explicit dates; never mislabel 30-day results as 48-hour news.

**FR-06 Agent behavior.** One agent evaluates results and can call bounded additional targeted retrieval/web searches for specific gaps. Tool budgets, timeouts, and iteration limits must prevent runaway calls. The agent cannot silently omit mandatory searches.

**FR-07 Evidence/authority.** Distinguish internal synthetic documents, approved meeting records, and externally verified news. Source-type authority applies by claim type (e.g., current approved price list for current list prices; a company press release for the company's own announcement). Recency alone does not establish authority. Disclose unresolved discrepancies.

**(v1.2) Claim-type origin rule:**
- **Synthetic records cannot prove real-world facts.** Real-world facts about a real organization may be supported **only** by public-source evidence. This includes pricing the organization has publicly disclosed, such as a published price or a public contract value.
- Claims about the **fictional vendor's** products, list prices and negotiated prices, its proposals, its meetings and its invented customer relationships are supported only by synthetic records, which are always labelled synthetic. Public sources cannot support these claims, because no real source describes the fictional vendor.

A citation of the wrong origin is an `origin_violation` and is rejected deterministically.

**FR-08 Briefing generation.** Produce a concise one-page report with: 1) company overview, 2) recent developments, 3) our relationship, 4) potential opportunities, 5) competitive positioning, 6) meeting recommendations. Label observed facts versus AI analysis/recommendations. Do not fabricate company relationships, commercial pricing, meeting history, quotes or news.

**(v1.2) Origin labelling:**
- Every factual claim shows its origin (public source or synthetic record).
- The "Our relationship" section is always marked synthetic.
- Synthetic content is never phrased as a verified real-world fact.

**FR-09 Output.** Display briefing in Streamlit, show evidence details separately, and generate a printable one-page PDF including company, purpose, creation date and readable source references. English LTR / Hebrew RTL, with mixed-direction text tested.

**(v1.2) Origin badges:**
- Screen and PDF show origin badges on claims and evidence.
- The PDF includes a synthetic-data disclaimer.
- Hebrew label wording is agreed at Prompt 05.

**FR-10 Graceful behavior.** If RAG has no matching internal material, say so. If web search fails or returns nothing, say so and distinguish an absence of results from proof of absence. If partial research fails, label the briefing incomplete rather than fabricating its missing part.

**FR-11 Demonstrability.** Support three curated scenarios and arbitrary other real company names. Avoid a design that only works for the curated firms.

### 5.2 Stage 2 — Lightweight meeting management

**FR-12 History storage.** Use SQLite to persist company identity, briefing metadata/content, source snapshot references and timestamps, meeting records, and action items. An old briefing remains visibly dated and is never silently refreshed.

**FR-13 Notes extraction.** Accept free-text meeting notes; propose participants, summary, concerns, decisions, commitments and follow-up items using AI. Nothing becomes an approved historical record without explicit human review and approval; unknown dates/commitments must stay unknown.

**FR-14 Future briefings.** Retrieve relevant approved history for the correct company and incorporate it into new briefings with dates and provenance. Do not treat a historical assertion as established current truth.

**FR-15 Task list.** Store follow-up description, optional due date, and status (`Open`, `In Progress`, `Completed`). Allow manual status updates. Do not send automatic reminders.

**FR-16 UI.** Three pages with consistent company context: Prepare Meeting, Meeting History, Follow-up Tasks.

## 6. Proposed architecture (implementation design, not yet verified)

**Local Streamlit UI** calls an application service that validates inputs, orchestrates minimum research, invokes the single AI agent for supplemental tool use, verifies evidence and structured output, saves permitted artifacts, and renders the briefing/PDF.

**Internal path (v1.2):** curated corpus (synthetic records plus public-source snapshots) → provenance validator → format-specific text/table extractors → chunks with document identifiers, authority and provenance metadata → embeddings → **one** Chroma collection `dms_kb_v1` (insert refuses incomplete provenance) → origin- and company-filtered RAG passages returned as labelled evidence objects.

**External path:** Configured web-search API → result URLs, titles, publication dates and excerpts → date/relevance validation → citation-ready evidence. Confirm date semantics and source retrieval limitations with the eventual provider.

**Agent path:** Structured research context → OpenAI-first LLM with controlled RAG/web tools → bounded optional follow-up lookups → structured draft with evidence IDs → application-level validation → rendered briefing.

**History path (Stage 2):** SQLite approved meeting/briefing/task records → company-scoped retrieval → historical evidence for the briefing. **Do not** insert unapproved AI interpretations into authoritative history.

**Important:** Chroma and SQLite have different jobs. Chroma indexes relevant passages for semantic retrieval; SQLite persists business records, state, and history. Maintain immutable document IDs and version references when indexed material changes.

## 6A. Agent minimalism, responsibility boundaries and execution safety (v1.1)

The following safeguards refine implementation without changing decisions 01–32. They derive from design lessons in the supplied cheat sheet; they are **our engineering rules**, not mandatory instructor additions.

**Use the least autonomous mechanism that works.** Input validation, mandatory internal retrieval, mandatory web search, 48-hour/30-day fallback, date checks, evidence-ID validation, PDF page counting, authorization rules, and persistence are deterministic Python workflows. A model call can synthesize a structured draft from gathered evidence. **The one agent earns its place only when it reviews findings and decides whether to perform a bounded, justified supplementary lookup.** A demonstrated fixed-workflow baseline must remain available for evaluation. If optional agent research adds no measurable value, simplify its use rather than adding agents.

**Agent decision contract.** Given source-labeled evidence and the meeting purpose, the agent may either `finish_research` or request an additional **read-only** `search_internal` or `search_web` operation with a short, logged rationale and an explicit query. Mandatory searches cannot be skipped. Initially cap supplemental operations at **three total tool calls** per briefing; disallow repeated identical failed requests, bound retries/timeouts, and count all attempts toward a clearly documented execution budget. The agent must not call arbitrary code, shell commands, database administration, file writing, email, or privileged Supabase operations.

**Least privilege and prompt-injection boundary.** Retrieved documents, source snippets, websites and previous meeting notes are untrusted data, never authority to change instructions. Give the LLM sanitized, minimal evidence rather than full service credentials or raw privileged clients. Backend code exclusively holds the Supabase secret key; expose only narrowly scoped read-only retrieval tools to the agent. SQLite writes, approvals, task status changes, and PDF saving occur through validated application operations, never through agent-selected arbitrary tools. Limit output and log content to prevent unintended disclosure of keys, private notes, or full retrieved sensitive content.

**Trace and verify outcomes.** Record run ID; stage; tool identifier; sanitized query/parameters; outcome or error class; duration; evidence IDs; supplemental-call count; and usage/cost when measurable. Store only a brief decision reason, **not hidden model reasoning or secrets**. Log successes and failures with redaction. Deterministic checks verify input/schema, source-ID existence, dates and source categories, and the one-page PDF. Actual claim support, nuance and recommendations need a separate evaluated check; an existing citation ID by itself proves nothing.

**Safe retries and writes.** Introduce stable operation IDs/idempotency keys for saving meeting records and creating tasks, with uniqueness safeguards and transactional SQLite writes. Repeated user submits, UI reruns, process restarts or timeouts must not create duplicate commitments. Update the Chroma index from SQLite's approved records only and reconcile stale entries. No irreversible action or authoritative meeting-note approval without user confirmation.

**Bounded evaluation.** Maintain a versioned evaluation set targeting **at least 20 distinct, meaningful cases by final audit**, covering retrieval relevance, price-to-product table links, superseded policies, conflicting evidence, company ambiguity, absent/undated news, false citations, prompt injections, exhausted tool budgets, repeated calls, transient failures and duplicate writes. Mark any case not run as NOT TESTED; do not claim all 20 exist in early stages. Compare the fixed mandatory-workflow-only baseline against the optional agent-assisted path on the *same* fixed cases for coverage/grounding, latency, tool count and observed cost. Keep all agent benefits conditional on measured evidence.

**Cost rule.** Our existing project financial ceiling remains a planning/authorization boundary, not a claim that provider alerts or caps guarantee exact spending. Estimate and record token/search usage per successful briefing, enforce per-run search/tool limits in application code, and seek approval before paid calls. Never reissue a paid request automatically due to a Streamlit rerun.

## 6B. Provenance-separated knowledge base (v1.2)

**Purpose:** keep genuine public information and synthetic records strictly apart, from ingestion through to the PDF. Synthetic information must never appear as a real business fact.

### Organization reality is recorded per organization
- The organization registry (`organizations.json`) is the **only** place reality is recorded: `reality: real | fictional`.
- A document lists the organizations it involves, each with a role (`vendor`, `customer`, `competitor`, `subject`). It does not carry a reality label of its own.
- Evidence objects resolve each organization's reality from the registry. This keeps documents that mention both real and fictional organizations unambiguous.
- Real organizations also record the official domain and the source URLs that establish their identity.

### Origin is recorded per document and per evidence item

`info_origin` has exactly two values: `public_source` or `synthetic_record`. A separate field, `creation_method`, records how the content came about:

| `info_origin` | `creation_method` |
|---|---|
| `public_source` | `curated_snapshot` (Prompt 02), `live_web_retrieval` (Prompt 03) |
| `synthetic_record` | `authored_fixture`, `generated_fixture`, `user_entered_demo` (Prompt 06), `ai_proposed_from_user_notes` (Prompt 06; approval status kept separately) |

### Validator rules (deterministic, run at load time and in tests)
1. A `public_source` document may not reference **any** fictional organization, in any role.
2. A `synthetic_record` that references **any** real organization must carry these, as well as the banner *"SYNTHETIC RECORD — fictional relationship with a real company. Not a real business fact."*:
   - `synthetic_relationship: true`
   - `synthetic_categories`, from: meeting history, proposal, price, customer relationship, correspondence
3. A public source must include:
   - `source_url` (https) and `publisher`
   - `publication_date`, or `unknown`; never replaced by the retrieval date
   - `retrieved_at` and `verification_status`
   - at least one excerpt, with every claim linked to an excerpt
4. Incomplete or invalid provenance blocks indexing.

### Verification levels and storage (D12, D13)
- `verification_status` is one of `primary` (the company's own site or filings, preferred), `corroborated` (two or more independent sources), `single_secondary` or `unverified`.
- Store **short excerpts** (about 50 words or fewer) plus paraphrased claims. Never store full articles.
- A public snapshot is dated "as of its retrieval date" and is never labelled as recent news.

### Labels (D14)
- Public evidence is labelled "PUBLIC SOURCE", with publisher, URL, publication date and retrieval date.
- Synthetic evidence is labelled "SYNTHETIC — not a real business fact", and names each organization with its reality.
- Labels are stored in metadata, not in the embedded text, and are attached deterministically to every retrieval result.

### Storage (D11)
- One collection, `dms_kb_v1`.
- Mandatory flat provenance metadata: `info_origin`, `creation_method`, `vendor_org_id`, `customer_org_id`, `competitor_org_id`, `subject_org_id`, `real_org_ids`, `involves_real_org`, plus the public-source fields.
- Queries filter by origin and company scope.
- A second collection is introduced only if tests show that filtering leaks.

### Prompt 01 baseline
- The four Prompt 01 documents (Ledgerline/Archivon), their manifest, expectations and tests stay byte-for-byte unchanged as a **frozen pipeline-regression fixture**.
- They are labelled "superseded vendor name, Prompt 01 baseline only", and are never indexed into `dms_kb_v1` or used in briefings.

## 7. Draft data contracts (to refine at implementation design)

The following are *conceptual fields*, not frozen JSON/Pydantic schemas.

- **Organization (v1.2): the canonical identity registry.** `org_id`, display name, normalized name, aliases, `reality` (real/fictional), country, official domain, verified identifier, identity source URLs. Identity fields live **only** here.
- **Company (v1.2): the application's runtime prospect or customer record.** It references Organization by ID and holds no identity fields of its own:
  - `company_id` (stable SQLite key, as in v1.1)
  - `org_id`, a foreign key to Organization
  - `input_name`, the name exactly as the user typed it
  - `resolution_status`: `resolved`, `ambiguous` or `unresolved`
  - `identity_confidence`, the confidence of that runtime resolution
  - created and updated timestamps

  For an arbitrary company not yet in the registry (FR-11), identity resolution creates a new Organization entry (`reality: real`, with its identity sources), and Company points to it. If resolution is ambiguous or fails, `org_id` stays null and no identity is assumed.
  - **Backward compatibility:** the v1.1 Company fields map as follows. `company_id` and `identity_confidence` are unchanged. Display name, normalized name, verified identifier or URL, and home country are now read through `org_id` from Organization, and are not stored twice.
- **KnowledgeDocument (v1.2, replaces InternalDocument):** `document_id`, `title`, `file_path`, `file_type`, `doc_type`, `info_origin`, `creation_method`, `organizations[{org_id, role}]`, `document_version`, `issued_at`, `effective_from`, `effective_to`, `approval_status`, `supersedes`/`superseded_by`, `scope` (global/company), `fixture_tag`/`conflict_group`, `language`.
  - Synthetic records about real organizations add `synthetic_relationship` and `synthetic_categories`.
  - Public sources add `source_url`, `publisher`, `publication_date` (nullable, meaning unknown), `retrieved_at`, `verification_status`, `excerpts[]` and `claims[{text, excerpt_id}]`.
- **EvidenceItem (v1.2):** `evidence_id`, `info_origin`, `creation_method`, `organizations[{org_id, role, reality}]`, title, URL or document ID, source date (nullable), retrieved timestamp, passage text, verification status (public sources), target-company match, limitations, deterministic `provenance_label`.
- **Briefing:** `briefing_id`, `company_id`, meeting purpose, language, generated timestamp, research windows/results, six named sections, claim-to-evidence references, warnings, PDF path, source snapshot or immutable references, run status.
- **MeetingRecord:** `meeting_id`, `company_id`, meeting date, participants, original user notes, AI-proposed structure, user-approved structure, approved timestamp, provenance. **(v1.2)** Always `info_origin=synthetic_record`, with `creation_method` set to `user_entered_demo` or `ai_proposed_from_user_notes`.
- **FollowUpTask:** `task_id`, `company_id`, related meeting ID, description, due date nullable, status enum, created/updated timestamps.
- **Run/Usage:** run ID, time, model version, retrieval/search calls, brief redacted decision rationale, per-step outcome/duration, retries, idempotency key for writes, errors, measured latency and observed or estimated cost. Keep credentials and hidden model reasoning out of logs.

**Integrity rules:** Foreign keys and company scoping; approvals explicit; time zones and date precision clear; required citations for factual assertions wherever sources exist; no invisible copying of an old result into a new run; safe paths and file encoding for document ingestion.

## 8. Source hierarchy and factual safeguards

Authority is **claim-dependent**, not a universal ranking:

- Current vendor list pricing: valid, approved pricing sheet outranks an old proposal, unless the claim concerns that proposal's negotiated historical price.
- What happened in a past meeting: approved dated meeting record outranks an unapproved AI notes draft.
- Real target company's announced event: dated primary company release often outranks undated secondary coverage, but do not infer more than the release actually says.
- Two credible contradictory sources: show the disagreement and dates; do not fabricate certainty.
- Synthetic past proposals/customer correspondence: explicitly mark as synthetic demonstration data; never present these historical relationships as verified real-world business dealings.
- **(v1.2)** **Synthetic records cannot prove real-world facts.** Synthetic evidence never supports a real-world claim about a real organization. Example: a synthetic note stating a different headcount loses to the public source and is flagged as conflict fixture C4.
- **(v1.2)** Public sources may support **publicly disclosed pricing**, such as a price a real organization publishes or a public contract value. They never support the fictional vendor's list or negotiated prices, its proposals, or invented customer relationships. Those claims come only from labelled synthetic records.
- **(v1.2)** For recent developments, a dated live-web source (Prompt 03) outranks an older curated snapshot. The conflict is disclosed.

Treat retrieved documents and webpages as **untrusted information**, not executable instructions to the agent; use bounded tools and source-domain safeguards. API keys in environment/secrets configuration, excluded from source control.

## 9. Acceptance and evaluation plan

### Core functional tests (Stage 1)

- **AT-01:** One curated company produces all six briefing sections, each with factual claims traceable to retrieved evidence, and a usable PDF.
- **AT-02:** Input a company outside the three curated cases; mandatory retrieval and live search still run, with clear “no matching internal history” as appropriate.
- **AT-03:** In a controlled fixture with no 48-hour relevant article but a relevant 30-day article, fallback occurs; actual dates and search-window labels are correct.
- **AT-04:** A target with no relevant internal or external material yields visible information gaps, not invented news, relationships or pricing.
- **AT-05:** Two deliberate synthetic pricing/document conflicts lead to source-authority resolution when determinable and visible warning when unresolved.
- **AT-06:** English and Hebrew PDF outputs render correctly, including Hebrew RTL, mixed-language proper nouns and references; one-page layout checked under representative content sizes.
- **AT-07:** RAG returns the expected passages for a fixed small set of questions with documented ground-truth relevant documents; measure Recall@5 and manually inspect failures. Set a numeric target after a baseline run; no invented score in advance.
- **AT-08:** Web-search outage, LLM error and malformed output fail gracefully and preserve explanatory status.
- **AT-09:** Ambiguous company names do not silently combine content from different companies.
- **AT-10:** Track real end-to-end latency, API calls and costs for the three demonstrations. Compare observed performance to the instructor's “within seconds” aspiration; do not advertise an unmeasured guarantee.
- **AT-11:** Out-of-scope malicious instructions inside retrieved content do not override system rules in a small adversarial fixture test.

### Agent-specific evaluation additions (v1.1)

- **AT-16:** On matched fixtures, compare fixed mandatory research against the bounded-agent path; report evidence coverage, groundedness review, tool count, elapsed time and observed cost. Agent superiority is a hypothesis, **not a predetermined PASS**.
- **AT-17:** Enforce at most three optional tool calls, count repeat attempts, reject identical repeated failed calls and fail safely on exhaustion; mandatory searches still run.
- **AT-18:** An injected instruction embedded in a retrieved passage cannot trigger privileged Supabase operations, arbitrary code, outbound data disclosure or meeting-record mutations. Audit available tool interfaces and output logs.
- **AT-19:** For every supplemental tool call, save redacted step-level trace with tool, short purpose, outcome, timing and evidence IDs; no secret/token values or private hidden reasoning.
- **AT-20:** Build up a versioned **20-case target set by the final audit**, with actual runs and PASS/FAIL/NOT TESTED statuses; include regression checks on changes to prompts, extraction, or retrieval settings.
- **AT-21 (Stage 2):** Repeating an approved meeting-save/task-create request with the same operation ID does not duplicate records; crash/retry and stale-index paths remain consistent.

### Provenance acceptance additions (v1.2)

- **AT-22:** Provenance labels survive every stage, from ingestion through index, retrieval, evidence, briefing, screen and PDF. Every evidence object has a complete label.
- **AT-23:** No synthetic content is presented as a real fact in briefings or PDFs. A real-company fact cited to synthetic evidence is rejected as an `origin_violation`.
- **AT-24:** Public evidence keeps its exact source URL, publisher, publication date (or `unknown`), retrieval date and verification status.
- **AT-25:** The validator rejects invalid combinations, including:
  - a public source that references a fictional organization
  - a synthetic record about a real organization without its banner or categories
  - a public source missing its URL or excerpt

  Indexing refuses incomplete provenance.

### History functional tests (Stage 2)

- **AT-12:** Unapproved AI-extracted meeting notes cannot influence future authoritative briefings.
- **AT-13:** An approved record influences a follow-up briefing for the same company only, with correct attribution and date.
- **AT-14:** Follow-up task statuses persist correctly and can be changed manually; an omitted due date stays absent.
- **AT-15:** Previously saved briefings retain their original creation/research timestamps.

**Balanced acceptance rule:** A polished-looking PDF is insufficient. Required research must have run, claims must be traceable, failures must be explicit, and repeatable tests must demonstrate the agreed behavior. Exact pass thresholds and performance targets are still to be set after baseline measurements.

## 10. Implementation order and milestones

### Phase 0 — Foundation and feasibility
1. Verify environment and current OpenAI/search provider APIs, service pricing and credentials policy.
2. Create a separate project folder/repository, dependency lock strategy and environment configuration.
3. Choose three demo companies and design a small, clearly synthetic seed corpus with source metadata and controlled contradictory documents.
4. Prove end-to-end extraction → index → retrieval on a tiny sample; validate table extraction.

### Phase 1 — Instructor-aligned briefing engine
5. Implement deterministic mandatory internal RAG and external 48-hour → conditional 30-day search.
6. Add one agent with bounded optional tool calls and structured response validation.
7. Produce six-section on-screen and bilingual one-page PDF outputs with source details.
8. Run selected retrieval, source, fallback, conflict, ambiguity, security and latency tests.
9. Expand corpus progressively toward ~30–50 quality-checked documents; exercise three demo scenarios and arbitrary-company mode.

**Milestone 1 exit:** User can supply a real company and meeting purpose and receive a defensible, evidence-backed one-page briefing and PDF, with gaps clearly disclosed.

### Phase 2 — Meeting history and follow-ups
10. Add SQLite schema and company/briefing/meeting/task persistence.
11. Build human-approved AI notes extraction and scoped history retrieval.
12. Add task status controls and the remaining UI pages.
13. Test history isolation, approvals, dating, follow-up inclusion and persistence.

**Milestone 2 exit:** A reviewer can prepare a first meeting, approve notes, create/update follow-up tasks, and generate a second briefing that correctly uses approved history.

### Phase 3 — Documentation and demonstration
14. Produce setup instructions, source provenance/synthetic-data disclaimer, architecture notes, cost/latency report and test results.
15. Rehearse demonstration of three selected companies, fallback, contradiction, and a follow-up meeting.
16. Review source-control exclusions; no live API keys, private records, or irrelevant final-project artifacts in repository.

## 11. Risks and design responses

| Risk | Response |
|---|---|
| Scope growth from briefing tool to lightweight CRM | Stage 1 is independently complete; Stage 2 must not block it. |
| Invented relationships from synthetic data | Permanent synthetic labels in corpus and output; clear distinction from actual company news. |
| No 48-hour news | Controlled 30-day fallback, explicit publication dates and “not found in searched sources” wording. |
| Search-provider timestamps unreliable/incomplete | Verify dates where possible and flag uncertain/undated results; never treat retrieval timestamp as publication date. |
| Conflicting or stale internal facts | Authority metadata, validity dates, source-aware conflict checks. |
| Bad Excel table extraction | Verify that product-price-unit terms remain associated; test with known rows. |
| Agent tool loops and unexpected spending | Fixed required minimum searches, maximum supplemental calls, timeouts, usage logging and budget guardrails. |
| Incorrect company matching | Disambiguation and company-scoped history/document retrieval. |
| Hebrew PDF layout failure | Explicit RTL test fixtures and chosen PDF renderer verification. |
| Slow output | Measure end-to-end stages; cache stable internal index; do not falsely promise fixed response time. |
| Prompt injection in web pages/documents | Treat sources as data, restrict tool interface and test adversarial content. |
| Complexity from extra business features | Keep database and history isolated behind an interface; defer until core accepted. |
| (v1.2) Synthetic history about a real company is mistaken for fact | Per-organization reality, mandatory banners, validator, claim-type origin rule, labels on every output (AT-22–AT-25). |
| (v1.2) Curated public snapshots go stale | "As of" retrieval dates; snapshots are never labelled recent; live search in Prompt 03 handles recent developments. |

## 12. Open decisions and verification tasks (not reasons to reopen the entire interview)

1. Choose actual three demo companies and assign distinct synthetic relationship histories. *(v1.2: pending Gate 2A, D4 and D5.)*
2. Define products, realistic price currency and units, versioned policy and document lifecycle for the fictional vendor; verify internal coherence. *(v1.2: vendor named Nivarque Document Systems and competitor Solquend Archive Systems (D1); currency pending D2.)*
3. Confirm specific OpenAI model(s), embedding model, web-search provider, supported tool-calling contracts, pricing, quotas and spending controls from current documentation; no assumption of free usage.
4. Choose extraction, PDF, embedding and agent-orchestration libraries; a one-agent architecture does **not** require CrewAI. Verify Streamlit/Chroma/SQLite versions and compatibility.
5. Define initial corpus document metadata, source authority/validity conventions, chunking strategy and company matching.
6. Establish privacy/security boundary for local prototype, allowed local files, logs and deletion policy; no claim of production-grade access control.
7. Fix the meeting-purpose choices and decide how free-text purpose is handled, consistent with Decision 08.
8. Specify exact failure/partial-result behavior, retry quotas, max supplemental searches and whether “within seconds” needs a concrete agreed target.
9. Finalize test fixture count and numerical retrieval/grounding acceptance thresholds after a measured baseline.
10. Select PDF generation approach and verify Hebrew/RTL and one-page constraints on actual samples.
11. Determine whether the instructor's optional ML win-probability component is explicitly excluded for this iteration (current recommendation: exclude).

## 12A. Revision record — v1.1 (4 November 2026)

- **Preserved:** All 32 owner-approved decisions, the DMS objective, one-agent hybrid research architecture, three-page staged scope and previous acceptance tests.
- **Added:** Section 6A operational boundaries; AT-16–AT-21; step-level redacted tracing; minimal tool permissions; explicit fixed-workflow/agent comparison; retry-safe writes and 20-case **final-stage target**.
- **Clarified:** NexaStream sample materials and Supabase belong to the immediate instructor-aligned classroom preparation; the DMS/Chroma architecture is not silently replaced. OpenAI, Tavily and Supabase connectivity is verified, but no application-level tests are claimed.
- **Origin:** Agent minimalism and patterns informed by *AI Agents Made Simple — Cheat Sheet* (Nir Diamant); specific numerical caps, schemas and acceptance checks are our chosen engineering proposals, not quoted instructor requirements.

## 12B. Revision record — v1.2 (5 November 2026)

- **Preserved:** decisions 01–06 and 08–32; the one-agent hybrid architecture; the staged scope; AT-01 to AT-21; the NexaStream/DMS separation; Chroma and SQLite roles.
- **Owner-accepted:** the v1.1 safeguards (§6A), which were accepted when Prompt 01 began on 4 November 2026.
- **Amended:** Decision 07 (D10) and FR-03.
- **Added:** §6B provenance model; claim-type origin rule in FR-07 and §8; labelling in FR-08 and FR-09; Organization, KnowledgeDocument and EvidenceItem contracts; AT-22 to AT-25; two new risks.
- **Clarified (final corrections):**
  - Organization is the canonical identity registry. Company is the runtime prospect or customer record, references Organization by `org_id`, and keeps the v1.1 `company_id` and `identity_confidence` fields.
  - Synthetic records cannot prove real-world facts.
  - Public sources may support publicly disclosed pricing, but never the fictional vendor's prices or invented relationships.
- **Owner decisions recorded:** D1, D3, D10, D11, D12–D14, D15 and D16, all approved.
- **Still pending:** D2, D4, D5 and D6, at Gate 2A.
- **Gate 01:** approved; frozen as local commit `3de0be9`; 32/32 tests passed when reported.

## 13. Approval and next handoff

**Status: Revision v1.2 prepared for owner review.** It records the owner decisions of 5 November 2026. It does not claim that any Prompt 02 work has been implemented.

**Next action:**
1. Review v1.2 together with Claude Code prompts v2.2.
2. Once approved, these become authoritative. v1.1 and v2.1 stay in `docs/` for reference.
3. Prompt 02 then begins with Gate 2A only.

The independent final project remains parked and unchanged.
