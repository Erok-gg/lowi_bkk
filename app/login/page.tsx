"use client";

import { Suspense, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";

function LoginForm() {
  const router = useRouter();
  const params = useSearchParams();
  const next = params.get("next") || "/";
  const [pw, setPw] = useState("");
  const [err, setErr] = useState(false);
  const [loading, setLoading] = useState(false);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setLoading(true);
    setErr(false);
    const res = await fetch("/api/login", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ password: pw }),
    });
    setLoading(false);
    if (res.ok) router.replace(next);
    else setErr(true);
  }

  return (
    <div className="flex h-full w-full items-center justify-center bg-anthracite-deep">
      <form
        onSubmit={submit}
        className="w-80 rounded-xl border border-violet-soft bg-surface p-6 shadow-xl"
      >
        <div className="mb-1 font-logo text-3xl">
          <span className="text-gold">lowi</span>
          <span className="ml-1 align-middle text-[11px] uppercase tracking-widest text-text-faint">
            bkk
          </span>
        </div>
        <p className="mb-5 text-sm text-text-muted">Accès privé</p>
        <input
          type="password"
          autoFocus
          value={pw}
          onChange={(e) => setPw(e.target.value)}
          placeholder="Mot de passe"
          className="mb-3 w-full rounded-md border border-violet-soft bg-anthracite-deep px-3 py-2 text-text outline-none focus:border-violet-fluo"
        />
        {err && <p className="mb-3 text-sm text-red-400">Mot de passe incorrect.</p>}
        <button
          type="submit"
          disabled={loading}
          className="w-full rounded-md bg-violet px-3 py-2 font-medium text-white transition hover:bg-violet-fluo disabled:opacity-50"
        >
          {loading ? "…" : "Entrer"}
        </button>
      </form>
    </div>
  );
}

export default function LoginPage() {
  return (
    <Suspense>
      <LoginForm />
    </Suspense>
  );
}
