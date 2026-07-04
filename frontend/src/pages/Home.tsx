import { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { auth, type CurrentUser, users } from "../api/client";
import { ChatInterface } from "../components/ChatInterface";
import { ColorModeToggle } from "../components/ColorModeToggle";
import { DinLogo } from "../components/DinLogo";

/**
 * Authenticated home — chat interface lives here.
 *
 * Any failure to fetch /users/me (401, 404, network, parse error)
 * bounces to /login. Treating non-401 as "maybe authed" once let a
 * backend routing bug leak the chat UI — fail closed instead.
 */
export default function Home() {
  const navigate = useNavigate();
  const [me, setMe] = useState<CurrentUser | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const u = await users.me();
        if (!cancelled) {
          setMe(u);
          setLoading(false);
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

  const handleLogout = async () => {
    try {
      await auth.logout();
    } finally {
      navigate("/login", { replace: true });
    }
  };

  if (loading) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-white dark:bg-din-navy">
        <p className="text-sm italic opacity-70">Loading…</p>
      </div>
    );
  }

  return (
    <div className="flex min-h-screen flex-col bg-white dark:bg-din-navy">
      <header className="flex items-center justify-between p-3">
        <div className="flex items-center gap-3 px-2">
          <DinLogo width={100} />
        </div>
        <div className="flex items-center gap-2">
          {me?.role === "admin" ? (
            <Link
              to="/admin/audit"
              className="rounded border border-din-blue/30 px-3 py-2 text-xs font-bold uppercase tracking-wide text-din-blue hover:bg-din-cream focus:outline-none focus:ring-2 focus:ring-din-gold dark:hover:bg-din-navy-soft"
            >
              Audit
            </Link>
          ) : null}
          <ColorModeToggle />
          <button
            type="button"
            onClick={handleLogout}
            className="rounded border border-din-blue/30 px-3 py-2 text-xs font-bold uppercase tracking-wide text-din-blue hover:bg-din-cream focus:outline-none focus:ring-2 focus:ring-din-gold dark:hover:bg-din-navy-soft"
          >
            Sign out
          </button>
        </div>
      </header>

      <main className="flex min-h-0 flex-1 flex-col items-center px-4 pb-4">
        <div className="flex min-h-0 w-full max-w-2xl flex-1 flex-col">
          <ChatInterface />
        </div>
      </main>
    </div>
  );
}
