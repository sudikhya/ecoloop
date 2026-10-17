import { canonicalRequest, CanonicalApiError } from "./canonical-transport";
export { CanonicalApiError, type ApiFailureCode } from "./canonical-transport";

export type KitchenObservation = {
  item_id: string;
  name: string;
  amount: number | null;
  unit: string | null;
  date_value: string | null;
  date_type: string;
  storage: string | null;
  version: number;
  observed_at: string;
};

export type ShoppingEntry = {
  entry_id: string;
  item_name: string;
  desired_amount: number | null;
  unit: string | null;
  version: number;
  updated_at: string;
};

export type HouseholdLocation = {
  address?: string;
  lat?: number;
  lng?: number;
  place_id?: string;
};

export type CreatedHousehold = {
  household_id: string;
  name: string;
  role: string;
  address?: string;
  location?: { lat: number; lng: number };
};
export type HouseholdMembership = CreatedHousehold;

export type CanonicalData =
  | { kind: "kitchen"; records: KitchenObservation[] }
  | { kind: "shopping"; records: ShoppingEntry[] };

function object(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}
function boundedString(value: unknown, max: number): value is string { return typeof value === "string" && value.length > 0 && value.length <= max; }
function nullableString(value: unknown, max: number): value is string | null { return value === null || (typeof value === "string" && value.length <= max); }
function recordId(value: unknown): value is string { return boundedString(value, 128) && /^[A-Za-z0-9._:-]+$/.test(value); }
function nullableAmount(value: unknown): value is number | null { return value === null || (typeof value === "number" && Number.isFinite(value) && value >= 0 && value <= 1_000_000); }
function positiveVersion(value: unknown): value is number { return typeof value === "number" && Number.isSafeInteger(value) && value > 0; }
function isoTimestamp(value: unknown): value is string { return boundedString(value, 40) && /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:\d{2})$/.test(value) && !Number.isNaN(Date.parse(value)); }
function dateOnly(value: unknown): value is string | null {
  if (value === null) return true;
  if (typeof value !== "string" || !/^\d{4}-\d{2}-\d{2}$/.test(value)) return false;
  const [year, month, day] = value.split("-").map(Number);
  const parsed = new Date(Date.UTC(year, month - 1, day));
  return parsed.getUTCFullYear() === year && parsed.getUTCMonth() === month - 1 && parsed.getUTCDate() === day;
}
function validQuantity(amount: unknown, unit: unknown): boolean {
  return nullableAmount(amount) && (amount === null ? unit === null : boundedString(unit, 32) && /^[A-Za-z][A-Za-z0-9_-]*$/.test(unit));
}
const dateTypes = new Set(["USE_BY", "EXPIRY", "BEST_BEFORE", "USER_TARGET", "UNKNOWN"]);
function isKitchenObservation(value: unknown): value is KitchenObservation {
  return object(value) && recordId(value.item_id) && boundedString(value.name, 120) && validQuantity(value.amount, value.unit) && dateOnly(value.date_value) && typeof value.date_type === "string" && dateTypes.has(value.date_type) && (value.date_value === null ? value.date_type === "UNKNOWN" : value.date_type !== "UNKNOWN") && nullableString(value.storage, 120) && positiveVersion(value.version) && isoTimestamp(value.observed_at);
}
function isShoppingEntry(value: unknown): value is ShoppingEntry {
  return object(value) && recordId(value.entry_id) && boundedString(value.item_name, 120) && validQuantity(value.desired_amount, value.unit) && positiveVersion(value.version) && isoTimestamp(value.updated_at);
}

function validateSuccess(data: unknown, kind: "kitchen" | "shopping"): CanonicalData {
  if (!object(data) || data.schema_version !== 1 || !boundedString(data.request_id, 128) || !object(data.result)) throw new CanonicalApiError("invalid_response", "The household API returned an unexpected response.");
  const list = kind === "kitchen" ? data.result.observations : data.result.entries;
  const valid = Array.isArray(list) && list.length <= 200 && list.every(kind === "kitchen" ? isKitchenObservation : isShoppingEntry);
  const ids = valid ? list.map((record) => kind === "kitchen" ? (record as KitchenObservation).item_id : (record as ShoppingEntry).entry_id) : [];
  if (!valid || new Set(ids).size !== ids.length) throw new CanonicalApiError("invalid_response", "The household API returned records that do not match the supported format.", data.request_id);
  return { kind, records: list as KitchenObservation[] | ShoppingEntry[] } as CanonicalData;
}

export async function readCanonicalRecords(kind: "kitchen" | "shopping", idToken: string, householdId: string, signal?: AbortSignal): Promise<CanonicalData> {
  if (kind !== "kitchen" && kind !== "shopping") throw new CanonicalApiError("validation", "This household list is not supported.");
  return validateSuccess(await canonicalRequest(kind, idToken, householdId, { signal }), kind);
}

export async function createCanonicalHousehold(
  idToken: string,
  name: string,
  idempotencyKey: string,
  location?: HouseholdLocation,
  signal?: AbortSignal,
): Promise<CreatedHousehold> {
  const cleanName = name.trim();
  if (!cleanName || cleanName.length > 60 || /[\u0000-\u001f\u007f]/.test(cleanName) || !/^[A-Za-z0-9-]{16,128}$/.test(idempotencyKey)) {
    throw new CanonicalApiError("validation", "Enter a household name and review it before creating.");
  }
  const bodyPayload: Record<string, unknown> = {
    schema_version: 1,
    idempotency_key: idempotencyKey,
    name: cleanName,
  };
  if (location?.address) bodyPayload.address = location.address.trim().slice(0, 256);
  if (typeof location?.lat === "number" && typeof location?.lng === "number") {
    bodyPayload.lat = location.lat;
    bodyPayload.lng = location.lng;
  }
  if (location?.place_id) bodyPayload.place_id = location.place_id.slice(0, 128);

  const payload = await canonicalRequest("households", idToken, null, {
    method: "POST",
    body: bodyPayload,
    signal,
  });
  if (!object(payload) || payload.schema_version !== 1 || !boundedString(payload.request_id, 128) || !object(payload.result)) {
    throw new CanonicalApiError("invalid_response", "The household service returned an unexpected creation response.", object(payload) && boundedString(payload.request_id, 128) ? payload.request_id : undefined);
  }
  const result = payload.result;
  if (typeof result.household_id !== "string" || !/^[A-Za-z0-9_-]{1,128}$/.test(result.household_id) || !boundedString(result.name, 60) || result.name !== cleanName || !boundedString(result.role, 32) || !/^[a-z][a-z_-]*$/i.test(result.role)) {
    throw new CanonicalApiError("invalid_response", "The household service returned an unexpected creation result.", payload.request_id);
  }
  return {
    household_id: result.household_id,
    name: result.name,
    role: result.role,
    address: location?.address,
    location: location?.lat !== undefined && location?.lng !== undefined ? { lat: location.lat, lng: location.lng } : undefined,
  };
}

export async function listCanonicalHouseholds(idToken: string, signal?: AbortSignal): Promise<HouseholdMembership[]> {
  const payload = await canonicalRequest("households", idToken, null, { method: "GET", signal });
  if (!object(payload) || payload.schema_version !== 1 || !boundedString(payload.request_id, 128) || !object(payload.result) || !Array.isArray(payload.result.households) || payload.result.households.length > 50) {
    throw new CanonicalApiError("invalid_response", "The household service returned an unexpected membership list.");
  }
  const rows = payload.result.households;
  if (!rows.every((row) => object(row) && typeof row.household_id === "string" && /^[A-Za-z0-9_-]{1,128}$/.test(row.household_id) && boundedString(row.name, 60) && boundedString(row.role, 32) && /^[a-z][a-z_-]*$/i.test(row.role)) || new Set(rows.map((row) => (row as Record<string, unknown>).household_id)).size !== rows.length) {
    throw new CanonicalApiError("invalid_response", "The household service returned memberships that do not match the supported format.");
  }
  return rows as HouseholdMembership[];
}

export async function deleteCanonicalHousehold(idToken: string, householdId: string, signal?: AbortSignal): Promise<void> {
  if (!householdId || !/^[A-Za-z0-9_-]{1,128}$/.test(householdId)) {
    throw new CanonicalApiError("validation", "A valid household ID is required to delete.");
  }
  const payload = await canonicalRequest("households", idToken, null, {
    method: "DELETE",
    recordId: householdId,
    signal,
  });
  if (!object(payload) || payload.schema_version !== 1 || !boundedString(payload.request_id, 128)) {
    throw new CanonicalApiError("invalid_response", "The household service returned an unexpected deletion response.");
  }
}

