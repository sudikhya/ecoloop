# Personal GCP deployment — 18 October 2026

## Result

EcoLoop was deployed successfully from `sudikhya/ecoloop` commit `00c3f9a` to the single authorized Google Cloud/Firebase project `ecoloop-511918` in `asia-south1`.

- Web: `https://ecoloop-web-722209767801.asia-south1.run.app`
- API: `https://ecoloop-api-722209767801.asia-south1.run.app`
- Final GitHub Actions run `39064800329` succeeded in 3m 29s.
- The web service loaded the signed-out household-access state.
- `GET /api/v1/health` returned `status: healthy`.
- An unauthenticated `GET /api/v1/households` returned `401`.
- A CORS preflight from the canonical web origin returned `200` with that exact `access-control-allow-origin` value.
- Both Cloud Run services reported healthy and serving traffic.

The first signed-in household-list request later returned `503`. A bounded
diagnostic revision (`1993f78`, GitHub Actions run `39065735102`) identified
Firestore `FailedPrecondition`/`400` on the `members.uid` collection-group
lookup. The runtime service account was granted `roles/datastore.user` and
`roles/firebaseauth.viewer`, and the declared `members.uid` ascending
collection-group index was enabled in Firestore. The Firebase console showed
the index active after its build completed; this configuration change did not
require another Cloud Run deployment.

The household location field was subsequently updated to use Google Maps'
current `PlaceAutocompleteElement` widget. The old implementation silently
fell back to a text field and contained a hard-coded fallback key, while the
container build did not receive `NEXT_PUBLIC_GOOGLE_MAPS_API_KEY`. The fallback
key was removed, the build/deployment path now requires the GitHub Actions
secret `GOOGLE_MAPS_BROWSER_API_KEY`, and the UI presents an explicit manual
entry state when Maps is unavailable. Maps JavaScript API and Places API (New)
were enabled in `ecoloop-511918`. An initially supplied key belonged to another
project and was rejected at runtime. It was replaced by the dedicated
`EcoLoop web Maps autocomplete` key in `ecoloop-511918`, restricted to those
two APIs and `https://ecoloop-web-722209767801.asia-south1.run.app/*`. A second
live failure isolated a client readiness race: the direct Maps script used
`loading=async`, but the component treated the script download event as Maps
readiness. The loader now waits for Google's explicit callback before calling
`importLibrary("places")`. After live suggestions were confirmed, the household
setup panel was changed from clipping overflow to an explicit overlay stacking
context so the Maps suggestion list remains visible above the following UI.

The account flow was then corrected to reconcile a successful household
creation into the signed-in membership list immediately. The empty-membership
message now disappears when creation succeeds, the new household is shown in
the chooser without a reload, and list-button and manual-ID selection both use
the same state transition that activates Home, Kitchen, Ask, and Shop. Deleting
the last household reopens the setup flow instead of leaving an empty chooser
with no creation controls.

## Cloud and security configuration

- Billing uses the owner's reviewed billing account; `ecoloop-511918` was the only linked project at review time.
- A monthly INR 1,000 budget with 50%, 90%, and 100% email thresholds was created. This is an alert, not a hard spending cap.
- Firebase was initialized on Blaze without Google Analytics.
- Email/password and Google authentication are enabled with public name `EcoLoop` and the owner's approved support email.
- Firestore `(default)` was created in `asia-south1`, Standard edition, production mode, with deny-by-default initial rules and no scheduled backups.
- The deployed Cloud Run web hostname was added to Firebase Authentication authorized domains.
- GitHub Actions uses Workload Identity Federation and the repository secrets `FIREBASE_WEB_API_KEY` and `GOOGLE_MAPS_BROWSER_API_KEY`; no long-lived service-account key was added.
- The release uses one project and one environment. Cloud Run is bounded to min 0, max 1, concurrency 20, one CPU, 512 MiB, and a 60-second timeout.
- Assistant/model execution remains explicitly disabled for the first release. No Gemini credential was configured.

## Verification notes and follow-up

- Frontend TypeScript checking and lint passed locally after the Maps autocomplete and household membership updates.
- A local Next.js production build could not complete because Turbopack was denied permission to bind its helper port in the local execution environment. The same Docker production build completed successfully in GitHub Actions.
- The household membership update also completed a local production build with
  Next's webpack builder; this bypassed the host-specific Turbopack helper-port
  restriction while exercising the same application routes and TypeScript
  compilation.
- The repository Firestore rules/indexes were not deployed by this workflow; the database retains the Firebase production-mode deny-all client rule. Backend Admin SDK access is therefore the current data path.
- The required `members.uid` collection-group single-field index was applied manually from the repository declaration after the initial signed-in request exposed the missing-index failure. Automating rules/index deployment remains follow-up work.
- Historical browser/API keys that previously appeared in local workflow history should be rotated or restricted where they remain active. The blocked unpublished commit containing an old key was rewritten before the successful push.
- The replacement Maps browser key is stored only as an encrypted GitHub Actions secret, not committed. GitHub Actions run `39067364235`, attempt 2, successfully rebuilt and deployed the frontend with that project-owned key. Live suggestion acceptance remains pending a fresh signed-in household setup after key-restriction propagation.
- A bounded origin-referrer probe confirmed that the deployed key loads the Maps JavaScript bootstrap without a known authorization error, and a Places API (New) sample autocomplete request returned suggestions. These checks isolated the remaining failure to client initialization rather than the key, billing, API activation, or referrer restriction.
- The rejected owner-supplied key was shared in conversation and should be rotated in its owning Google Cloud project.
- Before enabling Gemini/ADK, separately review model access, bounded cost, managed Sessions/Memory Bank, privacy-safe telemetry, and acceptance evidence.

Architecture and decision pointers: [architecture](../ARCHITECTURE.md), [decisions](../DECISIONS.md), [current MVP specification](../../planning/CURRENT_MVP_SPEC.md), and [implementation plan](../../planning/IMPLEMENTATION_PLAN.md).

## Lessons

Enable the Firestore API before creating the database, keep Firebase and compute in the same named project, and deploy required Firestore indexes alongside the application. Treat push protection as a release gate: removing a secret from the latest file is insufficient if it remains in an unpublished commit being pushed. Public browser-service keys still require explicit build-time injection, narrow HTTPS referrer and API restrictions, and a visible degraded UI state; never hide a stale fallback key in source. A successful canonical mutation must also update or revalidate its dependent client views; otherwise the backend fact and the visible membership state diverge until reload.
