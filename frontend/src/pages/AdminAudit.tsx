import { Download, Loader2 } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import {
  admin,
  ApiError,
  type AuditListResponse,
  type AuditListQuery,
  type CurrentUser,
  users,
} from "../api/client";
import { ColorModeToggle } from "../components/ColorModeToggle";
import { DinLogo } from "../components/DinLogo";

/**
 * Admin-only audit log viewer. Member-role users navigating directly
 * to /admin/audit see an access-denied state instead of the table —
 * the backend would return 403 anyway, but the UI flag is the user-
 * facing signal.
 *
 * Filters are simple text/number inputs for Phase 1. Action dropdown
 * could be enumerated when the action set stabilizes.
 */

const PAGE_SIZE = 50;

export default function AdminAudit() {
  const navigate = useNavigate();
  const [me, setMe] = useState<CurrentUser | null>(null);
  const [meLoading, setMeLoading] = useState(true);

  const [page, setPage] = useState(1);
  const [actionFilter, setActionFilter] = useState("");
  const [userIdFilter, setUserIdFilter] = useState("");
  const [data, setData] = useState<AuditListResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Fetch current user once for the role check.
  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const u = await users.me();
        if (!cancelled) {
          setMe(u);
          setMeLoading(false);
        }
      } catch {
        if (cancelled) return;
        navigate("/login", { replace: true });
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [navigate]);

  // Build the query from current filter state.
  const query: AuditListQuery = useMemo(
    () => ({
      page,
      page_size: PAGE_SIZE,
      action: actionFilter || undefined,
      user_id: userIdFilter ? Number(userIdFilter) : undefined,
    }),
    [page, actionFilter, userIdFilter],
  );

  // Fetch audit rows whenever filters or page change. Skip while we
  // don't yet know the user's role (avoid the doomed 403 round-trip).
  useEffect(() => {
    if (meLoading || !me || me.role !== "admin") return;
    let cancelled = false;
    setLoading(true);
    setError(null);
    admin
      .listAudit(query)
      .then((r) => {
        if (!cancelled) setData(r);
      })
      .catch((e: unknown) => {
        if (cancelled) return;
        const msg =
          e instanceof ApiError ? `${e.status} ${e.message}` : String(e);
        setError(msg);
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [query, me, meLoading]);

  if (meLoading) {
    return <CenteredMessage text="Loading…" />;
  }
  if (!me || me.role !== "admin") {
    return (
      <Shell>
        <div className="din-callout">
          <div className="font-bold uppercase tracking-wide text-din-red dark:text-din-red-soft">
            Access denied
          </div>
          <p className="mt-2 text-sm">
            The audit log is admin-only. If this looks wrong, ask Alex Rivera to
            flip your role.
          </p>
        </div>
      </Shell>
    );
  }

  const totalPages = data ? Math.max(1, Math.ceil(data.total / PAGE_SIZE)) : 1;

  return (
    <Shell>
      <div className="mb-4 flex items-end justify-between gap-4">
        <div>
          <h1>Audit Log</h1>
          <p className="mt-1 text-sm italic opacity-70">
            Every write recorded by the system. Newest first.
          </p>
        </div>
        <a
          href={admin.auditCsvUrl(query)}
          className="inline-flex h-9 items-center gap-1.5 rounded border border-din-blue/40 px-3 text-xs font-bold uppercase tracking-wide text-din-blue hover:bg-din-blue/5 dark:border-din-cream/30 dark:text-din-cream/90 dark:hover:bg-din-cream/10"
          target="_blank"
          rel="noopener noreferrer"
        >
          <Download size={14} />
          Download CSV
        </a>
      </div>

      <div className="mb-4 flex flex-wrap items-end gap-3 rounded border border-din-blue/20 bg-din-cream-soft/40 p-3 text-sm dark:border-din-cream/15 dark:bg-din-navy-soft/40">
        <label className="flex flex-col gap-1">
          <span className="text-[11px] font-bold uppercase tracking-wide opacity-70">
            Action
          </span>
          <input
            type="text"
            value={actionFilter}
            onChange={(e) => {
              setActionFilter(e.target.value);
              setPage(1);
            }}
            placeholder="e.g. export_sheet"
            className="h-8 w-44 rounded border border-din-blue/30 bg-white px-2 text-sm focus:border-din-blue focus:outline-none focus:ring-1 focus:ring-din-gold dark:border-din-cream/30 dark:bg-din-navy-soft"
          />
        </label>
        <label className="flex flex-col gap-1">
          <span className="text-[11px] font-bold uppercase tracking-wide opacity-70">
            User ID
          </span>
          <input
            type="number"
            value={userIdFilter}
            onChange={(e) => {
              setUserIdFilter(e.target.value);
              setPage(1);
            }}
            placeholder="e.g. 1"
            className="h-8 w-28 rounded border border-din-blue/30 bg-white px-2 text-sm focus:border-din-blue focus:outline-none focus:ring-1 focus:ring-din-gold dark:border-din-cream/30 dark:bg-din-navy-soft"
          />
        </label>
        {(actionFilter || userIdFilter) && (
          <button
            type="button"
            onClick={() => {
              setActionFilter("");
              setUserIdFilter("");
              setPage(1);
            }}
            className="h-8 self-end rounded px-2 text-[11px] font-bold uppercase tracking-wide text-din-blue hover:underline dark:text-din-cream/85"
          >
            clear
          </button>
        )}
      </div>

      {error ? (
        <div className="mb-4 rounded border border-din-red/40 bg-din-red/5 p-3 text-sm text-din-red dark:text-din-red-soft">
          Failed to load: {error}
        </div>
      ) : null}

      <div className="overflow-x-auto rounded border border-din-blue/20 dark:border-din-cream/15">
        <table className="w-full min-w-[720px] text-left text-sm">
          <thead className="bg-din-cream-soft text-[11px] font-bold uppercase tracking-wide text-din-blue dark:bg-din-navy-soft dark:text-din-cream/80">
            <tr>
              <th className="px-3 py-2">When</th>
              <th className="px-3 py-2">Who</th>
              <th className="px-3 py-2">Action</th>
              <th className="px-3 py-2">Target</th>
              <th className="px-3 py-2 font-mono">Hash</th>
            </tr>
          </thead>
          <tbody>
            {loading && !data ? (
              <tr>
                <td colSpan={5} className="px-3 py-6 text-center opacity-60">
                  <Loader2 size={14} className="inline animate-spin" /> Loading…
                </td>
              </tr>
            ) : data && data.rows.length === 0 ? (
              <tr>
                <td
                  colSpan={5}
                  className="px-3 py-6 text-center italic opacity-60"
                >
                  No audit rows match the current filter.
                </td>
              </tr>
            ) : (
              data?.rows.map((r) => (
                <tr
                  key={r.id}
                  className="border-t border-din-blue/15 dark:border-din-cream/10"
                >
                  <td className="px-3 py-2 font-mono text-xs">
                    {new Date(r.created_at).toLocaleString()}
                  </td>
                  <td className="px-3 py-2">
                    <span className="font-mono text-xs opacity-70">
                      {r.user_id}
                    </span>
                    {r.user_email ? (
                      <span className="ml-2">{r.user_email}</span>
                    ) : null}
                  </td>
                  <td className="px-3 py-2 font-bold">{r.action}</td>
                  <td className="px-3 py-2 text-xs">
                    {r.target_type ?? ""}
                    {r.target_id !== null ? `:${r.target_id}` : ""}
                  </td>
                  <td className="px-3 py-2 font-mono text-[11px] opacity-60">
                    {r.payload_hash ? r.payload_hash.slice(0, 10) : ""}
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>

      {data ? (
        <div className="mt-4 flex items-center justify-between text-xs">
          <span className="opacity-70">
            {data.total.toLocaleString()} total · page {data.page} of{" "}
            {totalPages}
          </span>
          <div className="flex gap-2">
            <PagerButton
              disabled={page <= 1 || loading}
              onClick={() => setPage((p) => Math.max(1, p - 1))}
              label="‹ Prev"
            />
            <PagerButton
              disabled={page >= totalPages || loading}
              onClick={() => setPage((p) => p + 1)}
              label="Next ›"
            />
          </div>
        </div>
      ) : null}
    </Shell>
  );
}

function Shell({ children }: { children: React.ReactNode }) {
  return (
    <div className="flex min-h-screen flex-col bg-white text-din-navy dark:bg-din-navy dark:text-din-cream">
      <header className="flex items-center justify-between border-b border-din-blue/20 p-3 dark:border-din-cream/15">
        <div className="flex items-center gap-3 px-2">
          <DinLogo width={100} />
          <span className="text-xs uppercase tracking-wide opacity-60">
            Admin
          </span>
        </div>
        <ColorModeToggle />
      </header>
      <main className="mx-auto w-full max-w-5xl flex-1 px-6 py-8">
        {children}
      </main>
    </div>
  );
}

function CenteredMessage({ text }: { text: string }) {
  return (
    <div className="flex min-h-screen items-center justify-center bg-white text-din-navy dark:bg-din-navy dark:text-din-cream">
      <p className="text-sm italic opacity-70">{text}</p>
    </div>
  );
}

function PagerButton({
  label,
  onClick,
  disabled,
}: {
  label: string;
  onClick: () => void;
  disabled: boolean;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      disabled={disabled}
      className="rounded border border-din-blue/40 px-3 py-1.5 font-bold uppercase tracking-wide text-din-blue disabled:cursor-not-allowed disabled:opacity-40 hover:enabled:bg-din-blue/5 dark:border-din-cream/30 dark:text-din-cream/90 dark:hover:enabled:bg-din-cream/10"
    >
      {label}
    </button>
  );
}
