# Surplus recovery implementation and deployment gate — 18 October 2026

## Result

The approved isolated household-surplus and dummy-NGO collection pilot is implemented and deployed to the single hackathon project `ecoloop-511918`. Two independent ADK projects run on Google Agent Runtime in `asia-south1`: `agents/surplus-intake` and `agents/collection-planner`. FastAPI remains the identity, authorization, eligibility, version, idempotency and canonical-mutation boundary. The frontend adds `/surplus`, `/ngo/login` and `/ngo`.

The household flow accepts bounded text, one image or recorded/uploaded audio and receives editable extraction candidates only. Saving requires five explicit declarations plus confirmed item, amount/unit, preparation/packaging state, canonical household location and a future availability deadline. The NGO flow is separately authenticated and server-allowlisted, reads only confirmed eligible unexpired pilot records, accepts a food/category ask with amount/unit and mapped origin, and saves a validated advisory proposal with at most ten stops and an explicit unmet amount.

The planner can call only a bounded surplus-list tool and Google Routes. Route distance, duration, ordering and encoded geometry must come from the provider response. Neither agent has a canonical write, reservation, dispatch, contact or stock-mutation tool. Media bytes are request-scoped and are not written to Firestore, agent sessions or artifacts.

## Privacy correction

An implementation review found that the first household proposal response returned the full proposal record, which included every stop, the NGO origin and the encoded full-route geometry. That contradicted the governing decision that exact pickup locations are exposed only to the allowlisted demo NGO.

The household boundary is now a server-side whitelist. It returns the proposal ID, aggregate matched/unmet amounts, route availability/status, validity and only the requesting household's selected stop. It replaces model explanation text with deterministic privacy copy and excludes the NGO identity, creator UID, origin, other stops and encoded route. The household UI maps only its own confirmed pickup point; the NGO UI retains the full provider route and ordered exact stops.

## Local verification

- `agents-cli lint` passes for both agents after the Agent Runtime enhancement. Each run completed dependency sync, Ruff checking and formatting, codespell and `ty` type checking.
- Frontend `npm run lint` passes.
- `npm exec next build -- --webpack` passes, including TypeScript and static generation for `/surplus`, `/ngo` and `/ngo/login`.
- Targeted backend Ruff E/F/I checks and formatting pass; `python -m compileall -q app` passes.
- Both eval datasets/configs parse: seven surplus-intake cases and five collection-planner cases. These include ambiguity, prompt injection, prohibited plate/spoiled/expired food, separate multiple foods, blank image, silent audio, incompatible units, combined name/category matching, minimum-stop partial pickup, ten-stop unmet quantity and no-match handling. All five planner cases pass the deterministic selection contract without a model or Routes call.
- The collection safety plugin now enforces the tool sequence at runtime: one confirmed-surplus selection call followed by at most one Routes call. A deterministic callback contract rejects route-first, repeated-list and repeated-route attempts.
- Current Google documentation confirms the configured `gemini-3.8-flash` model ID, the `projects/{project}/locations/{location}/reasoningEngines/{id}` Agent Runtime resource shape and direct `agents-cli deploy` support for the `agent_runtime` target. Live project/model availability remains a pre-deployment check.
- A deterministic privacy contract confirms that a household proposal contains only its own stop and does not contain another address, the encoded route, NGO origin, NGO ID/creator or untrusted model explanation.
- Sanitized Agent Runtime dry-runs were executed from temporary copies that excluded real `.env` files. Both resolve to project `ecoloop-511918`, region `asia-south1`, one CPU, 4 GiB memory, minimum zero, maximum one and concurrency two. The CLI reported that Google Cloud checks were skipped because it is not authenticated.
- No frontend or backend unit tests ran, as required by the repository contract. No model or Routes request ran.

## Approved deployment

The owner approved required API enablement, a bounded twelve-case evaluation with a ₹50 stop, both Agent Runtime deployments, the Cloud Run app release and creation of one dummy NGO login. The owner later directed that no further validation was required and that manual owner testing would be the acceptance step.

- Surplus Intake Agent Runtime: `projects/722209767801/locations/asia-south1/reasoningEngines/2932028075371659264`.
- Collection Planner Agent Runtime: `projects/722209767801/locations/asia-south1/reasoningEngines/5620677052911845376`.
- Both runtimes use one CPU, 4 GiB memory, minimum zero, maximum one, concurrency two, Agent Identity and prompt/response-content capture disabled.
- Vertex AI/Agent Platform, Routes and Secret Manager APIs are enabled. The existing Cloud Run API identity received the standard Vertex AI User role required to invoke the runtimes. Its existing Cloud Build identity received the standard Cloud Build builder role after the project build bucket rejected source reads.
- The Surplus Intake live contract evaluation passed all seven cases. The Collection Planner evaluation was interrupted after two completed cases when the owner waived further validation; it is not claimed as passed.
- The reviewed application and agent source was committed locally as `b3cb746` (`feat: add surplus recovery MVP`). No push was authorized or performed.
- Both existing Agent Runtime resources were updated from that committed tree on 18 October 2026. Cloud Run API revision `ecoloop-api-00020-6bg` and web revision `ecoloop-web-00011-ltb`, built from images tagged `b3cb746`, receive 100% traffic. The stable web URL is `https://ecoloop-web-722209767801.asia-south1.run.app`.
- One Firebase dummy NGO identity and matching active demo-only `ngo_accounts/{uid}` record were created. The random password is intentionally omitted from repository evidence.
- An initial frontend image build missing its Firebase public browser key was cancelled and never deployed. The corrected replacement image was built and deployed.
- Per the owner's direction, authenticated household/NGO browser acceptance and route behavior are left for manual testing.

## Read-only Google Cloud preflight

The signed-in alternate account selected project `ecoloop-511918` (`ecoloop`), project number `722209767801`, in organisation `sudikhyatfu-org`.

- Cloud Run lists healthy `ecoloop-api` and `ecoloop-web` services in `asia-south1`.
- The paid billing account links only `ecoloop-511918`. Current-month cost displayed ₹0.00.
- `EcoLoop monthly cost alert` is ₹1,000 monthly with 50%, 90% and 100% thresholds. It applies to the billing account and has no spend cap.
- The billing console displays: “To avoid losing access to Google Cloud services, an administrator must verify this account.” This requires owner action before paid agent deployment.
- Places API (New), the Maps JavaScript backend, Cloud Run, Firestore, Identity Toolkit, Artifact Registry and Cloud Build are enabled.
- Agent Platform/Vertex AI, Routes and Secret Manager are not in the enabled-services list. The Agent Platform Deployments page independently reports that `aiplatform.googleapis.com` is disabled and shows no agent instances.
- Existing IAM includes the owner, the default compute service account, the Firebase Admin SDK service account and the GitHub deployer. No dedicated Agent Runtime identity exists yet. The GitHub deployer has Cloud Run/Artifact Registry/service-usage deployment roles but no observed Agent Platform/Vertex role.

No API, IAM role, quota, budget, account, secret, agent, Firestore record or deployment was created or changed during this preflight.

## Remaining acceptance

1. The owner will manually test household text/image/audio candidate extraction, explicit confirmation, centralized NGO surplus visibility, request-dependent planning and both map views.
2. Complete or rerun the five-case Collection Planner evaluation only if the owner later requests validation; it was intentionally stopped for this release.
3. Resolve the billing-account administrator-verification warning and restrict/rotate the browser Maps key as appropriate for the deployed domain.
4. Do not claim operational food redistribution, safety certification, reservation or dispatch from this demo.

## Architecture and decision pointers

- [Current MVP specification](../../planning/CURRENT_MVP_SPEC.md)
- [Implementation plan](../../planning/IMPLEMENTATION_PLAN.md)
- [Architecture](../ARCHITECTURE.md)
- [Decisions](../DECISIONS.md)
- [Approved agent specification](../../../.agents-cli-spec.md)

## Lessons

Generated deployment infrastructure must be reviewed as evidence, not accepted as the release plan. The scaffolded Terraform defaulted each runtime to one minimum instance, ten maximum instances, four CPUs, 8 GiB memory and additional storage/analytics resources. That unused bundle was removed from the agent projects. The bounded direct deployment plan instead uses minimum zero, maximum one, one CPU, 4 GiB and concurrency two, with prompt/response content capture off.

Route geometry is location data. Removing addresses from a response is insufficient if the same response still contains an encoded polyline through those locations. Tenant privacy therefore has to be enforced by a response whitelist at the authority boundary, not by hiding labels in React.

An allowlist alone does not bound paid tool use. The planner also needs a stateful call-order guard so a model cannot repeat an allowed Routes request. Prompt wording remains useful guidance, but the runtime callback owns the enforceable call count.
