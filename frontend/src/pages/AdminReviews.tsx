import { Loader2 } from "lucide-react";
import { useCallback, useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import {
  ApiError,
  type CurrentUser,
  type ReviewKind,
  type ReviewListQuery,
  type ReviewListResponse,
  type ReviewRow,
  type ReviewStatus,
  reviews,
  users,
} from "../api/client";
import { ColorModeToggle } from "../components/ColorModeToggle";
import { DinLogo } from "../components/DinLogo";

/**
 * Owner-facing review queue.
 *
 * Lists change requests filed against contacts the current user owns.
 * Status filter defaults to "pending"; flip to "all" or "approved" /
 * "disapproved" via the tab row. Approve/disapprove are inline — no
 * confirm modal, since each row already shows the kind + payload and
 * the action is reversible only via a follow-up change request.
 */

const PAGE_SIZE = 50;

type Tab = "pending" | "approved" | "disapproved" | "all";

export default function AdminReviews() {
  const navigate = useNavigate();
  const [me, setMe] = useState<CurrentUser | null>(null);
  const [meLoading, setMeLoading] = useState(true);

  const [tab, setTab] = useState<Tab>("pending");
  const [kindFilter, setKindFilter] = useState<ReviewKind | "">("");
  const [page, setPage] = useState(1);

  const [data, setData] = useState<ReviewListResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [pendingResolveId, setPendingResolveId] = useState<number | null>(null);

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

  const query: ReviewListQuery = useMemo(
    () => ({
      status: tab === "all" ? "all" : (tab as ReviewStatus),
      kind: kindFilter || undefined,
      page,
      page_size: PAGE_SIZE,
    }),
    [tab, kindFilter, page],
  );

  const fetchRows = useCallback(() => {
    if (meLoading || !me) return () => {};
    let cancelled = false;
    setLoading(true);
    setError(null);
    reviews
      .list(query)
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

  useEffect(() => fetchRows(), [fetchRows]);

  const handleResolve = async (
    row: ReviewRow,
    decision: "approve" | "disapprove",
  ) => {
    setPendingResolveId(row.id);
    setError(null);
    try {
      await reviews.resolve(row.id, decision);
      fetchRows();
    } catch (e: unknown) {
      const msg =
        e instanceof ApiError ? `${e.status} ${e.message}` : String(e);
      setError(`Resolve failed: ${msg}`);
    } finally {
      setPendingResolveId(null);
    }
  };

  if (meLoading) {
    return <CenteredMessage text="Loading…" />;
  }
  if (!me) {
    return <CenteredMessage text="Not signed in." />;
  }

  const totalPages = data ? Math.max(1, Math.ceil(data.total / PAGE_SIZE)) : 1;

  return (
    <Shell>
      <div className="mb-4">
        <h1>Review Queue</h1>
        <p className="mt-1 text-sm italic opacity-70">
          Change requests filed against your contacts. Approving applies the
          change; disapproving leaves the contact untouched.
        </p>
      </div>

      <TabRow
        active={tab}
        onChange={(t) => {
          setTab(t);
          setPage(1);
        }}
      />

      <div className="mb-4 flex flex-wrap items-end gap-3 rounded border border-din-blue/20 bg-din-cream-soft/40 p-3 text-sm dark:border-din-cream/15 dark:bg-din-navy-soft/40">
        <label className="flex flex-col gap-1">
          <span className="text-[11px] font-bold uppercase tracking-wide opacity-70">
            Kind
          </span>
          <select
            value={kindFilter}
            onChange={(e) => {
              setKindFilter(e.target.value as ReviewKind | "");
              setPage(1);
            }}
            className="h-8 w-48 rounded border border-din-blue/30 bg-white px-2 text-sm focus:border-din-blue focus:outline-none focus:ring-1 focus:ring-din-gold dark:border-din-cream/30 dark:bg-din-navy-soft"
          >
            <option value="">All kinds</option>
            <option value="off_fly_list">Off fly list</option>
            <option value="patina_override">Patina override</option>
          </select>
        </label>
        {kindFilter && (
          <button
            type="button"
            onClick={() => {
              setKindFilter("");
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
          {error}
        </div>
      ) : null}

      <div className="overflow-x-auto rounded border border-din-blue/20 dark:border-din-cream/15">
        <table className="w-full min-w-[760px] text-left text-sm">
          <thead className="bg-din-cream-soft text-[11px] font-bold uppercase tracking-wide text-din-blue dark:bg-din-navy-soft dark:text-din-cream/80">
            <tr>
              <th className="px-3 py-2">When</th>
              <th className="px-3 py-2">Requester</th>
              <th className="px-3 py-2">Contact</th>
              <th className="px-3 py-2">Kind</th>
              <th className="px-3 py-2">Reason</th>
              <th className="px-3 py-2">Status</th>
              <th className="px-3 py-2 text-right">Action</th>
            </tr>
          </thead>
          <tbody>
            {loading && !data ? (
              <tr>
                <td colSpan={7} className="px-3 py-6 text-center opacity-60">
                  <Loader2 size={14} className="inline animate-spin" /> Loading…
                </td>
              </tr>
            ) : data && data.rows.length === 0 ? (
              <tr>
                <td
                  colSpan={7}
                  className="px-3 py-6 text-center italic opacity-60"
                >
                  {tab === "pending"
                    ? "No pending requests against your contacts."
                    : "No matching requests."}
                </td>
              </tr>
            ) : (
              data?.rows.map((r) => (
                <tr
                  key={r.id}
                  className="border-t border-din-blue/15 dark:border-din-cream/10"
                >
                  <td className="px-3 py-2 font-mono text-xs">
                    {ageString(r.created_at)}
                  </td>
                  <td className="px-3 py-2">
                    {r.requester_email ?? `#${r.requester_id}`}
                  </td>
                  <td className="px-3 py-2 font-bold">{r.contact_name}</td>
                  <td className="px-3 py-2">
                    <KindBadge kind={r.kind} />
                    {r.kind === "patina_override" && r.payload ? (
                      <details className="mt-1">
                        <summary className="cursor-pointer text-[11px] opacity-70">
                          payload
                        </summary>
                        <pre className="mt-1 max-w-md overflow-x-auto rounded bg-din-cream-soft/60 p-2 text-[11px] dark:bg-din-navy-soft/60">
                          {JSON.stringify(r.payload, null, 2)}
                        </pre>
                      </details>
                    ) : null}
                  </td>
                  <td className="px-3 py-2 text-xs opacity-80">
                    {r.reason ?? <span className="italic opacity-60">—</span>}
                  </td>
                  <td className="px-3 py-2">
                    <StatusPill status={r.status} />
                  </td>
                  <td className="px-3 py-2 text-right">
                    {r.status === "pending" ? (
                      <div className="flex justify-end gap-1.5">
                        <ResolveButton
                          variant="approve"
                          disabled={pendingResolveId === r.id}
                          onClick={() => handleResolve(r, "approve")}
                          loading={pendingResolveId === r.id}
                        />
                        <ResolveButton
                          variant="disapprove"
                          disabled={pendingResolveId === r.id}
                          onClick={() => handleResolve(r, "disapprove")}
                          loading={pendingResolveId === r.id}
                        />
                      </div>
                    ) : (
                      <span className="text-[11px] italic opacity-60">
                        resolved
                      </span>
                    )}
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

function ageString(iso: string): string {
  const ms = Date.now() - new Date(iso).getTime();
  const mins = Math.floor(ms / 60000);
  if (mins < 1) return "just now";
  if (mins < 60) return `${mins}m ago`;
  const hours = Math.floor(mins / 60);
  if (hours < 24) return `${hours}h ago`;
  const days = Math.floor(hours / 24);
  return `${days}d ago`;
}

function TabRow({
  active,
  onChange,
}: {
  active: Tab;
  onChange: (t: Tab) => void;
}) {
  const tabs: { id: Tab; label: string }[] = [
    { id: "pending", label: "Pending" },
    { id: "approved", label: "Approved" },
    { id: "disapproved", label: "Disapproved" },
    { id: "all", label: "All" },
  ];
  return (
    <div className="mb-4 flex gap-1 border-b border-din-blue/20 dark:border-din-cream/15">
      {tabs.map((t) => (
        <button
          key={t.id}
          type="button"
          onClick={() => onChange(t.id)}
          className={`px-3 py-2 text-xs font-bold uppercase tracking-wide transition ${
            active === t.id
              ? "border-b-2 border-din-gold text-din-blue dark:text-din-cream"
              : "text-din-blue/60 hover:text-din-blue dark:text-din-cream/60 dark:hover:text-din-cream"
          }`}
        >
          {t.label}
        </button>
      ))}
    </div>
  );
}

function KindBadge({ kind }: { kind: ReviewKind }) {
  const label = kind === "off_fly_list" ? "off fly list" : "patina override";
  return (
    <span className="inline-block rounded bg-din-blue/10 px-2 py-0.5 text-[11px] font-bold uppercase tracking-wide text-din-blue dark:bg-din-cream/15 dark:text-din-cream">
      {label}
    </span>
  );
}

function StatusPill({ status }: { status: ReviewStatus }) {
  const tone =
    status === "pending"
      ? "bg-din-gold/20 text-din-blue dark:bg-din-gold/15 dark:text-din-cream"
      : status === "approved"
        ? "bg-emerald-100 text-emerald-800 dark:bg-emerald-900/30 dark:text-emerald-200"
        : "bg-din-red/15 text-din-red dark:bg-din-red/20 dark:text-din-red-soft";
  return (
    <span
      className={`inline-block rounded px-2 py-0.5 text-[11px] font-bold uppercase tracking-wide ${tone}`}
    >
      {status}
    </span>
  );
}

function ResolveButton({
  variant,
  onClick,
  disabled,
  loading,
}: {
  variant: "approve" | "disapprove";
  onClick: () => void;
  disabled: boolean;
  loading: boolean;
}) {
  const label = variant === "approve" ? "Approve" : "Disapprove";
  const tone =
    variant === "approve"
      ? "border-emerald-600/50 text-emerald-800 hover:enabled:bg-emerald-50 dark:border-emerald-400/40 dark:text-emerald-200 dark:hover:enabled:bg-emerald-400/10"
      : "border-din-red/50 text-din-red hover:enabled:bg-din-red/5 dark:border-din-red-soft/50 dark:text-din-red-soft";
  return (
    <button
      type="button"
      onClick={onClick}
      disabled={disabled}
      className={`inline-flex items-center gap-1 rounded border px-2.5 py-1 text-[11px] font-bold uppercase tracking-wide disabled:cursor-not-allowed disabled:opacity-40 ${tone}`}
    >
      {loading ? <Loader2 size={12} className="animate-spin" /> : null}
      {label}
    </button>
  );
}

function Shell({ children }: { children: React.ReactNode }) {
  return (
    <div className="flex min-h-screen flex-col bg-white text-din-navy dark:bg-din-navy dark:text-din-cream">
      <header className="flex items-center justify-between border-b border-din-blue/20 p-3 dark:border-din-cream/15">
        <div className="flex items-center gap-3 px-2">
          <DinLogo width={100} />
          <span className="text-xs uppercase tracking-wide opacity-60">
            Review queue
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
