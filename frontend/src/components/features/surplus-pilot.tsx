"use client";

import { useCallback, useEffect, useRef, useState } from "react";

import { PickupPointMap } from "@/components/features/route-map";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Heading } from "@/components/ui/heading";
import { Input } from "@/components/ui/input";
import {
  CanonicalApiError,
  cancelSurplus,
  confirmSurplus,
  extractSurplusMedia,
  extractSurplusText,
  listHouseholdRouteProposals,
  listHouseholdSurplus,
  type ConfirmSurplusInput,
  type RecoveryCategory,
  type RecoveryModality,
  type RecoveryUnit,
  type HouseholdRouteProposal,
  type SurplusCandidate,
  type SurplusRecord,
} from "@/lib/recovery-api";
import { useLiveHousehold } from "@/lib/live-household";

type CaptureMode = "text" | "image" | "audio" | "manual";
type Draft = {
  foodName: string;
  category: RecoveryCategory | "";
  amount: string;
  unit: RecoveryUnit | "";
  preparation: ConfirmSurplusInput["preparation_state"] | "";
  packaging: ConfirmSurplusInput["packaging_state"] | "";
  availableUntil: string;
  sourceModality: RecoveryModality;
};

const categoryOptions: { value: RecoveryCategory; label: string }[] = [
  { value: "produce", label: "Produce" },
  { value: "grains", label: "Grains" },
  { value: "bakery", label: "Bakery" },
  { value: "dairy", label: "Dairy" },
  { value: "packaged", label: "Packaged food" },
  { value: "prepared_food", label: "Unserved prepared food" },
  { value: "other", label: "Other" },
];
const unitOptions: RecoveryUnit[] = ["g", "kg", "ml", "l", "portion", "piece", "pack"];

function deadlineDefault() {
  const value = new Date(Date.now() + 4 * 60 * 60 * 1000);
  value.setMinutes(value.getMinutes() - value.getTimezoneOffset());
  return value.toISOString().slice(0, 16);
}

function emptyDraft(sourceModality: RecoveryModality = "manual"): Draft {
  return {
    foodName: "",
    category: "",
    amount: "",
    unit: "",
    preparation: "",
    packaging: "",
    availableUntil: deadlineDefault(),
    sourceModality,
  };
}

function draftFromCandidate(candidate: SurplusCandidate, modality: RecoveryModality): Draft {
  return {
    foodName: candidate.food_name ?? "",
    category: candidate.category ?? "",
    amount: candidate.amount ?? "",
    unit: candidate.unit ?? "",
    preparation: candidate.preparation_state === "unknown" ? "" : candidate.preparation_state,
    packaging: candidate.packaging_state === "unknown" ? "" : candidate.packaging_state,
    availableUntil: deadlineDefault(),
    sourceModality: modality,
  };
}

function message(error: unknown): string {
  return error instanceof Error ? error.message : "The recovery demo could not complete this request.";
}

export function SurplusPilot() {
  const household = useLiveHousehold();
  const [mode, setMode] = useState<CaptureMode>("text");
  const [textInput, setTextInput] = useState("");
  const [media, setMedia] = useState<Blob | null>(null);
  const [candidates, setCandidates] = useState<SurplusCandidate[]>([]);
  const [selectedCandidateIndex, setSelectedCandidateIndex] = useState(0);
  const [draft, setDraft] = useState<Draft>(() => emptyDraft("text"));
  const [declarations, setDeclarations] = useState([false, false, false, false, false]);
  const [records, setRecords] = useState<SurplusRecord[]>([]);
  const [proposals, setProposals] = useState<HouseholdRouteProposal[]>([]);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [recording, setRecording] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const saveKeyRef = useRef("");
  const cancelKeysRef = useRef(new Map<string, string>());
  const recorderRef = useRef<MediaRecorder | null>(null);
  const recordingStreamRef = useRef<MediaStream | null>(null);
  const chunksRef = useRef<Blob[]>([]);

  const reload = useCallback(async () => {
    if (!household.user || !household.householdId) return;
    setLoading(true);
    setError("");
    try {
      const token = await household.user.getIdToken();
      const [nextRecords, nextProposals] = await Promise.all([
        listHouseholdSurplus(token, household.householdId),
        listHouseholdRouteProposals(token, household.householdId),
      ]);
      setRecords(nextRecords);
      setProposals(nextProposals);
    } catch (nextError) {
      setError(message(nextError));
    } finally {
      setLoading(false);
    }
  }, [household.householdId, household.user]);

  useEffect(() => {
    void Promise.resolve().then(reload);
  }, [reload]);

  useEffect(() => () => {
    recorderRef.current?.stop();
    recordingStreamRef.current?.getTracks().forEach((track) => track.stop());
  }, []);

  function chooseMode(nextMode: CaptureMode) {
    setMode(nextMode);
    setCandidates([]);
    setSelectedCandidateIndex(0);
    setMedia(null);
    setError("");
    setNotice("");
    saveKeyRef.current = "";
    setDraft(emptyDraft(nextMode));
  }

  async function extract() {
    if (!household.user || !household.householdId) return;
    setBusy(true);
    setError("");
    setNotice("");
    try {
      const token = await household.user.getIdToken();
      const nextCandidates = mode === "text"
        ? await extractSurplusText(token, household.householdId, textInput.trim())
        : media
          ? await extractSurplusMedia(token, household.householdId, media)
          : [];
      if (!nextCandidates.length) {
        setError("No candidate was identified. Enter the details manually.");
        return;
      }
      setCandidates(nextCandidates);
      setSelectedCandidateIndex(0);
      setDraft(draftFromCandidate(nextCandidates[0], mode));
      setDeclarations([false, false, false, false, false]);
      setNotice("Review every field below. The agent has not created a surplus record.");
    } catch (nextError) {
      setError(message(nextError));
    } finally {
      setBusy(false);
    }
  }

  async function startRecording() {
    setError("");
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const preferred = ["audio/webm", "audio/mp4"].find((type) => MediaRecorder.isTypeSupported(type));
      const recorder = preferred ? new MediaRecorder(stream, { mimeType: preferred }) : new MediaRecorder(stream);
      chunksRef.current = [];
      recordingStreamRef.current = stream;
      recorderRef.current = recorder;
      recorder.addEventListener("dataavailable", (event) => {
        if (event.data.size) chunksRef.current.push(event.data);
      });
      recorder.addEventListener("stop", () => {
        const blob = new Blob(chunksRef.current, { type: recorder.mimeType || "audio/webm" });
        setMedia(blob);
        setRecording(false);
        stream.getTracks().forEach((track) => track.stop());
        recordingStreamRef.current = null;
        recorderRef.current = null;
      }, { once: true });
      recorder.start();
      setRecording(true);
    } catch {
      setError("Microphone access is unavailable. You can upload audio or enter the surplus manually.");
    }
  }

  function stopRecording() {
    if (recorderRef.current?.state === "recording") recorderRef.current.stop();
  }

  async function save() {
    if (!household.user || !household.householdId) return;
    if (!declarations.every(Boolean)) {
      setError("Confirm all five declarations before creating a demo surplus record.");
      return;
    }
    if (!draft.foodName.trim() || !draft.category || !draft.amount || !draft.unit || !draft.preparation || !draft.packaging) {
      setError("Complete every reviewed surplus field before confirming.");
      return;
    }
    if (draft.category === "prepared_food" && draft.preparation !== "unserved_prepared") {
      setError("Prepared food must be explicitly marked as unserved prepared food.");
      return;
    }
    const availableUntil = new Date(draft.availableUntil);
    if (!Number.isFinite(availableUntil.getTime()) || availableUntil <= new Date()) {
      setError("Choose a future availability deadline.");
      return;
    }
    saveKeyRef.current ||= crypto.randomUUID();
    setBusy(true);
    setError("");
    try {
      const token = await household.user.getIdToken();
      await confirmSurplus(token, household.householdId, {
        food_name: draft.foodName.trim(),
        category: draft.category,
        amount: draft.amount,
        unit: draft.unit,
        preparation_state: draft.preparation,
        packaging_state: draft.packaging,
        available_until: availableUntil.toISOString(),
        source_modality: draft.sourceModality,
      }, saveKeyRef.current);
      saveKeyRef.current = "";
      setCandidates([]);
      setSelectedCandidateIndex(0);
      setDraft(emptyDraft(mode));
      setDeclarations([false, false, false, false, false]);
      setTextInput("");
      setMedia(null);
      setNotice("Surplus confirmed for this household. No pickup or reservation was created.");
      await reload();
    } catch (nextError) {
      if (nextError instanceof CanonicalApiError && ["validation", "forbidden", "unauthenticated"].includes(nextError.code)) {
        saveKeyRef.current = "";
      }
      setError(message(nextError));
    } finally {
      setBusy(false);
    }
  }

  async function cancel(record: SurplusRecord) {
    if (!household.user || !household.householdId) return;
    const retryKey = cancelKeysRef.current.get(record.surplus_id) ?? crypto.randomUUID();
    cancelKeysRef.current.set(record.surplus_id, retryKey);
    setBusy(true);
    setError("");
    try {
      const token = await household.user.getIdToken();
      await cancelSurplus(token, household.householdId, record, retryKey);
      cancelKeysRef.current.delete(record.surplus_id);
      setNotice("Surplus cancelled. Any saved proposal using this version is now stale.");
      await reload();
    } catch (nextError) {
      if (nextError instanceof CanonicalApiError && ["validation", "forbidden", "unauthenticated", "conflict"].includes(nextError.code)) {
        cancelKeysRef.current.delete(record.surplus_id);
      }
      setError(message(nextError));
    } finally {
      setBusy(false);
    }
  }

  const activeProposal = proposals.find((proposal) => proposal.validity === "CURRENT" && proposal.route_status === "ready")
    ?? proposals[0];

  return (
    <div className="space-y-6">
      <section className="rounded-card bg-primary-container p-6 text-white shadow-card sm:p-8">
        <Badge tone="amber">DEMO ONLY</Badge>
        <h1 className="mt-4 text-3xl font-extrabold tracking-tight">Share household surplus</h1>
        <p className="mt-3 max-w-2xl text-sm leading-6 text-white/80">
          Describe food by text, image, or recorded voice. The agent creates editable candidates only; you confirm every fact before anything is saved.
        </p>
      </section>

      <Card className="p-5 sm:p-6">
        <Heading as="h2">1. Capture and review</Heading>
        <div className="mt-4 grid grid-cols-2 gap-2 sm:grid-cols-4" role="group" aria-label="Surplus input type">
          {(["text", "image", "audio", "manual"] as CaptureMode[]).map((value) => (
            <Button key={value} variant={mode === value ? "primary" : "secondary"} onClick={() => chooseMode(value)}>
              {value === "audio" ? "Voice" : value[0].toUpperCase() + value.slice(1)}
            </Button>
          ))}
        </div>
        {mode === "text" && (
          <div className="mt-4 space-y-2">
            <label htmlFor="surplus-description" className="text-sm font-semibold text-primary">Describe the surplus</label>
            <textarea id="surplus-description" value={textInput} onChange={(event) => setTextInput(event.target.value)} maxLength={8000} rows={4} className="w-full rounded-control border border-line bg-surface-muted p-4 text-sm focus:border-primary focus:outline-none focus:ring-2 focus:ring-primary/15" placeholder="For example: 3 kg sealed rice, available until this evening" />
          </div>
        )}
        {mode === "image" && (
          <div className="mt-4 space-y-2">
            <label htmlFor="surplus-image" className="text-sm font-semibold text-primary">Food image</label>
            <Input id="surplus-image" type="file" accept="image/jpeg,image/png,image/webp" onChange={(event) => setMedia(event.target.files?.[0] ?? null)} />
          </div>
        )}
        {mode === "audio" && (
          <div className="mt-4 space-y-3">
            <div className="flex flex-wrap gap-2">
              <Button onClick={() => void startRecording()} disabled={recording || busy}>Start recording</Button>
              <Button variant="secondary" onClick={stopRecording} disabled={!recording}>Stop</Button>
            </div>
            <label htmlFor="surplus-audio" className="block text-sm font-semibold text-primary">Or upload audio</label>
            <Input id="surplus-audio" type="file" accept="audio/mpeg,audio/mp4,audio/ogg,audio/wav,audio/webm" onChange={(event) => setMedia(event.target.files?.[0] ?? null)} />
            <p className="text-xs text-muted" role="status">{recording ? "Recording… stop when finished." : media ? "Audio is ready for one-time processing." : "No recording selected."}</p>
          </div>
        )}
        {mode !== "manual" && (
          <Button className="mt-4" onClick={() => void extract()} disabled={busy || (mode === "text" ? !textInput.trim() : !media)} aria-busy={busy}>
            {busy ? "Processing…" : "Create review candidates"}
          </Button>
        )}
        {candidates.length > 1 && (
          <div className="mt-4 flex flex-wrap gap-2" aria-label="Detected candidates">
            {candidates.map((item, index) => <Button key={`${item.food_name ?? "unknown"}-${index}`} size="sm" variant={selectedCandidateIndex === index ? "primary" : "secondary"} onClick={() => { setSelectedCandidateIndex(index); setDraft(draftFromCandidate(item, mode)); }}>{item.food_name ?? `Candidate ${index + 1}`}</Button>)}
          </div>
        )}

        <div className="mt-6 grid gap-4 sm:grid-cols-2">
          <label className="space-y-1 text-sm font-semibold text-primary">Food name<Input value={draft.foodName} onChange={(event) => setDraft((current) => ({ ...current, foodName: event.target.value }))} maxLength={100} /></label>
          <label className="space-y-1 text-sm font-semibold text-primary">Category<select value={draft.category} onChange={(event) => setDraft((current) => ({ ...current, category: event.target.value as Draft["category"] }))} className="min-h-12 w-full rounded-control border border-line bg-white px-4 text-ink"><option value="">Choose…</option>{categoryOptions.map((option) => <option key={option.value} value={option.value}>{option.label}</option>)}</select></label>
          <label className="space-y-1 text-sm font-semibold text-primary">Amount<Input inputMode="decimal" value={draft.amount} onChange={(event) => setDraft((current) => ({ ...current, amount: event.target.value }))} placeholder="2.5" /></label>
          <label className="space-y-1 text-sm font-semibold text-primary">Unit<select value={draft.unit} onChange={(event) => setDraft((current) => ({ ...current, unit: event.target.value as Draft["unit"] }))} className="min-h-12 w-full rounded-control border border-line bg-white px-4 text-ink"><option value="">Choose…</option>{unitOptions.map((value) => <option key={value} value={value}>{value}</option>)}</select></label>
          <label className="space-y-1 text-sm font-semibold text-primary">Preparation<select value={draft.preparation} onChange={(event) => setDraft((current) => ({ ...current, preparation: event.target.value as Draft["preparation"] }))} className="min-h-12 w-full rounded-control border border-line bg-white px-4 text-ink"><option value="">Choose…</option><option value="unprepared">Unprepared</option><option value="unserved_prepared">Prepared, never served</option><option value="packaged">Packaged</option></select></label>
          <label className="space-y-1 text-sm font-semibold text-primary">Packaging<select value={draft.packaging} onChange={(event) => setDraft((current) => ({ ...current, packaging: event.target.value as Draft["packaging"] }))} className="min-h-12 w-full rounded-control border border-line bg-white px-4 text-ink"><option value="">Choose…</option><option value="sealed">Sealed</option><option value="covered">Covered</option><option value="open">Open</option><option value="unpackaged">Unpackaged</option></select></label>
          <label className="space-y-1 text-sm font-semibold text-primary sm:col-span-2">Available until<Input type="datetime-local" value={draft.availableUntil} onChange={(event) => setDraft((current) => ({ ...current, availableUntil: event.target.value }))} /></label>
        </div>
        {candidates[selectedCandidateIndex]?.evidence_note && <p className="mt-4 rounded-2xl bg-tertiary-soft p-3 text-sm text-tertiary">Agent evidence note: {candidates[selectedCandidateIndex].evidence_note}</p>}
        <div className="mt-5 space-y-2 rounded-2xl border border-line bg-surface-muted p-4">
          {[
            "I confirm this is the selected household location.",
            "This is not plate leftover food.",
            "I have not observed spoilage.",
            "The food is not expired.",
            "The food has not previously been served.",
          ].map((label, index) => (
            <label key={label} className="flex min-h-11 items-center gap-3 text-sm text-foreground"><input type="checkbox" checked={declarations[index]} onChange={(event) => setDeclarations((current) => current.map((value, itemIndex) => itemIndex === index ? event.target.checked : value))} className="size-5 accent-primary" /><span>{label}</span></label>
          ))}
        </div>
        <p className="mt-3 text-xs leading-5 text-muted">EcoLoop and its agents do not certify food safety. Prepared food remains a simulated demo case requiring qualified human review before any real-world program.</p>
        <Button className="mt-4" onClick={() => void save()} disabled={busy || !declarations.every(Boolean)} aria-busy={busy}>Confirm demo surplus</Button>
        {notice && <p role="status" className="mt-4 rounded-2xl bg-primary-soft p-3 text-sm text-primary">{notice}</p>}
        {error && <p role="alert" className="mt-4 rounded-2xl bg-danger-soft p-3 text-sm text-danger">{error}</p>}
      </Card>

      <Card className="p-5 sm:p-6">
        <div className="flex items-center justify-between gap-3"><Heading as="h2">2. Your confirmed surplus</Heading><Button size="sm" variant="ghost" onClick={() => void reload()} disabled={loading || busy}>Reload</Button></div>
        {loading ? <p className="mt-4 text-sm text-muted">Loading household surplus…</p> : records.length === 0 ? <p className="mt-4 text-sm text-muted">No confirmed surplus yet.</p> : <ul className="mt-4 space-y-3">{records.map((record) => <li key={record.surplus_id} className="rounded-2xl border border-line bg-surface-muted p-4"><div className="flex flex-wrap items-start justify-between gap-3"><div><p className="font-bold text-primary">{record.food_name}</p><p className="mt-1 text-sm text-muted">{record.amount} {record.unit} · until {new Date(record.available_until).toLocaleString()}</p><p className="mt-1 text-xs text-muted">{record.location.address}</p></div><Badge tone={record.status === "CONFIRMED" ? "green" : "neutral"}>{record.status}</Badge></div>{record.requires_qualified_review && <p className="mt-2 text-xs text-tertiary">Prepared-food demo: qualified review would be required for real collection.</p>}{record.status === "CONFIRMED" && <Button className="mt-3" size="sm" variant="danger" onClick={() => void cancel(record)} disabled={busy}>Cancel surplus</Button>}</li>)}</ul>}
      </Card>

      <Card className="p-5 sm:p-6">
        <Heading as="h2">3. Collection proposal</Heading>
        {!activeProposal ? <p className="mt-4 text-sm text-muted">No NGO collection proposal includes this household yet.</p> : <div className="mt-4 space-y-4"><div className="flex flex-wrap gap-2"><Badge tone="amber">ADVISORY DEMO</Badge><Badge tone={activeProposal.validity === "STALE" ? "neutral" : "green"}>{activeProposal.validity}</Badge></div><p className="text-sm leading-6 text-muted">Proposal {activeProposal.proposal_id}: {activeProposal.matched_amount} {activeProposal.unit} matched, {activeProposal.unmet_amount} {activeProposal.unit} unmet. This does not reserve food or dispatch a driver.</p><p className="rounded-2xl bg-primary-soft p-3 text-sm text-primary">{activeProposal.explanation}</p>{activeProposal.stale_reason && <p className="rounded-2xl bg-tertiary-soft p-3 text-sm text-tertiary">{activeProposal.stale_reason}</p>}{activeProposal.selected_stops[0] && <PickupPointMap location={activeProposal.selected_stops[0].location} />}{activeProposal.route_available ? <p className="text-sm text-muted">The allowlisted NGO has a saved Google route. Its full geometry and other exact pickup stops are hidden from household accounts.</p> : <p className="text-sm text-muted">Google Routes did not return usable route geometry for this proposal.</p>}<ol className="space-y-2">{activeProposal.selected_stops.map((stop) => <li key={stop.surplus_id} className="rounded-2xl bg-surface-muted p-3 text-sm"><span className="font-bold text-primary">Your proposed pickup:</span> {stop.food_name}, {stop.pickup_amount} {stop.unit} — {stop.location.address}</li>)}</ol></div>}
      </Card>
    </div>
  );
}
