"use client";

import { useRef, useState } from "react";
import { Send, Loader2 } from "lucide-react";
import MessageBubble from "./MessageBubble";
import { streamQuery, type ChatMessage } from "@/lib/api";

export default function ChatWindow({ token }: { token: string }) {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState("");
  const [chatId, setChatId] = useState<string | null>(null);
  const [streaming, setStreaming] = useState(false);
  const bottomRef = useRef<HTMLDivElement>(null);

  const scrollToBottom = () => setTimeout(() => bottomRef.current?.scrollIntoView({ behavior: "smooth" }), 50);

  const handleSend = async () => {
    const question = input.trim();
    if (!question || streaming) return;

    const userMsg: ChatMessage = { id: crypto.randomUUID(), role: "user", content: question, citations: [] };
    const assistantId = crypto.randomUUID();
    setMessages((prev) => [...prev, userMsg, { id: assistantId, role: "assistant", content: "", citations: [] }]);
    setInput("");
    setStreaming(true);
    scrollToBottom();

    await streamQuery(token, question, chatId, {
      onSources: (sources) => {
        setMessages((prev) => prev.map((m) => (m.id === assistantId ? { ...m, citations: sources } : m)));
      },
      onToken: (tok) => {
        setMessages((prev) =>
          prev.map((m) => (m.id === assistantId ? { ...m, content: m.content + tok } : m))
        );
        scrollToBottom();
      },
      onDone: (id) => {
        setChatId(id);
        setStreaming(false);
      },
      onError: (err) => {
        setMessages((prev) =>
          prev.map((m) => (m.id === assistantId ? { ...m, content: `⚠️ ${err}` } : m))
        );
        setStreaming(false);
      },
    });
  };

  return (
    <div className="flex h-full flex-col">
      <div className="flex-1 overflow-y-auto scrollbar-thin px-6">
        {messages.length === 0 && (
          <div className="flex h-full flex-col items-center justify-center text-center text-muted">
            <p className="font-mono text-sm text-signal">SUPPORT_COPILOT // READY</p>
            <p className="mt-2 max-w-sm text-sm">
              Ask a question about your product docs, policies, or release notes. Answers are grounded in your
              indexed knowledge base with inline citations.
            </p>
          </div>
        )}
        <div className="mx-auto max-w-3xl divide-y divide-line/50">
          {messages.map((m) => (
            <MessageBubble key={m.id} message={m} streaming={streaming && m.role === "assistant" && m === messages[messages.length - 1]} />
          ))}
        </div>
        <div ref={bottomRef} />
      </div>

      <div className="border-t border-line p-4">
        <div className="mx-auto flex max-w-3xl items-end gap-2 rounded-xl border border-line bg-panel p-2">
          <textarea
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter" && !e.shiftKey) {
                e.preventDefault();
                handleSend();
              }
            }}
            rows={1}
            placeholder="Ask about refund policy, API auth, release notes…"
            className="max-h-32 flex-1 resize-none bg-transparent px-2 py-1.5 text-sm outline-none placeholder:text-muted"
          />
          <button
            onClick={handleSend}
            disabled={streaming || !input.trim()}
            className="flex h-8 w-8 flex-shrink-0 items-center justify-center rounded-lg bg-signal text-ink transition-opacity disabled:opacity-30"
          >
            {streaming ? <Loader2 size={15} className="animate-spin" /> : <Send size={15} />}
          </button>
        </div>
      </div>
    </div>
  );
}
