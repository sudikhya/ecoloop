# Household MVP — phase-wise implementation checklist

15 October 2026 · Planning baseline · 6 phases, 12 tasks, 36 granular units including 6 review gates.

This replaces the 156-unit platform plan. Every box starts unchecked: documentation is not implementation. The live MVPTasks Sheet is the status authority; this file is a baseline snapshot. Each unit has an owner, prerequisite and observable acceptance condition. A review gate counts once as a unit, not once per parent task.

**Verification constraint:** No frontend or backend unit tests, test frameworks/files or unit-test dependencies. Use type/lint/build checks only when requested, plus contract/integration/security checks, manual accessibility review, Cloud smoke checks and end-to-end journey evidence. AI evaluations may assess generated response quality under bounded data/cost but cannot establish deterministic correctness or authorization.

## How to execute

1. Read the current specification section for the unit, relevant Stitch export and active guidance only.
2. Open the live task, name the owner and set In progress. Work in one bounded domain; parallelize independent shell/schema tasks only after contracts agree.
3. Make a small reviewable change. For future implementation, gather actual evidence against the unit acceptance; do not import historical pass counts.
4. Attach evidence, reviewer and ISO update date; choose Complete and check Done. Calculated Verified also requires verified prerequisites.
5. Update session knowledge and stop at the next meaningful review boundary. If a prerequisite reopens, dependent progress reopens.

16 October execution update: the owner explicitly authorized implementation and parallel GPT-6 Luna/high agents with separate branches and pushed checkpoints. [Parallel execution](PARALLEL_EXECUTION.md) records the bounded demo path; [acceptance evidence](../evidence/demo-2026-10-16/README.md) records actual local checks. The original full-product units below remain unchecked where cloud prerequisites or acceptance evidence are missing. No frontend/backend unit tests were added or run.

## Critical path and token budget

Cloud access → identity/transactions → candidate confirmation → real managed agent/memory → typed approved action → recorded outcome → deployed full flow. Visual shell can overlap backend foundation after M0; memory and card work can overlap after M2. Deployment preparation M5.02.01 precedes deployed whole-flow proof M5.01.01; task IDs are stable, not a strict row execution order. Do not start ten parallel page builds.

Suggested context per coding session: 1–2k tokens of root/knowledge, 3–5k of the relevant spec/contract, 2–4k of current code/design, and a 1k handoff reserve. Keep a 20% context buffer; these are operational targets, not provider limits. Start with one unit per turn; split if evidence shows more than a few focused edits. Do not reload the full research archive. A second agent is useful for an independent design/security review, not duplicate research. Record actual model token usage before setting monetary caps.

Planning estimate: roughly 10–18 engineering days plus 2–4 integration/review days, with parallel work and credentials available. Per-phase ranges below are effort guidance and overlap; do not sum them into a promised calendar deadline. Do not substitute mock memory for a blocked core requirement.

## M0 — Freeze the smaller contract and prove access

Indicative effort: 1–2 engineering days. Entry: current source/design packet. Exit: M0.02.03 accepted.

### M0.01 Scope and contracts

- [ ] **M0.01.01 — Reconcile scope, source conflicts and screen authority**
  - Owner: Product lead. Prerequisites: None.
  - Acceptance: Owner review cites current Stitch map, exclusions and supersession; no unresolved contradictory active scope.

- [ ] **M0.01.02 — Define the first complete dinner-change slice**
  - Owner: Product + design. Prerequisites: M0.01.01.
  - Acceptance: Annotated Home→capture→confirm→Ask→approve→outcome journey includes all error/empty/conflict states.

- [ ] **M0.01.03 — Freeze schemas and mutation semantics**
  - Owner: Technical lead. Prerequisites: M0.01.02.
  - Acceptance: Reviewed candidate/date/unit/proposal/card contracts include unknowns, versions and idempotency.

### M0.02 Technical feasibility

- [ ] **M0.02.01 — Validate managed runtime, Sessions, Memory Bank and Gemini access**
  - Owner: Technical lead. Prerequisites: None.
  - Acceptance: Recorded project/region/IAM/quota and actual service response; explicit blocker ADR if fallback needed.
  - Local implementation note (17 October 2026): Agents CLI v1.10.0 is installed and its ADK skills are added to the workspace. The backend now has opt-in Agent Engine Sessions and direct Memory Bank adapter code, but no managed resource call or actual provider response was made. Project access, runtime identity, region/quota, and managed-service acceptance remain unverified; keep this task open.

- [ ] **M0.02.02 — Set privacy, consent, retention and cost boundaries**
  - Owner: Technical + product. Prerequisites: M0.01.03, M0.02.01.
  - Acceptance: Chosen retention durations, scoped preference consent/deletion policy and per-user cost limits documented; available credits are verified or recorded as unknown, the billing account's linked-project impact is reviewed, and a $10/month alert is configured for the single hackathon project before paid services are enabled. Its non-cap behavior and additional cost controls are explicit.

- [ ] **M0.02.03 — Review M0 exit evidence**
  - Owner: Reviewer. Prerequisites: M0.01.03, M0.02.02.
  - Acceptance: Scope, schemas and access proof reviewed; no implementation dependency rests on an unverified service claim.

## M1 — Build the shell and trusted household boundary

Indicative effort: 2–3 engineering days. Entry: M0 reviewed exit gate. Exit: M1.02.03 accepted.

### M1.01 Identity and authority

- [ ] **M1.01.01 — Establish solo household identity and membership**
  - Owner: Backend. Prerequisites: M0.02.03.
  - Acceptance: Valid identity resolves explicit membership; absent/foreign membership denied without default tenant.

- [ ] **M1.01.02 — Implement versioned facts and idempotent command boundary**
  - Owner: Backend. Prerequisites: M1.01.01.
  - Acceptance: Transaction checks base version and request hash; duplicate retry has one effect, changed payload conflicts.

- [ ] **M1.01.03 — Constrain media and direct data access**
  - Owner: Backend. Prerequisites: M1.01.02.
  - Acceptance: Private signed upload/read, bounded file validation, canonical client-write denial and retention handling demonstrated.
  - Local implementation note (17 October 2026): An isolated bounded cleanup command now claims expired server-owned metadata, deletes matching storage objects idempotently, and marks them deleted; it returns a nonzero status when records are skipped or remain pending, and emits an opaque continuation cursor for multi-page sweeps. The matching composite Firestore index is in `firestore.indexes.json` but is not deployed. No bucket, IAM, scheduler, or live object-retention run was verified. Keep this task open until the deployed lifecycle and acceptance evidence are reviewed.

### M1.02 Stitch shell

- [ ] **M1.02.01 — Establish shared tokenized UI foundation and four-tab responsive shell**
  - Owner: Frontend. Prerequisites: M0.02.03.
  - Acceptance: reusable Button/Heading/Input/Card primitives are in `frontend/src/components/ui/`; shared shell/navigation is in `frontend/src/components/layout/`; Tailwind v4 semantic tokens are centralized in `frontend/src/app/globals.css` `@theme`; Home/Kitchen/Ask/Shop reuse them and match the light Stitch references at 360px and wider breakpoints, with accessible touch/focus behavior.

- [ ] **M1.02.02 — Provide honest empty, loading, error and demo states**
  - Owner: Frontend. Prerequisites: M1.02.01.
  - Acceptance: Synthetic demo is visibly isolated; errors preserve drafts and unknown integrations are not labeled connected.

- [ ] **M1.02.03 — Review M1 exit evidence**
  - Owner: Reviewer. Prerequisites: M1.01.03, M1.02.02.
  - Acceptance: Shell review plus authenticated cross-scope denial and conflict/retry evidence available.

## M2 — Capture, confirm and maintain kitchen observations

Indicative effort: 2–3 engineering days. Entry: M1 reviewed exit gate. Exit: M2.02.03 accepted.

### M2.01 Intake

- [ ] **M2.01.01 — Add manual and text intake with candidate-only persistence**
  - Owner: Full stack. Prerequisites: M1.02.03.
  - Acceptance: Unconfirmed entries cannot change canonical Kitchen; bounds and cancel/retry work.

- [ ] **M2.01.02 — Connect real structured photo extraction**
  - Owner: Backend. Prerequisites: M2.01.01.
  - Acceptance: Real model response validates candidate schema; injection text is ignored as instructions; manual fallback works.

- [ ] **M2.01.03 — Implement correction and explicit confirmation sheet**
  - Owner: Full stack. Prerequisites: M2.01.02.
  - Acceptance: User edits names/amount/date type; one confirmation writes selected facts once and reports conflict safely.

### M2.02 Kitchen and dates

- [ ] **M2.02.01 — Implement Kitchen observation editing and uncertainty**
  - Owner: Full stack. Prerequisites: M2.01.03.
  - Acceptance: Unknown/stale stock is visible; incompatible units and negative quantities rejected; confirmed dates retain type/source.
  - Implementation note (17 October 2026): authenticated item details now include a default-off, versioned correction/recheck form using the canonical fact-confirm transaction. Known zero quantities are supported; unknown dates cannot retain stale provenance. Static lint/type checks pass, but no live edit/conflict journey ran, and M2.01.03 remains an open prerequisite. Do not mark this unit complete.

- [ ] **M2.02.02 — Add truthful Home/use-soon prompts**
  - Owner: Full stack. Prerequisites: M2.01.03, M2.02.01.
  - Acceptance: Confirmed date reminders differ from last-checked prompts; no photo-derived safety/expiry assertion.
  - Local implementation note (17 October 2026): Home now separates records with user-confirmed date/type from records without a date, links each prompt to the canonical item review, and offers an Add food entrypoint from Home and Kitchen. The prompt asks the household to review the stored date and check the food themselves; it makes no safety/freshness inference. Keep this task open until prerequisites and its authenticated acceptance evidence are reviewed.

- [ ] **M2.02.03 — Review M2 exit evidence**
  - Owner: Reviewer. Prerequisites: M2.01.03, M2.02.02.
  - Acceptance: Capture correction→confirm→Kitchen persists; no mutation before consent, retries/conflicts and missing fields covered.

## M3 — Prove real assistance, managed context and typed actions

Indicative effort: 3–4 engineering days. Entry: M2 reviewed exit gate. Exit: M3.02.03 accepted.

### M3.01 Managed agent and memory

- [ ] **M3.01.01 — Connect one real ADK orchestrator and scoped managed Sessions**
  - Owner: Backend. Prerequisites: M2.02.03.
  - Acceptance: Recorded actual Gemini/ADK tool trace with owned managed session IDs; foreign session lookup denied.
  - Local implementation note (17 October 2026): ADK selects `VertexAiSessionService` only when explicitly configured with an Agent Engine ID; new managed sessions receive the configured idle TTL. Health distinguishes configured from verified, and unsafe caller session IDs are deterministically mapped to provider-safe IDs. Default remains in-memory. No managed request, cross-user isolation run, or actual expiry observation occurred; keep this task open.

- [ ] **M3.01.02 — Implement approved-preference memory write and controls**
  - Owner: Backend. Prerequisites: M3.01.01.
  - Acceptance: Only consented preference event reaches managed Memory Bank; view/edit/revoke/delete states exposed without raw transcripts.
  - Local implementation note (17 October 2026): Added the Agent Platform SDK and a default-off direct Memory Bank adapter. Firestore remains canonical; only explicitly consented preference facts are eligible, using owner-scoped stable IDs. Versioned sync state, retry and deletion tombstones preserve revocation failures; retrieval returns only fresh canonical records matching provider candidates. Settings surfaces configuration/unverified state and explicit retry. No live provider calls or two-session recall/deletion proof occurred; keep this task open.

- [ ] **M3.01.03 — Prove recall across two sessions and memory isolation**
  - Owner: Technical lead. Prerequisites: M3.01.02.
  - Acceptance: Two distinct sessions recall approved preference; second user cannot; revoke excludes it immediately and provider deletion verified.

### M3.02 Typed decisions

- [ ] **M3.02.01 — Render the five validated card types**
  - Owner: Frontend + backend. Prerequisites: M2.02.03.
  - Acceptance: Discriminated schemas/components handle invalid card fallback; no arbitrary markup/endpoints or hidden writes.

- [ ] **M3.02.02 — Implement dinner adjustment and explicit proposal approval**
  - Owner: Full stack. Prerequisites: M3.01.01, M3.02.01.
  - Acceptance: 4→2 scaling deterministic; prepared-stage behavior sensible; stale/expired/malicious approvals denied; no inferred consumption.
  - Local coding note (17 October 2026): authenticated transactional approve/edit/dismiss now creates or revises canonical meal plans. Saved assistant quantities are labeled estimates; only eligible numeric quantities with recognized units scale deterministically before preparation. Portion changes require an exact household plan reference/version; model-proposed quantity deltas are preview-only. Kitchen stock is unchanged. Browser command acceptance, adversarial/stale/expiry acceptance, managed-session prerequisite, and reviewer exit evidence remain open; leave this task unchecked.

- [ ] **M3.02.03 — Review M3 exit evidence**
  - Owner: Reviewer. Prerequisites: M3.01.03, M3.02.02.
  - Acceptance: Real agent+memory proof and card approval transaction demonstrated; local substitutes cannot satisfy managed-service gate.

## M4 — Complete share, shopping and recorded outcomes

Indicative effort: 2–3 engineering days. Entry: M3 reviewed exit gate. Exit: M4.02.03 accepted.

### M4.01 Circular household actions

- [ ] **M4.01.01 — Record used, stored, discarded and compost observations**
  - Owner: Full stack. Prerequisites: M3.02.03.
  - Acceptance: Known compatible quantity updates once; unknown remains unknown; compost route is user-observed/local-policy-aware.

- [ ] **M4.01.02 — Implement share-before-waste sheet and handover states**
  - Owner: Full stack. Prerequisites: M3.02.03.
  - Acceptance: Owner-private handover log needs no second account; owner-reported offer/accept/handover/cancel states distinct; community interest simulated; prohibited recipient routes blocked.

- [ ] **M4.01.03 — Implement Shop list, stock check and permitted handoff**
  - Owner: Full stack. Prerequisites: M3.02.03.
  - Acceptance: Stale stock prompts confirmation; list edits approved; external link never claims purchase/live price/account sync.

### M4.02 Honest activity

- [ ] **M4.02.01 — Implement recorded activity with measurement basis**
  - Owner: Full stack. Prerequisites: M4.01.01, M4.01.02, M4.01.03.
  - Acceptance: Measured/estimated/unknown shown; duplicates/reversals excluded; no invented savings or undefined ratios.

- [ ] **M4.02.02 — Connect Home and Ask to outcome follow-up**
  - Owner: Frontend. Prerequisites: M4.01.03, M4.02.01.
  - Acceptance: Plan acceptance differs from actual use; user can return and record/correct outcome without losing context.
  - Local implementation note (17 October 2026): Home links a saved plan to an explicit outcome flow for its linked Kitchen items, or to a current-item selector when no ingredient is linked. The user sees that saving/approving a plan does not mean it was prepared or eaten. Outcome commands carry an optional plan ID; the backend verifies that ID exists in the same active household before committing under the existing item-version, actor-bound idempotency, and membership transaction. The plan reference is retained on the outcome and owner-private Activity records. Core-flow TypeScript, changed-file ESLint, and backend compile checks pass; the final Activity-history TypeScript rerun and browser acceptance remain open, so keep the task open.

- [ ] **M4.02.03 — Review M4 exit evidence**
  - Owner: Reviewer. Prerequisites: M4.01.03, M4.02.02.
  - Acceptance: Ten Stitch states covered through four destinations/shared flows; sharing/shopping/activity claims remain truthful.

## M5 — Prove the full flow and prepare a reviewable release

Indicative effort: 2–4 engineering days. Entry: M4 reviewed exit gate. Exit: M5.02.03 accepted.

### M5.01 Whole-journey proof

- [ ] **M5.01.01 — Verify end-to-end household loop and mobile usability**
  - Owner: Full stack + reviewer. Prerequisites: M5.02.01.
  - Acceptance: Real capture→confirm→Ask→approved adjustment→recorded outcome across deployed boundaries; screenshots and latency sample recorded.

- [ ] **M5.01.02 — Verify hostile, concurrent and unavailable-service cases**
  - Owner: Backend + reviewer. Prerequisites: M5.01.01.
  - Acceptance: Foreign scope/session, injected intake, malformed cards, retries/conflicts, no model/memory/network covered with actual outcomes.

- [ ] **M5.01.03 — Measure token, latency, cost and privacy behavior**
  - Owner: Technical lead. Prerequisites: M5.01.02.
  - Acceptance: Bounded representative sample names model/device/network; redacted trace and retention/deletion audit; no fabricated score.

### M5.02 Release and handoff

- [ ] **M5.02.01 — Automate authorized hackathon deployment with rollback**
  - Owner: Technical lead. Prerequisites: M4.02.03.
  - Acceptance: Reviewed single project/region, budget alerts and additional cost controls, IAM, Secret Manager references and rollback; repeatable Google Cloud build/deploy pipeline rolls out to the one hackathon environment; deployed version has HTTPS and health evidence before deployed E2E. Do not embed credentials in GitHub or repository files; if authorization/access unavailable, deployed gate stays blocked.

- [ ] **M5.02.02 — Record three-minute demo and operational handoff**
  - Owner: Product + technical. Prerequisites: M5.01.03, M5.02.01.
  - Acceptance: Shows real versus simulated labels, two-session preference, before/after facts and evidence links; remaining gaps explicit.

- [ ] **M5.02.03 — Review release gate and resolve open blockers**
  - Owner: Product + reviewer. Prerequisites: M5.01.03, M5.02.02.
  - Acceptance: All prerequisite evidence reviewed; only then mark hackathon-ready. No autonomous rollout or invented completion.

## M6 — Demo surplus recovery pilot

Added by owner approval on 18 October 2026. This is a bounded demo overlay, not authorization for operational food redistribution. It may progress against the deployed single-project foundation while earlier household phase gates remain honestly open.

### M6.01 Contracts and managed agents

- [ ] **M6.01.01 — Freeze recovery schemas, roles and safety rules**
  - Owner: Product + technical lead. Prerequisites: owner-approved `.agents-cli-spec.md`.
  - Acceptance: Reviewed typed `SurplusSubmission`, `NgoRequest` and `RouteProposal` contracts distinguish candidate/confirmed/proposed states; NGO access is server-allowlisted; prohibited foods, expiry, unit compatibility, ten-stop limit and no-reservation/no-dispatch rules are deterministic.
- [ ] **M6.01.02 — Implement the Surplus Intake Agent**
  - Owner: Agent/backend. Prerequisites: M6.01.01.
  - Acceptance: Bounded text/image/audio produces schema-valid candidate fields and explicit unknowns; prompt injection is treated as data; no tool can write canonical data; unsafe input cannot contaminate the agent session.
- [ ] **M6.01.03 — Implement the Collection Planning Agent**
  - Owner: Agent/backend. Prerequisites: M6.01.01.
  - Acceptance: Verified NGO requests receive a schema-valid proposal based only on the supplied eligible snapshot and Routes API facts; at most ten stops; unmet amount explicit; no reservation, dispatch or canonical write tool.

### M6.02 Canonical API and screens

- [ ] **M6.02.01 — Add household surplus commands and temporary media lifecycle**
  - Owner: Backend. Prerequisites: M6.01.02.
  - Acceptance: Firebase identity and live membership gate every request; candidate creation and explicit confirmation are separate; version/idempotency conflicts fail safely; temporary image/audio is private, bounded and deleted after processing.
- [ ] **M6.02.02 — Add demo NGO identity, requests, matching and routes**
  - Owner: Backend. Prerequisites: M6.01.03.
  - Acceptance: Only a Firebase UID in the server-owned active NGO allowlist can list centralized surplus or create a request; matching uses confirmed unexpired compatible records; route geometry/distance/duration come from Google Maps Routes; exact locations are never available to ordinary household accounts.
- [ ] **M6.02.03 — Add household and NGO interfaces**
  - Owner: Frontend. Prerequisites: M6.02.01, M6.02.02.
  - Acceptance: `/surplus`, `/ngo/login` and `/ngo` have signed-out/loading/empty/error/review/success states, mobile-first accessible controls, visible demo-only language, bounded recording/upload, explicit household confirmation, centralized NGO list and actual map route display.

### M6.03 Evaluate, deploy and verify

- [ ] **M6.03.01 — Run deterministic security and integration acceptance**
  - Owner: Technical lead + reviewer. Prerequisites: M6.02.03.
  - Acceptance: Allowed lint/type/build/compile and integration/security journeys cover foreign household, non-NGO, revoked NGO, malicious media text, prohibited food, stale record, incompatible unit, replay, stale version, >10 stops, route outage and no silent mutations. No frontend/backend unit tests are created or run.
- [ ] **M6.03.02 — Run bounded agent evaluations**
  - Owner: Agent lead + reviewer. Prerequisites: M6.03.01.
  - Acceptance: Synthetic dataset, selected model/region, per-run cost bound and observed results are recorded for both agents; evaluation is treated as quality evidence, never authorization or safety proof.
- [ ] **M6.03.03 — Review cost/IAM and deploy the pilot**
  - Owner: Owner + technical lead. Prerequisites: M6.03.02.
  - Acceptance: Owner reviews current billing linkage, budgets/quotas, APIs, Agent Runtime and Cloud Run service accounts, Firebase/Maps restrictions, secrets, rollback and expected incremental cost; then explicitly approves deployment. Both independent managed agents, API and web revisions are verified in `ecoloop-511918` with redacted evidence.
- [ ] **M6.03.04 — Create and verify the temporary NGO account**
  - Owner: Owner + technical lead. Prerequisites: M6.03.03.
  - Acceptance: A single dummy Firebase account is created, allowlisted as `NGO`, credentials are delivered only to the owner and never committed/logged, password rotation/deletion guidance is given, and a deployed end-to-end proposal is observed without dispatch or reservation.

## Deferred queue — outside release progress

Optional family invites and visibility controls; push notifications; authorized merchant OAuth/history; A2UI renderer package; authored dark theme; public/trusted-circle matching beyond the isolated pilot; qualified recipient operations; measured impact research. No deferred item is a hidden prerequisite or part of the completion denominator. Promote one only through an explicit scope/decision update.

## Live harness operating rules

MVPTasks inputs: Owner, Status, Done, Evidence, Reviewer, Updated. IDs/dependencies/acceptance change only through a reviewed plan revision. Formula columns are result and dependency readiness; do not type over them. Use filters, not physical sorting; dependency formulas use referenced rows. Complete + Done + evidence + reviewer + ISO date + all prerequisites verified yields Verified. A checkbox alone never passes.

MVPOverview rolls up Verified counts by phase. MVPDecisions contains the compact register. Archive tabs preserve prior work and are hidden to reduce clutter. Native collaboration updates immediately within the Sheet; Markdown and JSON do not sync automatically. At handoff, record a dated snapshot if needed. Do not count this artifact creation as product progress.
