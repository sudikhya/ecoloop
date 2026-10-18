"use client";

import { useEffect, useState, type FormEvent } from "react";
import { useRouter } from "next/navigation";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Heading } from "@/components/ui/heading";
import { Input } from "@/components/ui/input";
import { getFirebaseClient } from "@/lib/firebase-client";
import { useLiveHousehold } from "@/lib/live-household";
import { readNgoAccount } from "@/lib/recovery-api";

function authMessage(error: unknown): string {
  const code = typeof error === "object" && error !== null && "code" in error && typeof error.code === "string" ? error.code : "";
  if (["auth/invalid-credential", "auth/user-not-found", "auth/wrong-password"].includes(code)) return "The email or password is incorrect.";
  if (code === "auth/too-many-requests") return "Firebase temporarily paused sign-in attempts. Wait and retry.";
  if (code === "auth/network-request-failed") return "Firebase Authentication could not be reached.";
  return error instanceof Error ? error.message : "NGO sign-in could not be completed.";
}

export function NgoLogin() {
  const router = useRouter();
  const household = useLiveHousehold();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    if (!household.user) return;
    let active = true;
    void household.user.getIdToken()
      .then(readNgoAccount)
      .then(() => {
        if (active) router.replace("/ngo");
      })
      .catch((nextError: unknown) => {
        if (active) setError(nextError instanceof Error ? nextError.message : "This account is not authorized for the NGO pilot.");
      });
    return () => { active = false; };
  }, [household.user, router]);

  async function signIn(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setBusy(true);
    setError("");
    try {
      const firebase = await getFirebaseClient();
      if (!firebase) throw new Error("Firebase Authentication is not configured.");
      const { signInWithEmailAndPassword, signOut } = await import("firebase/auth");
      const credential = await signInWithEmailAndPassword(firebase.auth, email.trim(), password);
      try {
        await readNgoAccount(await credential.user.getIdToken());
      } catch (nextError) {
        await signOut(firebase.auth);
        throw nextError;
      }
      setPassword("");
      router.replace("/ngo");
    } catch (nextError) {
      setError(authMessage(nextError));
    } finally {
      setBusy(false);
    }
  }

  async function signOutCurrent() {
    const firebase = await getFirebaseClient();
    if (!firebase) return;
    const { signOut } = await import("firebase/auth");
    await signOut(firebase.auth);
    setError("");
  }

  return (
    <div className="mx-auto max-w-md py-6 sm:py-12">
      <Card className="p-6 sm:p-8">
        <Badge tone="amber">ISOLATED DEMO</Badge>
        <Heading as="h1" className="mt-4">NGO collection pilot</Heading>
        <p className="mt-3 text-sm leading-6 text-muted">Sign in with the separate dummy NGO account. Household accounts are not authorized here.</p>
        <form onSubmit={signIn} className="mt-6 space-y-4">
          <label className="block space-y-1 text-sm font-semibold text-primary">Email<Input type="email" value={email} onChange={(event) => setEmail(event.target.value)} autoComplete="username" required /></label>
          <label className="block space-y-1 text-sm font-semibold text-primary">Password<Input type="password" value={password} onChange={(event) => setPassword(event.target.value)} autoComplete="current-password" minLength={6} required /></label>
          <Button type="submit" fullWidth disabled={busy} aria-busy={busy}>{busy ? "Checking NGO access…" : "Sign in to NGO portal"}</Button>
        </form>
        {household.user && <Button className="mt-3" variant="ghost" fullWidth onClick={() => void signOutCurrent()}>Sign out current account</Button>}
        {error && <p className="mt-4 rounded-2xl bg-danger-soft p-3 text-sm text-danger" role="alert">{error}</p>}
        <p className="mt-5 text-xs leading-5 text-muted">No self-registration is available. NGO access comes only from a server-owned demo allowlist.</p>
      </Card>
    </div>
  );
}
