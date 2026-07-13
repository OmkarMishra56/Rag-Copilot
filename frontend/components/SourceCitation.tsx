"use client";

import { FileText, FileCode2, Globe, FileSpreadsheet, FileJson } from "lucide-react";
import type { Source } from "@/lib/api";

const ICONS: Record<string, any> = {
  pdf: FileText,
  docx: FileText,
  md: FileCode2,
  markdown: FileCode2,
  html: Globe,
  csv: FileSpreadsheet,
  json: FileJson,
};

export default function SourceCitation({ sources }: { sources: Source[] }) {
  if (!sources.length) return null;

  return (
    <div className="mt-3 flex flex-wrap gap-2">
      {sources.map((s) => {
        const Icon = ICONS[s.source_type || ""] || FileText;
        return (
          <div
            key={s.index}
            className="group relative flex items-center gap-1.5 rounded-md border border-line bg-panel px-2 py-1 text-xs text-muted hover:border-signal/60 hover:text-signal transition-colors"
            title={s.excerpt}
          >
            <span className="font-mono text-[10px] text-signal">[{s.index}]</span>
            <Icon size={12} />
            <span className="max-w-[140px] truncate">{s.filename}</span>
            {s.version ? <span className="font-mono text-[10px] text-muted">v{s.version}</span> : null}
            <div className="pointer-events-none absolute bottom-full left-0 z-10 mb-2 hidden w-72 rounded-md border border-line bg-ink p-3 text-[11px] leading-relaxed text-[#C4CCD6] shadow-xl group-hover:block">
              <div className="mb-1 font-mono text-signal">
                {s.filename} · relevance {(s.rerank_score * 100).toFixed(0)}%
              </div>
              {s.excerpt}
            </div>
          </div>
        );
      })}
    </div>
  );
}
