export type ApiFailureCode = "not_configured" | "bad_origin" | "unauthenticated" | "forbidden" | "conflict" | "validation" | "rate_limited" | "unavailable" | "timeout" | "network" | "invalid_response" | "unexpected";

export class CanonicalApiError extends Error {
  constructor(readonly code: ApiFailureCode, message: string, readonly requestId?: string) {
    super(message);
    this.name = "CanonicalApiError";
  }
}

export type CanonicalResource = "households" | "kitchen" | "shopping" | "shopping-archive" | "facts/confirm" | "outcomes" | "share-logs" | "share-transition" | "activity" | "meal-plans" | "assistant-turns" | "preferences" | "preference-memory-sync" | "proposal-turns" | "proposal-actions" | "proposal-meal-actions" | "proposal-history";
export type CanonicalRequestOptions = { method?: "GET" | "POST" | "PATCH" | "PUT" | "DELETE"; recordId?: string; body?: unknown; signal?: AbortSignal; query?: { limit?: number; cursor?: string } };
const methods: Record<CanonicalResource, readonly string[]> = {
  households: ["GET", "POST", "DELETE"], kitchen: ["GET"], shopping: ["GET", "POST"], "shopping-archive": ["PATCH"], "facts/confirm": ["POST"], outcomes: ["POST"], "share-logs": ["GET", "POST"], "share-transition": ["PATCH"], activity: ["GET"], "meal-plans": ["GET"], "assistant-turns": ["POST"], preferences: ["GET", "PUT", "DELETE"], "preference-memory-sync": ["POST"], "proposal-turns": ["POST"], "proposal-actions": ["POST"], "proposal-meal-actions": ["POST"], "proposal-history": ["GET"],
};
const RESPONSE_BYTES = 512_000;

function apiOrigin(): string {
  const configured = process.env.NEXT_PUBLIC_ECOLOOP_API_ORIGIN?.trim();
  if (!configured) throw new CanonicalApiError("not_configured", "Household connection is not configured yet.");
  let url: URL;
  try { url = new URL(configured); } catch { throw new CanonicalApiError("bad_origin", "The household connection address is invalid."); }
  const loopback = ["localhost", "127.0.0.1", "[::1]"].includes(url.hostname);
  if ((url.protocol !== "https:" && !(url.protocol === "http:" && loopback)) || url.username || url.password || url.pathname !== "/" || url.search || url.hash) {
    throw new CanonicalApiError("bad_origin", "The household connection requires HTTPS outside local development.");
  }
  return url.origin;
}

function failure(status: number, body: unknown, writing: boolean): CanonicalApiError {
  const error = typeof body === "object" && body !== null && "error" in body ? body.error : null;
  const ref = typeof error === "object" && error !== null && "requestID" in error && typeof error.requestID === "string" && error.requestID.length <= 128 ? error.requestID : undefined;
  if (status === 401) return new CanonicalApiError("unauthenticated", "Your sign-in is not accepted. Sign in again to continue.", ref);
  if (status === 403) return new CanonicalApiError("forbidden", "This account cannot access that household. Check the household ID.", ref);
  if (status === 409) return new CanonicalApiError("conflict", "This request conflicts with current records. Reload and review your choice.", ref);
  if (status === 400 || status === 413 || status === 422) return new CanonicalApiError("validation", "The household service rejected this request. Review the fields before trying again.", ref);
  if (status === 429) return new CanonicalApiError("rate_limited", "Too many requests were made. Wait before retrying.", ref);
  if (status >= 500) return new CanonicalApiError("unavailable", writing ? "The service could not confirm this request. A change may still have been recorded; keep its original retry key." : "Household records are temporarily unavailable. Try loading them again later.", ref);
  return new CanonicalApiError("unexpected", "The household service could not confirm this request.", ref);
}

async function readJson(response: Response): Promise<unknown> {
  if (Number(response.headers.get("content-length")) > RESPONSE_BYTES) {
    await response.body?.cancel();
    throw new CanonicalApiError("invalid_response", "The household response exceeded the supported size.");
  }
  if (!response.body) throw new CanonicalApiError("invalid_response", "The household service returned an empty response.");
  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let bytes = 0; let text = "";
  try {
    while (true) {
      const chunk = await reader.read();
      if (chunk.done) break;
      bytes += chunk.value.byteLength;
      if (bytes > RESPONSE_BYTES) { await reader.cancel(); throw new CanonicalApiError("invalid_response", "The household response exceeded the supported size."); }
      text += decoder.decode(chunk.value, { stream: true });
    }
    text += decoder.decode();
  } finally { reader.releaseLock(); }
  try { return JSON.parse(text) as unknown; } catch { throw new CanonicalApiError("invalid_response", "The household service returned unreadable data."); }
}

/** Fixed household endpoints only; callers own command and result schema validation. Never retries. */
export async function canonicalRequest(resource: CanonicalResource, idToken: string, householdId: string | null, options: CanonicalRequestOptions = {}): Promise<unknown> {
  const method = options.method ?? "GET";
  if (!Object.hasOwn(methods, resource) || !methods[resource].includes(method)) throw new CanonicalApiError("validation", "This household operation is not supported.");
  if (!idToken || idToken.length > 8192 || /[\r\n]/.test(idToken)) throw new CanonicalApiError("unauthenticated", "Sign in before accessing household records.");
  const householdCreation = resource === "households" && method === "POST";
  const householdDiscovery = resource === "households" && method === "GET";
  const householdDeletion = resource === "households" && method === "DELETE";
  const userPrivate = resource === "preferences" || resource === "preference-memory-sync";
  const assistantTurn = resource === "assistant-turns" || resource === "proposal-turns";
  if (householdCreation || householdDiscovery || householdDeletion || userPrivate ? householdId !== null : !householdId || !/^[A-Za-z0-9_-]{1,128}$/.test(householdId)) throw new CanonicalApiError("validation", "This household request has an invalid scope.");
  const writing = method !== "GET" && !assistantTurn;
  if (householdCreation && process.env.NEXT_PUBLIC_ECOLOOP_ENABLE_HOUSEHOLD_CREATE !== "true") throw new CanonicalApiError("not_configured", "First-household creation is not enabled for this app yet.");
  if (writing && !householdCreation && !householdDeletion && process.env.NEXT_PUBLIC_ECOLOOP_ENABLE_COMMANDS !== "true") throw new CanonicalApiError("not_configured", "Household changes are not enabled for this app yet.");
  let path = householdCreation || householdDiscovery ? "/api/v1/households" : householdDeletion ? `/api/v1/households/${encodeURIComponent(options.recordId ?? "")}` : `/api/v1/${resource}`;
  if (resource === "assistant-turns") {
    path = "/api/v1/assistant/turns";
  } else if (resource === "proposal-turns") {
    path = "/api/v1/assistant/proposals/turns";
  } else if (resource === "proposal-history") {
    path = "/api/v1/assistant/proposals/history";
  } else if (resource === "proposal-actions") {
    if (typeof options.recordId !== "string" || !/^[A-Za-z0-9._:-]{1,128}$/.test(options.recordId)) throw new CanonicalApiError("validation", "This proposal reference is invalid.");
    path = `/api/v1/assistant/proposals/${encodeURIComponent(options.recordId)}/actions`;
  } else if (resource === "proposal-meal-actions") {
    if (typeof options.recordId !== "string" || !/^[A-Za-z0-9._:-]{1,128}$/.test(options.recordId)) throw new CanonicalApiError("validation", "This proposal reference is invalid.");
    path = `/api/v1/assistant/proposals/${encodeURIComponent(options.recordId)}/meal-actions`;
  } else if (resource === "preference-memory-sync") {
    if (typeof options.recordId !== "string" || !/^[A-Za-z0-9_-]{16,64}$/.test(options.recordId)) throw new CanonicalApiError("validation", "This preference reference is invalid.");
    path = `/api/v1/preferences/${encodeURIComponent(options.recordId)}/memory-sync`;
  } else if (userPrivate && options.recordId !== undefined) {
    if (!/^[A-Za-z0-9_-]{16,64}$/.test(options.recordId)) throw new CanonicalApiError("validation", "This preference reference is invalid.");
    path = `/api/v1/preferences/${encodeURIComponent(options.recordId)}`;
  } else if (resource === "share-transition") {
    if (typeof options.recordId !== "string" || !/^[A-Za-z0-9._:-]{1,128}$/.test(options.recordId) || [".", ".."].includes(options.recordId)) throw new CanonicalApiError("validation", "Choose a valid sharing record.");
    path = `/api/v1/share-logs/${encodeURIComponent(options.recordId)}`;
  } else if (resource === "shopping-archive") {
    if (typeof options.recordId !== "string" || !/^[A-Za-z0-9._:-]{1,128}$/.test(options.recordId) || [".", ".."].includes(options.recordId)) throw new CanonicalApiError("validation", "Choose a valid shopping entry.");
    path = `/api/v1/shopping/${encodeURIComponent(options.recordId)}`;
  } else if (options.recordId !== undefined) throw new CanonicalApiError("validation", "A record reference is not supported for this operation.");
  const url = new URL(path, apiOrigin());
  if (options.query) {
    if (method !== "GET" || !["share-logs", "activity", "meal-plans"].includes(resource)) throw new CanonicalApiError("validation", "Pagination is not supported for this operation.");
    const { limit, cursor } = options.query;
    if (limit !== undefined) {
      if (!Number.isSafeInteger(limit) || limit < 1 || limit > 100) throw new CanonicalApiError("validation", "Choose a page size between 1 and 100.");
      url.searchParams.set("limit", String(limit));
    }
    if (cursor !== undefined) {
      if (typeof cursor !== "string" || !cursor || cursor.length > 256) throw new CanonicalApiError("validation", "The history page reference is invalid.");
      url.searchParams.set("cursor", cursor);
    }
  }
  const hasBody = method !== "GET";
  if ((!hasBody && options.body !== undefined) || (hasBody && options.body === undefined)) throw new CanonicalApiError("validation", "The household request body is invalid.");
  const serialized = hasBody ? JSON.stringify(options.body) : undefined;
  if (serialized !== undefined && new TextEncoder().encode(serialized).length > 256_000) throw new CanonicalApiError("validation", "This change exceeds the supported request size.");
  const controller = new AbortController();
  // Agent requests may use the server's maximum 60-second model budget.
  const timeout = setTimeout(() => controller.abort(), assistantTurn ? 70_000 : 12_000);
  const abort = () => controller.abort(options.signal?.reason);
  if (options.signal?.aborted) controller.abort(options.signal.reason);
  options.signal?.addEventListener("abort", abort, { once: true });
  try {
    const response = await fetch(url, { method, body: serialized, headers: { Authorization: `Bearer ${idToken}`, ...(!householdCreation && !householdDiscovery && !userPrivate ? { "X-Household-ID": householdId! } : {}), Accept: "application/json", ...(hasBody ? { "Content-Type": "application/json" } : {}) }, cache: "no-store", credentials: "omit", redirect: "error", signal: controller.signal });
    const body = await readJson(response);
    if (!response.ok) throw failure(response.status, body, writing);
    return body;
  } catch (error) {
    if (controller.signal.aborted) {
      if (options.signal?.aborted) throw new DOMException("Request cancelled", "AbortError");
      throw new CanonicalApiError("timeout", writing ? "The request timed out. Keep the original retry key when retrying a change." : "Loading took too long. Check your connection and try again.");
    }
    if (error instanceof CanonicalApiError) throw error;
    throw new CanonicalApiError("network", writing ? "The response could not be confirmed. Keep the original retry key when retrying a change." : "Household records could not be loaded. Check your connection and try again.");
  } finally { clearTimeout(timeout); options.signal?.removeEventListener("abort", abort); }
}
