import {
  Check,
  Copy,
  FileSpreadsheet,
  FileText,
  Loader2,
  Phone,
  User,
} from "lucide-react";
import type { LucideIcon } from "lucide-react";
import { useState } from "react";
import {
  ApiError,
  exports,
  type ContactCardData,
  type ExportFilter,
} from "../api/client";

/**
 * "Make this a list" affordance — sits above a ContactCardList and lets
 * the user generate a copy-paste-ready text version of the cards in
 * three formats:
 *   - Names only (first + last)
 *   - Names + phone numbers
 *   - Full details (title, company, email, both phones)
 *
 * Plus an Export button (when `exportFilter` is provided) that reproduces
 * the search server-side as a Google Sheet, with automatic CSV download
 * fallback if the user hasn't granted the drive.file scope.
 *
 * Future hooks (captured in Future_Ideas/list-export-targets.md):
 *   - Send to my email
 *   - Save to Google Drive as a doc
 *   - Save to Google Keep as a checklist
 */

type Format = "names" | "phones" | "full";

const FORMAT_LABELS: Record<Format, string> = {
  names: "Names",
  phones: "Names + phones",
  full: "Full details",
};

const FORMAT_ICONS: Record<Format, LucideIcon> = {
  names: User,
  phones: Phone,
  full: FileText,
};

function formatNamesOnly(c: ContactCardData): string {
  return c.name;
}

function formatNamesPhones(c: ContactCardData): string {
  const phones = [c.cell_phone, c.office_phone].filter(Boolean).join(" / ");
  return phones ? `${c.name} — ${phones}` : c.name;
}

function formatFull(c: ContactCardData): string {
  const lines: string[] = [c.name];
  if (c.title || c.company_name) {
    lines.push([c.title, c.company_name].filter(Boolean).join(", "));
  }
  if (c.email) lines.push(c.email);
  if (c.cell_phone) lines.push(`Cell: ${c.cell_phone}`);
  if (c.office_phone) lines.push(`Office: ${c.office_phone}`);
  return lines.join("\n");
}

function formatList(contacts: ContactCardData[], format: Format): string {
  switch (format) {
    case "names":
      return contacts.map(formatNamesOnly).join("\n");
    case "phones":
      return contacts.map(formatNamesPhones).join("\n");
    case "full":
      return contacts.map(formatFull).join("\n\n");
  }
}

interface ContactListExportProps {
  contacts: ContactCardData[];
  /** When provided, render an "Export to Sheet" button that POSTs this
   *  filter to /export/sheets. Without it the toolbar shows only the
   *  clipboard "Make a list" affordances. */
  exportFilter?: ExportFilter;
}

type ExportState =
  | { kind: "idle" }
  | { kind: "running" }
  | { kind: "error"; message: string };

function _triggerCsvDownload(blob: Blob, filename: string): void {
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  // Small delay so Safari has time to start the download before we revoke.
  window.setTimeout(() => URL.revokeObjectURL(url), 1000);
}

function _exportErrorMessage(e: unknown): string {
  if (e instanceof ApiError) {
    if (e.status === 412) {
      return "Sign out and back in to grant Google Drive access, then retry.";
    }
    if (e.status === 404) return "No contacts matched — nothing to export.";
    if (e.status === 429)
      return "Google rate limit hit. Try again in a minute.";
    if (e.status >= 500) return "Export failed. Try again.";
    return `Export failed (${e.status}).`;
  }
  return "Network error. Check your connection and retry.";
}

export function ContactListExport({
  contacts,
  exportFilter,
}: ContactListExportProps) {
  const [activeFormat, setActiveFormat] = useState<Format | null>(null);
  const [copied, setCopied] = useState(false);
  const [exportState, setExportState] = useState<ExportState>({ kind: "idle" });

  const text = activeFormat ? formatList(contacts, activeFormat) : "";

  const handleCopy = async () => {
    if (!text) return;
    try {
      await navigator.clipboard.writeText(text);
      setCopied(true);
      window.setTimeout(() => setCopied(false), 1500);
    } catch {
      // Clipboard API can fail in some browsers — fall back to manual select.
    }
  };

  const select = (f: Format) => {
    setActiveFormat((cur) => (cur === f ? null : f));
    setCopied(false);
  };

  const handleExport = async () => {
    if (!exportFilter || exportState.kind === "running") return;
    setExportState({ kind: "running" });
    try {
      const result = await exports.exportSheets(exportFilter);
      if (result.kind === "sheet") {
        // Open the new sheet in a separate tab so the chat history isn't
        // lost. window.open inside an async handler can be popup-blocked
        // on some browsers; if it returns null, fall back to assigning
        // the current tab's location.
        const opened = window.open(result.sheet_url, "_blank", "noopener");
        if (!opened) window.location.href = result.sheet_url;
      } else {
        _triggerCsvDownload(result.blob, result.filename);
      }
      setExportState({ kind: "idle" });
    } catch (e) {
      setExportState({ kind: "error", message: _exportErrorMessage(e) });
    }
  };

  return (
    <div className="rounded-md border border-din-blue/20 bg-white/70 p-2 text-xs dark:border-din-cream/15 dark:bg-din-navy-soft/40">
      <div className="flex flex-wrap items-center gap-2">
        {(Object.keys(FORMAT_LABELS) as Format[]).map((f) => {
          const active = activeFormat === f;
          const Icon = FORMAT_ICONS[f];
          return (
            <button
              key={f}
              type="button"
              onClick={() => select(f)}
              aria-label={FORMAT_LABELS[f]}
              aria-pressed={active}
              title={FORMAT_LABELS[f]}
              className={`inline-flex h-7 w-7 items-center justify-center rounded-full border transition-colors ${
                active
                  ? "border-din-blue bg-din-blue text-white dark:border-din-cream dark:bg-din-cream dark:text-din-navy"
                  : "border-din-blue/30 text-din-blue hover:bg-din-blue/5 dark:border-din-cream/30 dark:text-din-cream/85 dark:hover:bg-din-cream/10"
              }`}
            >
              <Icon size={14} />
            </button>
          );
        })}

        {exportFilter ? (
          <button
            type="button"
            onClick={handleExport}
            disabled={exportState.kind === "running"}
            aria-label={
              exportState.kind === "running"
                ? "Exporting to Sheet"
                : "Export to Sheet"
            }
            title="Export to Sheet"
            className="ml-auto inline-flex h-7 w-7 items-center justify-center rounded-full border border-din-gold bg-din-gold text-din-navy transition-colors hover:bg-din-gold/80 disabled:cursor-not-allowed disabled:opacity-60"
          >
            {exportState.kind === "running" ? (
              <Loader2 size={14} className="animate-spin" />
            ) : (
              <FileSpreadsheet size={14} />
            )}
          </button>
        ) : null}
      </div>

      {exportState.kind === "error" ? (
        <div className="mt-2 rounded border border-din-red/40 bg-din-red/5 px-2 py-1 text-[11px] text-din-red dark:text-din-red-soft">
          {exportState.message}
        </div>
      ) : null}

      {activeFormat ? (
        <div className="mt-2">
          <textarea
            readOnly
            value={text}
            rows={Math.min(12, Math.max(3, text.split("\n").length))}
            className="w-full resize-y rounded border border-din-blue/20 bg-din-cream-soft p-2 font-mono text-[11px] leading-snug text-din-navy dark:border-din-cream/15 dark:bg-din-navy dark:text-din-cream"
            onFocus={(e) => e.currentTarget.select()}
          />
          <div className="mt-2 flex justify-end">
            <button
              type="button"
              onClick={handleCopy}
              className="inline-flex items-center gap-1 rounded bg-din-blue px-3 py-1 text-[11px] font-bold uppercase tracking-wide text-white hover:bg-din-blue-dark dark:bg-din-cream dark:text-din-navy dark:hover:bg-din-cream/85"
            >
              {copied ? <Check size={12} /> : <Copy size={12} />}
              {copied ? "Copied" : "Copy"}
            </button>
          </div>
        </div>
      ) : null}
    </div>
  );
}
