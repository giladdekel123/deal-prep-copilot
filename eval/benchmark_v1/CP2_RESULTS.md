# CP-2: evidence profile in the live model input (Phase 4.5) — FICTIONAL TEST DATA

Development split only; no held-out data read, run or scored. Earlier baselines (B0-offline, CP-0, post-I1, I1, I2)
are unchanged.

## Implementation

- **Source-classification correction (`evidence_profile.source_class`):** a primary source is the company's own
  (`official_company_source`) only when its URL is on the company's official domain (or a subdomain) from the
  resolved identity. A primary source elsewhere, such as a regulator, is `primary_third_party`: authoritative for
  what it records, not the company's own position. With no known company domain the class is `primary_source`
  (owner not established). Web news on the company's own domain is `company_announcement`, otherwise `news`.
  "Restates" now means a non-primary source repeating any primary source.
- **CP-2 integration:** `evidence.model_evidence` adds `"profile"` to each evidence entry the live drafter
  (`briefing.build_messages`) and the research agent (`agent.agent_context`) receive: `source_class`,
  `statement_form`, `date_status` and, when not empty, `contested_with` and `restates`. Switch
  `evidence.PROFILE_IN_MODEL_INPUT` (default on) exists only for the controlled comparison
  (`scripts/benchmark_live.py --no-profile`). The offline template uses the supplied profile when present.
- Not changed: models, settings, prompts, recommendation rules, I1 meeting history, frozen data.
- Prompt size: about 2,200–2,800 extra characters per drafting prompt (dry run).

## Live comparison

Same six development scenarios, models (gpt-6.1-terra drafter, gpt-6-luna agent, low effort, 4,000 / 600 output
tokens), fixture news, history seed, clock and scorer 1.1. Configuration A: I2 evidence selection without profile
fields. B: identical with profile fields. Two runs each, interleaved A1, B1, A2, B2. Prices checked on the official
pricing page before the runs (unchanged). Prepaid credit cannot be read with an API key; spending was enforced by
the per-call guard, a $1.25 cap per run and the experiment hard cap.

| Metric (scorer 1.1) | A1 | A2 | B1 | B2 |
|---|---|---|---|---|
| R1 must-reach evidence | 25/31 | 24/31 | 24/31 | 25/31 |
| R2 meeting history | 16/16 | 16/16 | 16/16 | 16/16 |
| R3 stale / misleading news excluded | 15/15 | 15/15 | 15/15 | 15/15 |
| O1 number consistency (partial) | 36/37 | 31/32 | 33/34 | 34/35 |
| O2a must-cite cited | 21/23 | 21/23 | 21/23 | 22/23 |
| O2b non-distractor citations | 60/60 | 53/53 | 56/56 | 57/57 |
| O3b formal contradiction disclosure | 0/4 | 0/4 | 0/4 | 0/4 |
| O3b_text contradiction stated in text | 2/4 | 3/4 | 3/4 | 3/4 |
| O3c undated marked | 2/6 | 3/6 | 3/6 | 2/6 |
| **O5a official verbatim preferred** | **4/5** | **5/6** | **6/6** | **6/6** |
| O5b quote pages out of Recent developments | 6/6 | 6/6 | 6/6 | 6/6 |
| O6a open items (scorer) | 7/12 | 5/12 | 6/12 | 8/12 |
| O6b existing terms not opportunities | 4/4 | 4/4 | 3/4 | 4/4 |
| O7a customer-grounded recommendations | 6/6 | 6/6 | 4/6 | 5/6 |
| O7b no unsupported product/competitor advice | 14/14 | 15/15 | 12/13 | 15/16 |
| O8 safety (partial) | 21/21 | 20/20 | 20/20 | 22/22 |

Every O1 failure is the drafter's description of the news window ("30-day context, not last-48-hours"), not a
factual figure.

| Run | Calls | Input tokens (cached) | Output tokens (reasoning) | Cost |
|---|---|---|---|---|
| A1 | 23 | 89,981 (0) | 7,847 (1,715) | $0.0632 |
| B1 | 22 | 100,150 (0) | 7,727 (1,933) | $0.0657 |
| A2 | 22 | 85,980 (12,374) | 7,855 (1,797) | $0.0579 |
| B2 | 21 | 94,088 (10,988) | 7,251 (1,374) | $0.0597 |
| **Total** | **88** | | | **$0.2464** of $5.00 |

## Reading the results

- **Consistent across both repeats (probably the profile):** in DEV-M2 both B runs cite the official verbatim
  passages; both A runs cite the official claims summary instead (O5a 9/11 versus 12/12). One run noted the news date
  as "provider-estimated", which only the profile states.
- **Within run-to-run variation (no claim):** O3b_text, O3c, O6a, O7a, O7b and O6b. A2 and B1 differ as much from
  their own repeats as from each other. O7a's B misses are new leads (E1, M2) whose recommendations cite news or no
  evidence; one B2 recommendation cited nothing.
- **I2 selection, present in both A and B (application improvement since post-I1, live):** quote pages never
  appear as news (O5b 6/6 in all four runs); the 30-day Lyon news for DEV-L1 now reaches the drafter; O2b is clean in
  all four runs (post-I1: 48/49); the contested factory and hospital counts reach the drafter in every run, and are
  stated as unresolved in most.
- **Manual review (Claude Code, not the owner's M2 audit):** no unsupported figure found. Contested counts were
  attributed to the company profile versus the aggregator and called unresolved. Remaining unsupported certainty:
  DEV-P2 A1 states that certificates were digital "since 2020" and that the board "decided in 2022" to do so, as if
  consistent: a chronology contradiction presented as established (I4). Recommendations in customer scenarios were
  specific (user count versus proposal, sizing questionnaire, discount-approval thresholds) in both configurations.

## Verification

Run one after another, 3.5–3.7 GB free memory throughout:
- full suite 603/604; the failure was the safeguard that production code never names the benchmark (a new comment in
  `evidence.py` did). The comment was reworded and the test passes; the test itself is unchanged.
- offline development benchmark identical to I2; rehearsal 35/35; consistency check 36/36; held-out freeze valid
  (1 of 3 executions used); protected local data unchanged before and after the paid runs.

## Conclusion

The profile fields are cheap (about $0.002 per briefing) and gave a small, repeatable gain in citing official
verbatim wording, with no measured regression beyond normal variation. Formal disclosure of contradictions (O3b 0/4)
and chronology are unchanged: the fields make disagreements visible, but the model is not told how to use them
(that is a prompt change, CP-3 / I6).
