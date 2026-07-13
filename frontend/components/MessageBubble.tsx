"use client";

import { useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { Prism as SyntaxHighlighter } from "react-syntax-highlighter";
import { oneDark } from "react-syntax-highlighter/dist/esm/styles/prism";
import { Copy, Check, Bot, User as UserIcon } from "lucide-react";
import clsx from "clsx";
import SourceCitation from "./SourceCitation";
import type { ChatMessage } from "@/lib/api";

export default function MessageBubble({ message, streaming }: { message: ChatMessage; streaming?: boolean }) {
  const [copied, setCopied] = useState(false);
  const isUser = message.role === "user";

  const handleCopy = async () => {
    await navigator.clipboard.writeText(message.content);
    setCopied(true);
    setTimeout(() => setCopied(false), 1500);
  };

  return (
    <div className={clsx("flex gap-3 py-4", isUser && "flex-row-reverse")}>
      <div
        className={clsx(
          "flex h-7 w-7 flex-shrink-0 items-center justify-center rounded-md border",
          isUser ? "border-line bg-panel text-muted" : "border-signal/40 bg-signal/10 text-signal"
        )}
      >
        {isUser ? <UserIcon size={14} /> : <Bot size={14} />}
      </div>

      <div className={clsx("group max-w-[75%] flex-1", isUser && "flex flex-col items-end")}>
        <div
          className={clsx(
            "rounded-xl border px-4 py-3 text-[13.5px] leading-relaxed",
            isUser ? "border-line bg-panel text-[#E6EBF1]" : "border-line bg-[#0F141A] text-[#DCE3EA]"
          )}
        >
          <div className="prose-copilot">
            <ReactMarkdown
              remarkPlugins={[remarkGfm]}
              components={{
                code({ className, children, ...props }: any) {
                  const match = /language-(\w+)/.exec(className || "");
                  return match ? (
                    <SyntaxHighlighter style={oneDark as any} language={match[1]} PreTag="div">
                      {String(children).replace(/\n$/, "")}
                    </SyntaxHighlighter>
                  ) : (
                    <code className={className} {...props}>
                      {children}
                    </code>
                  );
                },
              }}
            >
              {message.content || " "}
            </ReactMarkdown>
            {streaming && <span className="cursor-blink text-signal">▍</span>}
          </div>
        </div>

        {!isUser && message.citations?.length > 0 && <SourceCitation sources={message.citations} />}

        {!isUser && message.content && (
          <button
            onClick={handleCopy}
            className="mt-1.5 flex items-center gap-1 text-[11px] text-muted opacity-0 transition-opacity hover:text-signal group-hover:opacity-100"
          >
            {copied ? <Check size={12} /> : <Copy size={12} />}
            {copied ? "Copied" : "Copy"}
          </button>
        )}
      </div>
    </div>
  );
}
