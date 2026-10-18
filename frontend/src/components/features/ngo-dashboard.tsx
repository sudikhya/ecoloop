"use client";

import Link from "next/link";
import { useCallback, useEffect, useRef, useState, type FormEvent } from "react";

import { LocationAutocomplete, type SelectedLocation } from "@/components/account/location-autocomplete";
import { RouteMap } from "@/components/features/route-map";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Heading } from "@/components/ui/heading";
import { Input } from "@/components/ui/input";
import { getFirebaseClient } from "@/lib/firebase-client";
import { useLiveHousehold } from "@/lib/live-household";
import {
  CanonicalApiError,
  createNgoRequest,
  listNgoProposals,
  listNgoSurplus,
  planNgoRequest,
  readNgoAccount,
  type RecoveryCategory,
  type RecoveryUnit,
  type RouteProposal,
  type SurplusRecord,
} from "@/lib/recovery-api";

const categories: { value: RecoveryCategory; label: string }[] = [
  { value: "produce", label: "Produce" },
  { value: "grains", label: "Grains" },
  { value: "bakery", label: "Bakery" },
  { value: "dairy", label: "Dairy" },
  { value: "packaged", label: "Packaged food" },
  { value: "prepared_food", label: "Unserved prepared food" },
  { value: "other", label: "Other" },
];
const units: RecoveryUnit[] = ["g", "kg", "ml", "l", "portion", "piece", "pack"];

function message(error: unknown) {
  return error instanceof Error ? error.message : "The NGO demo could not complete this request.";
}

export function NgoDashboard() {
  const household = useLiveHousehold();
  const [ngoId, setNgoId] = useState("");
  const [surplus, setSurplus] = useState<SurplusRecord[]>([]);
  const [proposals, setProposals] = useState<RouteProposal[]>([]);
  const [foodName, setFoodName] = useState("");
  const [category, setCategory] = useState<RecoveryCategory | "">("");
  const [amount, setAmount] = useState("");
  const [unit, setUnit] = useState<RecoveryUnit>("kg");
  const [origin, setOrigin] = useState<SelectedLocation | null>(null);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [planRetryPending, setPlanRetryPending] = useState(false);
  const requestKeyRef = useRef("");
  const planKeyRef = useRef("");
  const pendingRequestRef = useRef<{ request_id: string; version: number } | null>(null);

  const reload = useCallback(async () => {
    if (!household.user) {
      setLoading(false);
      return;
    }
    setLoading(true);
    setError("");
    try {
      const token = await household.user.getIdToken();
      const account = await readNgoAccount(token);
      const [nextSurplus, nextProposals] = await Promise.all([
        listNgoSurplus(token),
        listNgoProposals(token),
      ]);
      setNgoId(account.ngo_id);
      setSurplus(nextSurplus);
      setProposals(nextProposals);
    } catch (nextError) {
      setError(message(nextError));
    } finally {
      setLoading(false);
    }
  }, [household.user]);

  useEffect(() => {
    void Promise.resolve().then(reload);
  }, [reload]);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!household.user) return;
    if ((!foodName.trim() && !category) || !amount || !origin?.address || origin.lat === undefined || origin.lng === undefined) {
      setError("Enter a food name or category, amount, and choose a mapped starting location.");
      return;
    }
    setBusy(true);
    setError("");
    setNotice("");
    requestKeyRef.current ||= crypto.randomUUID();
    planKeyRef.current ||= crypto.randomUUID();
    try {
      const token = await household.user.getIdToken();
      const request = pendingRequestRef.current ?? await createNgoRequest(token, {
        food_name: foodName.trim() || null,
        category: category || null,
        amount,
        unit,
        origin: {
          address: origin.address,
          latitude: origin.lat,
          longitude: origin.lng,
          place_id: origin.place_id,
        },
      }, requestKeyRef.current);
      pendingRequestRef.current = request;
      setPlanRetryPending(true);
      const proposal = await planNgoRequest(token, request, planKeyRef.current);
      pendingRequestRef.current = null;
      setPlanRetryPending(false);
      requestKeyRef.current = "";
      planKeyRef.current = "";
      setProposals((current) => [proposal, ...current.filter((item) => item.proposal_id !== proposal.proposal_id)]);
      setNotice("A validated advisory proposal was saved. No food was reserved and no driver was dispatched.");
      await reload();
    } catch (nextError) {
      if (nextError instanceof CanonicalApiError && ["validation", "forbidden", "unauthenticated", "conflict"].includes(nextError.code)) {
        if (!pendingRequestRef.current) requestKeyRef.current = "";
        planKeyRef.current = "";
        if (nextError.code === "conflict" || nextError.code === "validation") {
          pendingRequestRef.current = null;
          setPlanRetryPending(false);
        }
      }
      setError(message(nextError));
    } finally {
      setBusy(false);
    }
  }

  async function signOut() {
    const firebase = await getFirebaseClient();
    if (!firebase) return;
    const { signOut: firebaseSignOut } = await import("firebase/auth");
    await firebaseSignOut(firebase.auth);
  }

  if (!household.user && household.auth !== "loading") {
    return <Card className="mx-auto max-w-lg p-6"><Heading as="h1">NGO sign-in required</Heading><p className="mt-3 text-sm text-muted">Use the separate dummy NGO account to access this isolated pilot.</p><Link href="/ngo/login" className="mt-5 inline-flex min-h-12 items-center rounded-full bg-primary px-6 text-sm font-bold text-white">Open NGO login</Link></Card>;
  }

  const activeProposal = proposals.find((proposal) => proposal.validity === "CURRENT" && proposal.route_status === "ready") ?? proposals[0];

  return (
    <div className="space-y-6">
      <section className="rounded-card bg-primary-container p-6 text-white shadow-card sm:p-8">
        <div className="flex flex-wrap items-start justify-between gap-4"><div><Badge tone="amber">ADVISORY DEMO</Badge><h1 className="mt-4 text-3xl font-extrabold tracking-tight">NGO collection planner</h1><p className="mt-3 max-w-2xl text-sm leading-6 text-white/80">Ask for a specific food or category. The planner checks confirmed pilot surplus and requests one bounded Google route with no more than ten stops.</p></div><Button variant="secondary" onClick={() => void signOut()}>Sign out</Button></div>
        {ngoId && <p className="mt-4 text-xs text-white/70">Authorized NGO: {ngoId}</p>}
      </section>

      <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_minmax(320px,.75fr)]">
        <Card className="p-5 sm:p-6">
          <Heading as="h2">Create collection ask</Heading>
          <form onSubmit={submit} className="mt-4 space-y-4">
            <label className="block space-y-1 text-sm font-semibold text-primary">Food name (optional if category is selected)<Input value={foodName} onChange={(event) => setFoodName(event.target.value)} maxLength={100} placeholder="Tomatoes" /></label>
            <label className="block space-y-1 text-sm font-semibold text-primary">Category<select value={category} onChange={(event) => setCategory(event.target.value as RecoveryCategory | "")} className="min-h-12 w-full rounded-control border border-line bg-white px-4 text-ink"><option value="">Any matching name only</option>{categories.map((item) => <option key={item.value} value={item.value}>{item.label}</option>)}</select></label>
            <div className="grid grid-cols-[minmax(0,1fr)_120px] gap-3"><label className="space-y-1 text-sm font-semibold text-primary">Amount<Input inputMode="decimal" value={amount} onChange={(event) => setAmount(event.target.value)} placeholder="10" required /></label><label className="space-y-1 text-sm font-semibold text-primary">Unit<select value={unit} onChange={(event) => setUnit(event.target.value as RecoveryUnit)} className="min-h-12 w-full rounded-control border border-line bg-white px-3 text-ink">{units.map((value) => <option key={value} value={value}>{value}</option>)}</select></label></div>
            <LocationAutocomplete idPrefix="ngo-origin" label="NGO starting location" onLocationSelected={setOrigin} disabled={busy} />
            <Button type="submit" fullWidth disabled={busy || origin?.lat === undefined || origin?.lng === undefined || (!foodName.trim() && !category)} aria-busy={busy}>{busy ? "Planning with agent…" : planRetryPending ? "Retry route plan" : "Find surplus and plan route"}</Button>
          </form>
          {notice && <p className="mt-4 rounded-2xl bg-primary-soft p-3 text-sm text-primary" role="status">{notice}</p>}
          {error && <p className="mt-4 rounded-2xl bg-danger-soft p-3 text-sm text-danger" role="alert">{error}</p>}
        </Card>

        <Card className="p-5 sm:p-6">
          <div className="flex items-center justify-between gap-3"><Heading as="h2">Available surplus</Heading><Button size="sm" variant="ghost" onClick={() => void reload()} disabled={loading || busy}>Reload</Button></div>
          {loading ? <p className="mt-4 text-sm text-muted">Loading confirmed surplus…</p> : surplus.length === 0 ? <p className="mt-4 text-sm text-muted">No eligible, unexpired pilot surplus is available.</p> : <ul className="mt-4 max-h-[520px] space-y-3 overflow-y-auto pr-1">{surplus.map((record) => <li key={record.surplus_id} className="rounded-2xl bg-surface-muted p-4"><p className="font-bold text-primary">{record.food_name}</p><p className="mt-1 text-sm text-muted">{record.amount} {record.unit} · {record.category.replaceAll("_", " ")}</p><p className="mt-2 text-xs leading-5 text-muted">{record.location.address}</p><p className="mt-1 text-xs text-muted">Available until {new Date(record.available_until).toLocaleString()}</p>{record.requires_qualified_review && <Badge tone="amber" className="mt-2">QUALIFIED REVIEW NEEDED</Badge>}</li>)}</ul>}
        </Card>
      </div>

      <Card className="p-5 sm:p-6">
        <Heading as="h2">Latest saved proposal</Heading>
        {!activeProposal ? <p className="mt-4 text-sm text-muted">Submit an ask to create the first advisory proposal.</p> : <div className="mt-4 space-y-4"><div className="flex flex-wrap gap-2"><Badge tone="amber">NO RESERVATION</Badge><Badge tone={activeProposal.validity === "STALE" ? "neutral" : "green"}>{activeProposal.validity ?? "CURRENT"}</Badge></div><p className="text-sm leading-6 text-muted">Matched {activeProposal.matched_amount} {activeProposal.unit}; unmet {activeProposal.unmet_amount} {activeProposal.unit}. {activeProposal.explanation}</p>{activeProposal.warnings.length > 0 && <ul className="list-disc space-y-1 pl-5 text-xs text-tertiary">{activeProposal.warnings.map((warning) => <li key={warning}>{warning}</li>)}</ul>}{activeProposal.stale_reason && <p className="rounded-2xl bg-tertiary-soft p-3 text-sm text-tertiary">{activeProposal.stale_reason}</p>}{activeProposal.route ? <><div className="grid gap-3 sm:grid-cols-2"><div className="rounded-2xl bg-surface-muted p-4"><p className="text-xs font-bold uppercase text-muted">Distance</p><p className="mt-1 text-xl font-bold text-primary">{(activeProposal.route.distance_meters / 1000).toFixed(1)} km</p></div><div className="rounded-2xl bg-surface-muted p-4"><p className="text-xs font-bold uppercase text-muted">Estimated drive</p><p className="mt-1 text-xl font-bold text-primary">{Math.ceil(activeProposal.route.duration_seconds / 60)} min</p></div></div><RouteMap encodedPolyline={activeProposal.route.encoded_polyline} origin={activeProposal.origin} stops={activeProposal.selected_stops.map((stop) => stop.location)} /><ol className="space-y-2">{activeProposal.selected_stops.map((stop, index) => <li key={stop.surplus_id} className="rounded-2xl border border-line p-4"><p className="font-bold text-primary">Stop {index + 1}: {stop.food_name}</p><p className="mt-1 text-sm text-muted">Collect {stop.pickup_amount} {stop.unit} · {stop.location.address}</p><p className="mt-1 text-xs text-muted">Available until {new Date(stop.available_until).toLocaleString()}</p></li>)}</ol></> : <p className="rounded-2xl bg-tertiary-soft p-3 text-sm text-tertiary">Matches were saved, but no usable Google route was returned. No distance or travel time is being invented.</p>}</div>}
      </Card>
    </div>
  );
}
