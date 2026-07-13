const BASE = "/api/backend";

export type Source = {
  index: number;
  filename: string;
  source_type: string | null;
  version: number | null;
  excerpt: string;
  rerank_score: number;
};

export type ChatMessage = {
  id: string;
  role: "user" | "assistant";
  content: string;
  citations: Source[];
};

function authHeaders(token: string | null): Record<string, string> {
  return token ? { Authorization: `Bearer ${token}` } : {};
}

export async function login(email: string, password: string): Promise<string> {
  const body = new URLSearchParams({ username: email, password });
  const res = await fetch(`${BASE}/auth/login`, {
    method: "POST",
    headers: { "Content-Type": "application/x-www-form-urlencoded" },
    body,
  });
  if (!res.ok) throw new Error("Login failed");
  const data = await res.json();
  return data.access_token;
}

export async function register(email: string, password: string, fullName: string): Promise<string> {
  const res = await fetch(`${BASE}/auth/register`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email, password, full_name: fullName }),
  });
  if (!res.ok) throw new Error("Registration failed");
  const data = await res.json();
  return data.access_token;
}

export async function uploadFiles(token: string, files: File[]) {
  const formData = new FormData();
  files.forEach((f) => formData.append("files", f));
  const res = await fetch(`${BASE}/upload`, {
    method: "POST",
    headers: authHeaders(token),
    body: formData,
  });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

export async function listDocuments(token: string) {
  const res = await fetch(`${BASE}/documents`, { headers: authHeaders(token) });
  if (!res.ok) throw new Error("Failed to load documents");
  return res.json();
}

export async function deleteDocument(token: string, id: string) {
  const res = await fetch(`${BASE}/documents/${id}`, { method: "DELETE", headers: authHeaders(token) });
  if (!res.ok) throw new Error("Failed to delete document");
}

/**
 * Streams a RAG query via SSE. Calls onSources once, onToken repeatedly,
 * and onDone when the stream completes (with the resolved chat_id).
 */
export async function streamQuery(
  token: string,
  question: string,
  chatId: string | null,
  handlers: {
    onSources: (sources: Source[]) => void;
    onToken: (token: string) => void;
    onDone: (chatId: string) => void;
    onError: (message: string) => void;
  }
) {
  try {
    const res = await fetch(`${BASE}/query`, {
      method: "POST",
      headers: { "Content-Type": "application/json", ...authHeaders(token) },
      body: JSON.stringify({ question, chat_id: chatId }),
    });

    if (!res.ok || !res.body) {
      handlers.onError(`Request failed (${res.status})`);
      return;
    }

    const reader = res.body.getReader();
    const decoder = new TextDecoder();
    let buffer = "";

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });

      const events = buffer.split("\n\n");
      buffer = events.pop() || "";

      for (const raw of events) {
        const eventMatch = raw.match(/^event:\s*(.*)$/m);
        const dataMatch = raw.match(/^data:\s*(.*)$/m);
        const event = eventMatch?.[1]?.trim();
        const data = dataMatch?.[1] ?? "";

        if (event === "sources") handlers.onSources(JSON.parse(data));
        else if (event === "token") handlers.onToken(data);
        else if (event === "done") handlers.onDone(JSON.parse(data).chat_id);
      }
    }
  } catch (err) {
    handlers.onError(err instanceof Error ? err.message : "Stream error");
  }
}
