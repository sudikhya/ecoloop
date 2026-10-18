# Decision knowledge

## Use canonical API data in household destinations (2026-10-17)

Home, Kitchen, Ask, Shop and Activity must read household data from the authenticated API. Do not fall back to browser-generated records when auth, membership, API, assistant, capture, outcome, sharing or managed preference services are unavailable; show an explicit unavailable state instead. Keep canonical writes disabled until identity, database and idempotency acceptance is reviewed.

## Prepare account commands behind a default-off build flag (2026-10-16)

Local Kitchen/Shopping command UI and private history may be implemented while billing is deferred. Keep browser commands disabled by default until live identity/database acceptance and approval to enable them. The public build flag is a release control, not an authorization boundary; FastAPI identity, membership, version and idempotency checks remain mandatory. Share/outcome writes, extraction and managed-agent operations remain separate unfinished units. Root owns the shared transport and account integration; feature workers own separate files.

## Demo-first parallel implementation (2026-10-16)

Owner explicitly authorized coding, separate feature branches, GPT-6 Luna/high workers and regular pushed checkpoints. Implement a synthetic browser demo while billing is deferred, alongside a fail-closed canonical backend foundation. This is an execution exception for the hackathon, not cancellation of managed Gemini/ADK/context requirements. Keep authenticated data out of the local store; do not mark complete cloud phases from demo evidence. A single integrator owns shared files, coordinates up to three workers and prepares reviewable merges. Hourly continuation resumes unfinished authorized work when usage and access permit. See current execution plan/session.
Current register: [MVP-D01–14](../planning/DECISIONS.md). Household scope is resolved by current user direction and newer consumer/Stitch evidence.

Managed Sessions, consented Memory Bank and typed cards remain core. Actual household exports override contradictory DESIGN.md prose. Dinner adjustment is the first complete slice, not the entire product. Autonomous war-room reports do not override current user scope; external test counts are not local proof.

Old DEC-PLAT register and ADRs remain historical sources. M0 resolves exact contracts and cloud access. Documentation/guidance only; recommendations do not imply deployment approval.

## Confirm selected intake candidates atomically (2026-10-17)

Candidate review remains separate from canonical Kitchen facts until the owner confirms selected rows. A creator-scoped intake confirmation transaction checks current membership, intake version, candidate ownership and absent item IDs, writes selected observations once, and leaves unselected rows pending. Reuse each server-generated candidate ID as its canonical item ID so retries cannot create duplicates. Bind idempotency to the target intake as well as actor and command. Browser writes remain behind the default-off command flag until live acceptance is reviewed.


## Superseded source material (2026-10-16)

The broad platform archive and consolidated build pack were removed from the active checkout to reduce stale discovery paths; Git history retains them. The current spec, decisions and implementation plan in `docs/planning/` govern. Current navigation is Home, Kitchen, Ask, Shop; sharing is an owner-recorded private log. Family invitations, recipient confirmations, live partner integrations and deposit/tote/marketplace flows are deferred. Canonical user-supplied Stitch PNG/HTML files remain under `docs/prototypes/`.

Current user decisions: shared accessible UI primitives under `frontend/src/components/ui/`; shared navigation/layout under `frontend/src/components/layout/`; one central Tailwind v4 `@theme` token source in `frontend/src/app/globals.css`; mobile-first responsive development; Google Cloud/Gemini services for approved product integrations; no frontend/backend unit tests or dependencies. See [MVP-D15–16](../planning/DECISIONS.md).

## Single hackathon environment — historical billing snapshot (2026-10-16)

Use one named Google Cloud/Firebase project and one environment for the hackathon by default; do not add staging/production separation unless the owner explicitly asks. Current project ID is `ecoloop-staging-20261015` (immutable); display name is “EcoLoop Hackathon.” Existing billing is off. The only listed billing account is closed and still linked to another active project, so inspect account-wide impact before reopening. The credits page failed to load; balance is unknown. See MVP-D17–18 and the current cloud setup session.

## Require explicit local assistant activation (2026-10-17)

Load local backend settings from the ignored `backend/.env` for development, with process environment taking precedence. Provider credentials and automatic provider selection do not authorize model calls: `AGENT_ENABLED` defaults to false and must be set true explicitly. Health reports the selected configured provider and activation state without validating credentials or calling a provider. Managed Sessions, Memory Bank and managed Agent Runtime remain separate unfinished requirements.

## Archive removed shopping entries (2026-10-17)

Shop removal is a versioned soft archive, scoped to the active household and authenticated actor, with an idempotent retry record. The active-list read filters archived rows after its existing bounded query, so removal preserves history without adding a Firestore index or changing Kitchen stock. A removal is reviewed explicitly before the command is sent.

## Forward photo bytes to Gemini without EcoLoop media persistence (2026-10-17)

The bounded household photo intake sends validated JPEG, PNG, or WebP bytes directly from the authenticated API request to the configured Gemini Developer API. EcoLoop stores only strictly validated candidate fields in the existing creator-private intake record; it does not write image bytes to disk or Cloud Storage, and no provider retention duration is claimed. Photo processing stays unavailable unless `AGENT_ENABLED=true` and a Developer API key are configured. The browser command flag remains default-off. See the photo-intake session for local verification and cloud acceptance gaps.

## Billing observations superseded (2026-10-17)

The 16 October note below records the state observed before the owner enabled billing; it is historical and must not be used as the current cloud state. On 17 October, read-only CLI and Console checks confirmed billing enabled for `ecoloop-staging-20261015`, linked to the open “Hackathon billing Account”; EcoLoop was the only project returned for that account. A ₹2,000 monthly budget is filtered to Gemini API, with 50/80/100% alerts and a Gemini API spend cap. The billing console reported ₹0 for 1–17 October, subject to reporting delay. Credits remain unverified. This does not cap other services or establish paid-service readiness. See [Agent Platform integration plan](../planning/AGENT_PLATFORM_PLAN.md).

## Agent Platform local adapter boundary (2026-10-17)

Keep Google managed Sessions and Memory Bank opt-in and disabled by default. The existing ADK orchestrator may use `VertexAiSessionService` only with a configured existing Agent Engine resource; health must label it configured-but-unverified until a real managed request and isolation check succeed. Firestore remains the source of truth. Memory Bank receives only explicitly consented saved preference facts and may supply assistant context only after each candidate is matched to the current owner-scoped Firestore record. Retain deletion tombstones until managed cleanup is confirmed; show unavailable/reconciliation state and allow explicit retry. No transcript ingestion or provider probe from health/GET. See [implementation session](sessions/2026-10-17-agent-platform-local-implementation.md).

## Minimal PWA installability and reminder boundary (2026-10-17)

Expose a manifest, platform icons and browser-supported installation prompt without adding a service worker: the current household app has authenticated data and no approved offline contract, so no runtime cache is introduced. Reminder readiness remains unavailable for push/email until a real device subscription and backend delivery/scheduler exist. Existing confirmed dates and last-check prompts stay in-app; browser notification permission is not presented as delivery readiness. See [PWA session](sessions/2026-10-17-pwa-reminders.md).

## Single-project Cloud Run shape (2026-10-17)

Deploy the Next.js web app and FastAPI API as two bounded Cloud Run services in the existing `ecoloop-staging-20261015` project and Firestore region. Both services need public Cloud Run invocation for browser access; every household API route remains behind verified Firebase identity and explicit membership, with exact-origin CORS. Keep minimum instances at zero and maximum instances at one for the hackathon demo. Cloud Build write flags default off; a release may opt in only for the explicitly requested household journey. The first revision of a new Cloud Run service receives default traffic because `--no-traffic` is rejected at service creation. Keep the assistant disabled until its provider key/billing scope and cost boundary are verified. See [Cloud Run release record](../implementation/cloud-run-readiness.md) and [deployment session](sessions/2026-10-17-cloud-run-deployment.md).

## Same-project Vertex for the EcoLoop assistant (2026-10-17)

Use Vertex AI in the existing `ecoloop-staging-20261015` project for the Google-model requirement instead of a Gemini API key from a separate billing-disabled project. The API runtime receives `roles/aiplatform.user`; assistant generation is enabled with an EcoLoop application cap of 300 requests per user per UTC day, a 2,048-token output cap on the serving revision, and a maximum 50-second model request. Do not treat provider health or a direct local model diagnostic as product acceptance: two authenticated Cloud Run ADK turns timed out. Keep the acceptance gap visible and resolve the Cloud Run ADK latency/hang before claiming the feature works. The project billing budget is alert-only, not a spend cap; see [AI enablement session](sessions/2026-10-17-ai-enable-and-architecture.md).

## Isolated two-agent surplus recovery pilot (2026-10-18)

The owner explicitly approved a demo-only household surplus and NGO collection-planning overlay in the currently deployed personal project `ecoloop-511918`. Implement two independently deployable ADK applications on Google Agent Runtime: one typed multimodal Surplus Intake Agent and one typed Collection Planning Agent. Do not fold them into the existing household assistant and do not give either agent a canonical write, reservation or dispatch tool. FastAPI owns Firebase identity, live household membership, the server-owned NGO allowlist, versions, idempotency, eligibility, unit compatibility and every Firestore mutation. Google Maps Routes owns route geometry/distance/duration; the planning model may explain supplied route facts but never invent them.

This pilot exposes exact confirmed pickup locations only to the allowlisted dummy NGO account. It accepts bounded text, one image or recorded audio; temporary bytes are deleted after processing. A household must review and confirm item, amount/unit, location and `available_until`. Plate leftovers, spoiled/expired food and uncertain safety are rejected; prepared food is never represented as cleared for real distribution. Proposals contain at most ten dynamic stops based on the NGO ask and show unmet quantity. The household proposal response is a server-side whitelist containing only that household's stop, aggregate status and amounts; the NGO origin, other stops and full route geometry are excluded. All screens and outputs say demo-only; there is no auto-reservation, dispatch, pickup, delivery or stock decrement. Cross-session memory and autonomous background execution are excluded.

The approved `.agents-cli-spec.md` is the build specification. The selected recipe patterns are runner-level safety lifecycle hooks and an ordered fail-closed pre-tool guard. Model-judged authorization, broad grants, autonomous execution and long-horizon memory were reviewed and rejected for this pilot. Deployment remains gated on bounded evaluation plus a fresh owner review of billing/IAM/APIs/secrets/rollback and incremental cost.
