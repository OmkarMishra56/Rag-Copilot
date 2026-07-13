"use client";

import { useEffect, useState } from "react";
import { Terminal } from "lucide-react";
import ChatWindow from "@/components/ChatWindow";
import UploadPanel from "@/components/UploadPanel";
import { login, register } from "@/lib/api";

export default function Page() {
  const [token, setToken] = useState<string | null>(null);
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [mode, setMode] = useState<"login" | "register">("login");
  const [error, setError] = useState("");

  useEffect(() => {
    const stored = localStorage.getItem("copilot_token");
    if (stored) setToken(stored);
  }, []);

  const handleAuth = async () => {
    setError("");
    try {
      const t = mode === "login" ? await login(email, password) : await register(email, password, "");
      localStorage.setItem("copilot_token", t);
      setToken(t);
    } catch {
      setError("Authentication failed. Check your credentials.");
    }
  };

  if (!token) {
    return (
      <main className="flex min-h-screen items-center justify-center px-4">
        <div className="w-full max-w-sm rounded-xl border border-line bg-panel p-6">
          <div className="mb-5 flex items-center gap-2 text-signal">
            <Terminal size={18} />
            <span className="font-mono text-sm">SUPPORT_COPILOT</span>
          </div>
          <div className="mb-4 flex gap-1 rounded-lg border border-line p-1 text-xs">
            {(["login", "register"] as const).map((m) => (
              <button
                key={m}
                onClick={() => setMode(m)}
                className={`flex-1 rounded-md py-1.5 capitalize transition-colors ${
                  mode === m ? "bg-signal text-ink" : "text-muted"
                }`}
              >
                {m}
              </button>
            ))}
          </div>
          <input
            type="email"
            placeholder="agent@company.com"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            className="mb-2 w-full rounded-md border border-line bg-ink px-3 py-2 text-sm outline-none focus:border-signal"
          />
          <input
            type="password"
            placeholder="Password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && handleAuth()}
            className="mb-3 w-full rounded-md border border-line bg-ink px-3 py-2 text-sm outline-none focus:border-signal"
          />
          {error && <p className="mb-3 text-xs text-alert">{error}</p>}
          <button
            onClick={handleAuth}
            className="w-full rounded-md bg-signal py-2 text-sm font-medium text-ink hover:opacity-90"
          >
            {mode === "login" ? "Sign in" : "Create account"}
          </button>
        </div>
      </main>
    );
  }

  return (
    <main className="grid h-screen grid-cols-[280px_1fr]">
      <aside className="border-r border-line bg-panel/40">
        <div className="flex items-center gap-2 border-b border-line px-4 py-3 text-signal">
          <Terminal size={16} />
          <span className="font-mono text-xs">SUPPORT_COPILOT</span>
        </div>
        <UploadPanel token={token} />
      </aside>
      <section className="min-w-0">
        <ChatWindow token={token} />
      </section>
    </main>
  );
}
