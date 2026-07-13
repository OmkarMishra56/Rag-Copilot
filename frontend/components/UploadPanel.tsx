"use client";

import { useCallback, useEffect, useState } from "react";
import { UploadCloud, Trash2, Loader2, CheckCircle2, XCircle, Clock } from "lucide-react";
import { deleteDocument, listDocuments, uploadFiles } from "@/lib/api";

type Doc = {
  id: string;
  filename: string;
  source_type: string;
  version: number;
  status: string;
};

const STATUS_ICON: Record<string, any> = {
  indexed: CheckCircle2,
  processing: Loader2,
  pending: Clock,
  failed: XCircle,
};

export default function UploadPanel({ token }: { token: string }) {
  const [docs, setDocs] = useState<Doc[]>([]);
  const [dragOver, setDragOver] = useState(false);
  const [uploading, setUploading] = useState(false);

  const refresh = useCallback(async () => {
    try {
      setDocs(await listDocuments(token));
    } catch {
      // knowledge base list is best-effort; ignore transient errors
    }
  }, [token]);

  useEffect(() => {
    refresh();
  }, [refresh]);

  const handleFiles = async (files: FileList | null) => {
    if (!files || files.length === 0) return;
    setUploading(true);
    try {
      await uploadFiles(token, Array.from(files));
      await refresh();
    } catch (err) {
      console.error(err);
    } finally {
      setUploading(false);
    }
  };

  return (
    <div className="flex h-full flex-col">
      <div
        onDragOver={(e) => {
          e.preventDefault();
          setDragOver(true);
        }}
        onDragLeave={() => setDragOver(false)}
        onDrop={(e) => {
          e.preventDefault();
          setDragOver(false);
          handleFiles(e.dataTransfer.files);
        }}
        className={`m-3 flex flex-col items-center justify-center gap-2 rounded-lg border-2 border-dashed p-6 text-center text-xs transition-colors ${
          dragOver ? "border-signal bg-signal/5 text-signal" : "border-line text-muted"
        }`}
      >
        {uploading ? <Loader2 size={20} className="animate-spin text-signal" /> : <UploadCloud size={20} />}
        <p>{uploading ? "Ingesting…" : "Drag files here or"}</p>
        <label className="cursor-pointer text-signal underline underline-offset-2">
          browse
          <input
            type="file"
            multiple
            className="hidden"
            accept=".pdf,.docx,.md,.txt,.html,.csv,.json"
            onChange={(e) => handleFiles(e.target.files)}
          />
        </label>
        <p className="text-[10px] text-muted">PDF · DOCX · MD · TXT · HTML · CSV · JSON</p>
      </div>

      <div className="flex-1 overflow-y-auto scrollbar-thin px-3 pb-3">
        <p className="mb-2 px-1 font-mono text-[10px] uppercase tracking-wider text-muted">Knowledge base</p>
        <div className="flex flex-col gap-1.5">
          {docs.map((d) => {
            const Icon = STATUS_ICON[d.status] || Clock;
            return (
              <div
                key={d.id}
                className="group flex items-center justify-between rounded-md border border-line bg-panel px-2.5 py-2 text-xs"
              >
                <div className="flex min-w-0 items-center gap-2">
                  <Icon size={13} className={d.status === "processing" ? "animate-spin text-signal" : "text-muted"} />
                  <span className="truncate">{d.filename}</span>
                  <span className="flex-shrink-0 font-mono text-[10px] text-muted">v{d.version}</span>
                </div>
                <button
                  onClick={async () => {
                    await deleteDocument(token, d.id);
                    refresh();
                  }}
                  className="opacity-0 transition-opacity hover:text-alert group-hover:opacity-100"
                >
                  <Trash2 size={13} />
                </button>
              </div>
            );
          })}
          {docs.length === 0 && <p className="px-1 text-xs text-muted">No documents indexed yet.</p>}
        </div>
      </div>
    </div>
  );
}
