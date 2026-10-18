import { CanonicalApiError, recoveryRequest } from "./canonical-transport";

export type RecoveryCategory =
  | "produce"
  | "grains"
  | "bakery"
  | "dairy"
  | "packaged"
  | "prepared_food"
  | "other";
export type RecoveryUnit = "g" | "kg" | "ml" | "l" | "portion" | "piece" | "pack";
export type RecoveryModality = "text" | "image" | "audio" | "manual";
export type RecoveryLocation = {
  address: string;
  latitude: number;
  longitude: number;
  place_id?: string;
};

export type SurplusCandidate = {
  food_name: string | null;
  category: RecoveryCategory | null;
  amount: string | null;
  unit: RecoveryUnit | null;
  preparation_state: "unprepared" | "unserved_prepared" | "packaged" | "unknown";
  packaging_state: "sealed" | "covered" | "open" | "unpackaged" | "unknown";
  review_flags: string[];
  disposition: "review" | "do_not_share";
  evidence_note: string;
};

export type SurplusRecord = {
  surplus_id: string;
  household_id: string;
  status: "CONFIRMED" | "CANCELLED";
  version: number;
  food_name: string;
  category: RecoveryCategory;
  amount: string;
  unit: RecoveryUnit;
  preparation_state: "unprepared" | "unserved_prepared" | "packaged";
  packaging_state: "sealed" | "covered" | "open" | "unpackaged";
  available_until: string;
  location: RecoveryLocation;
  source_modality: RecoveryModality;
  requires_qualified_review: boolean;
  created_at: string;
  updated_at: string;
};

export type RouteStop = {
  surplus_id: string;
  version: number;
  household_id: string;
  food_name: string;
  pickup_amount: string;
  unit: RecoveryUnit;
  available_until: string;
  location: RecoveryLocation;
};

export type RouteProposal = {
  proposal_id: string;
  request_id: string;
  origin: RecoveryLocation;
  selected_stops: RouteStop[];
  matched_amount: string;
  unmet_amount: string;
  unit: RecoveryUnit;
  route_status: "ready" | "unavailable" | "no_matches";
  route: null | {
    distance_meters: number;
    duration_seconds: number;
    encoded_polyline: string;
    ordered_surplus_ids: string[];
  };
  explanation: string;
  warnings: string[];
  created_at: string;
  validity?: "CURRENT" | "STALE";
  stale_reason?: string | null;
};

export type HouseholdRouteProposal = {
  proposal_id: string;
  request_id: string;
  selected_stops: RouteStop[];
  matched_amount: string;
  unmet_amount: string;
  unit: RecoveryUnit;
  route_status: "ready" | "unavailable" | "no_matches";
  route_available: boolean;
  explanation: string;
  warnings: string[];
  created_at: string;
  validity: "CURRENT" | "STALE";
  stale_reason: string | null;
};

export type ConfirmSurplusInput = {
  food_name: string;
  category: RecoveryCategory;
  amount: string;
  unit: RecoveryUnit;
  preparation_state: "unprepared" | "unserved_prepared" | "packaged";
  packaging_state: "sealed" | "covered" | "open" | "unpackaged";
  available_until: string;
  source_modality: RecoveryModality;
};

export type NgoRequestInput = {
  food_name: string | null;
  category: RecoveryCategory | null;
  amount: string;
  unit: RecoveryUnit;
  origin: RecoveryLocation;
};

function object(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function id(value: unknown): value is string {
  return typeof value === "string" && /^[A-Za-z0-9._:-]{1,128}$/.test(value);
}

function text(value: unknown, max: number): value is string {
  return typeof value === "string" && value.length > 0 && value.length <= max;
}

function decimal(value: unknown): value is string {
  return typeof value === "string" && /^(?:0|[1-9]\d{0,6})(?:\.\d{1,3})?$/.test(value) && Number(value) >= 0;
}

function timestamp(value: unknown): value is string {
  return typeof value === "string" && value.length <= 40 && Number.isFinite(Date.parse(value));
}

const categories = new Set<RecoveryCategory>([
  "produce",
  "grains",
  "bakery",
  "dairy",
  "packaged",
  "prepared_food",
  "other",
]);
const units = new Set<RecoveryUnit>(["g", "kg", "ml", "l", "portion", "piece", "pack"]);

function category(value: unknown): value is RecoveryCategory {
  return typeof value === "string" && categories.has(value as RecoveryCategory);
}

function unit(value: unknown): value is RecoveryUnit {
  return typeof value === "string" && units.has(value as RecoveryUnit);
}

function location(value: unknown): value is RecoveryLocation {
  return (
    object(value) &&
    text(value.address, 300) &&
    typeof value.latitude === "number" &&
    Number.isFinite(value.latitude) &&
    value.latitude >= -90 &&
    value.latitude <= 90 &&
    typeof value.longitude === "number" &&
    Number.isFinite(value.longitude) &&
    value.longitude >= -180 &&
    value.longitude <= 180 &&
    (value.place_id === undefined || text(value.place_id, 300))
  );
}

function result(payload: unknown): Record<string, unknown> {
  if (
    !object(payload) ||
    payload.schema_version !== 1 ||
    !text(payload.request_id, 128) ||
    !object(payload.result)
  ) {
    throw new CanonicalApiError("invalid_response", "The recovery API returned an unexpected response.");
  }
  return payload.result;
}

function candidate(value: unknown): value is SurplusCandidate {
  return (
    object(value) &&
    (value.food_name === null || text(value.food_name, 100)) &&
    (value.category === null || category(value.category)) &&
    (value.amount === null || decimal(value.amount)) &&
    (value.unit === null || unit(value.unit)) &&
    (value.amount === null) === (value.unit === null) &&
    ["unprepared", "unserved_prepared", "packaged", "unknown"].includes(String(value.preparation_state)) &&
    ["sealed", "covered", "open", "unpackaged", "unknown"].includes(String(value.packaging_state)) &&
    Array.isArray(value.review_flags) &&
    value.review_flags.length <= 9 &&
    value.review_flags.every((flag) => text(flag, 80)) &&
    ["review", "do_not_share"].includes(String(value.disposition)) &&
    text(value.evidence_note, 240)
  );
}

function surplus(value: unknown): value is SurplusRecord {
  return (
    object(value) &&
    id(value.surplus_id) &&
    id(value.household_id) &&
    ["CONFIRMED", "CANCELLED"].includes(String(value.status)) &&
    Number.isSafeInteger(value.version) &&
    Number(value.version) > 0 &&
    text(value.food_name, 100) &&
    category(value.category) &&
    decimal(value.amount) &&
    Number(value.amount) > 0 &&
    unit(value.unit) &&
    ["unprepared", "unserved_prepared", "packaged"].includes(String(value.preparation_state)) &&
    ["sealed", "covered", "open", "unpackaged"].includes(String(value.packaging_state)) &&
    timestamp(value.available_until) &&
    location(value.location) &&
    ["text", "image", "audio", "manual"].includes(String(value.source_modality)) &&
    typeof value.requires_qualified_review === "boolean" &&
    timestamp(value.created_at) &&
    timestamp(value.updated_at)
  );
}

function stop(value: unknown): value is RouteStop {
  return (
    object(value) &&
    id(value.surplus_id) &&
    id(value.household_id) &&
    Number.isSafeInteger(value.version) &&
    Number(value.version) > 0 &&
    text(value.food_name, 100) &&
    decimal(value.pickup_amount) &&
    Number(value.pickup_amount) > 0 &&
    unit(value.unit) &&
    timestamp(value.available_until) &&
    location(value.location)
  );
}

function proposal(value: unknown): value is RouteProposal {
  if (
    !object(value) ||
    !id(value.proposal_id) ||
    !id(value.request_id) ||
    !location(value.origin) ||
    !Array.isArray(value.selected_stops) ||
    value.selected_stops.length > 10 ||
    !value.selected_stops.every(stop) ||
    !decimal(value.matched_amount) ||
    !decimal(value.unmet_amount) ||
    !unit(value.unit) ||
    !["ready", "unavailable", "no_matches"].includes(String(value.route_status)) ||
    !text(value.explanation, 600) ||
    !Array.isArray(value.warnings) ||
    value.warnings.length > 8 ||
    !value.warnings.every((warning) => text(warning, 240)) ||
    !timestamp(value.created_at)
  ) return false;
  if (value.route === null) return value.route_status !== "ready";
  return (
    value.route_status === "ready" &&
    object(value.route) &&
    Number.isSafeInteger(value.route.distance_meters) &&
    Number(value.route.distance_meters) >= 0 &&
    Number.isSafeInteger(value.route.duration_seconds) &&
    Number(value.route.duration_seconds) >= 0 &&
    text(value.route.encoded_polyline, 200_000) &&
    Array.isArray(value.route.ordered_surplus_ids) &&
    value.route.ordered_surplus_ids.length === value.selected_stops.length &&
    value.route.ordered_surplus_ids.every(id)
  );
}

function proposalList(payload: unknown): RouteProposal[] {
  const data = result(payload);
  if (!Array.isArray(data.proposals) || data.proposals.length > 20 || !data.proposals.every(proposal)) {
    throw new CanonicalApiError("invalid_response", "The recovery API returned invalid route proposals.");
  }
  return data.proposals;
}

function householdProposal(value: unknown): value is HouseholdRouteProposal {
  return (
    object(value) &&
    id(value.proposal_id) &&
    id(value.request_id) &&
    Array.isArray(value.selected_stops) &&
    value.selected_stops.length > 0 &&
    value.selected_stops.length <= 10 &&
    value.selected_stops.every(stop) &&
    decimal(value.matched_amount) &&
    decimal(value.unmet_amount) &&
    unit(value.unit) &&
    ["ready", "unavailable", "no_matches"].includes(String(value.route_status)) &&
    typeof value.route_available === "boolean" &&
    text(value.explanation, 600) &&
    Array.isArray(value.warnings) &&
    value.warnings.length <= 8 &&
    value.warnings.every((warning) => text(warning, 240)) &&
    timestamp(value.created_at) &&
    ["CURRENT", "STALE"].includes(String(value.validity)) &&
    (value.stale_reason === null || text(value.stale_reason, 240))
  );
}

export async function extractSurplusText(
  token: string,
  householdId: string,
  input: string,
): Promise<SurplusCandidate[]> {
  const data = result(await recoveryRequest("surplus-intake-text", token, {
    method: "POST",
    householdId,
    body: { schema_version: 1, text: input },
  }));
  if (!object(data.candidate) || !Array.isArray(data.candidate.candidates) || !data.candidate.candidates.every(candidate)) {
    throw new CanonicalApiError("invalid_response", "The intake agent returned invalid candidates.");
  }
  return data.candidate.candidates;
}

export async function extractSurplusMedia(
  token: string,
  householdId: string,
  media: Blob,
): Promise<SurplusCandidate[]> {
  const data = result(await recoveryRequest("surplus-intake-media", token, {
    method: "POST",
    householdId,
    media,
  }));
  if (!object(data.candidate) || !Array.isArray(data.candidate.candidates) || !data.candidate.candidates.every(candidate)) {
    throw new CanonicalApiError("invalid_response", "The intake agent returned invalid candidates.");
  }
  return data.candidate.candidates;
}

export async function listHouseholdSurplus(token: string, householdId: string): Promise<SurplusRecord[]> {
  const data = result(await recoveryRequest("surplus-list", token, { householdId }));
  if (!Array.isArray(data.surplus) || data.surplus.length > 200 || !data.surplus.every(surplus)) {
    throw new CanonicalApiError("invalid_response", "The API returned invalid household surplus records.");
  }
  return data.surplus;
}

export async function confirmSurplus(
  token: string,
  householdId: string,
  input: ConfirmSurplusInput,
  idempotencyKey: string,
): Promise<SurplusRecord> {
  const data = result(await recoveryRequest("surplus-create", token, {
    method: "POST",
    householdId,
    body: {
      schema_version: 1,
      idempotency_key: idempotencyKey,
      ...input,
      household_location_confirmed: true,
      not_plate_leftover: true,
      not_spoiled: true,
      not_expired: true,
      not_previously_served: true,
    },
  }));
  if (!surplus(data.surplus)) {
    throw new CanonicalApiError("invalid_response", "The API returned an invalid surplus record.");
  }
  return data.surplus;
}

export async function cancelSurplus(
  token: string,
  householdId: string,
  record: Pick<SurplusRecord, "surplus_id" | "version">,
  idempotencyKey: string,
): Promise<void> {
  const data = result(await recoveryRequest("surplus-cancel", token, {
    method: "POST",
    householdId,
    recordId: record.surplus_id,
    body: { schema_version: 1, idempotency_key: idempotencyKey, base_version: record.version },
  }));
  if (data.surplus_id !== record.surplus_id || data.status !== "CANCELLED") {
    throw new CanonicalApiError("invalid_response", "The API returned an invalid cancellation result.");
  }
}

export async function listHouseholdRouteProposals(token: string, householdId: string): Promise<HouseholdRouteProposal[]> {
  const data = result(await recoveryRequest("household-route-proposals", token, { householdId }));
  if (
    !Array.isArray(data.proposals) ||
    data.proposals.length > 20 ||
    !data.proposals.every(householdProposal)
  ) {
    throw new CanonicalApiError("invalid_response", "The API returned invalid household proposal summaries.");
  }
  return data.proposals;
}

export async function readNgoAccount(token: string): Promise<{ uid: string; ngo_id: string }> {
  const data = result(await recoveryRequest("ngo-me", token));
  if (!text(data.uid, 128) || !id(data.ngo_id) || data.role !== "NGO" || data.demo_only !== true) {
    throw new CanonicalApiError("invalid_response", "The API returned an invalid NGO role record.");
  }
  return { uid: data.uid, ngo_id: data.ngo_id };
}

export async function listNgoSurplus(token: string): Promise<SurplusRecord[]> {
  const data = result(await recoveryRequest("ngo-surplus", token));
  if (!Array.isArray(data.surplus) || data.surplus.length > 200 || !data.surplus.every(surplus)) {
    throw new CanonicalApiError("invalid_response", "The API returned invalid central surplus records.");
  }
  return data.surplus;
}

export async function createNgoRequest(
  token: string,
  input: NgoRequestInput,
  idempotencyKey: string,
): Promise<{ request_id: string; version: number }> {
  const data = result(await recoveryRequest("ngo-requests", token, {
    method: "POST",
    body: { schema_version: 1, idempotency_key: idempotencyKey, ...input },
  }));
  if (!object(data.request) || !id(data.request.request_id) || data.request.version !== 1) {
    throw new CanonicalApiError("invalid_response", "The API returned an invalid NGO request.");
  }
  return { request_id: data.request.request_id, version: data.request.version };
}

export async function planNgoRequest(
  token: string,
  request: { request_id: string; version: number },
  idempotencyKey: string,
): Promise<RouteProposal> {
  const data = result(await recoveryRequest("ngo-plan", token, {
    method: "POST",
    recordId: request.request_id,
    body: {
      schema_version: 1,
      idempotency_key: idempotencyKey,
      base_request_version: request.version,
    },
  }));
  if (!proposal(data.proposal)) {
    throw new CanonicalApiError("invalid_response", "The planner returned an invalid route proposal.");
  }
  return data.proposal;
}

export async function listNgoProposals(token: string): Promise<RouteProposal[]> {
  return proposalList(await recoveryRequest("ngo-proposals", token));
}

export { CanonicalApiError };
