import { useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { ApiError, users } from "../api/client";

/**
 * Landing page after the OAuth callback redirects here. The session
 * cookie should already be set by the backend. Fetch /users/me, then
 * route to /intro (first time) or /home (returning user).
 *
 * If /users/me returns 401, the cookie didn't make it — bounce back
 * to /login.
 */
export default function AuthSuccess() {
  const navigate = useNavigate();

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const me = await users.me();
        if (cancelled) return;
        navigate(me.intro_seen ? "/" : "/intro", { replace: true });
      } catch (e) {
        if (cancelled) return;
        if (e instanceof ApiError && e.status === 401) {
          navigate("/login", { replace: true });
        } else {
          navigate("/login?error=session", { replace: true });
        }
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [navigate]);

  return (
    <div className="flex min-h-screen items-center justify-center bg-white dark:bg-din-navy">
      <p className="text-sm italic opacity-70">Signing you in…</p>
    </div>
  );
}
