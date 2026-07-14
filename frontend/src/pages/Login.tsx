import { auth } from "../api/client";
import { ColorModeToggle } from "../components/ColorModeToggle";
import { DinLogo } from "../components/DinLogo";

/**
 * Login page — first thing every unauthenticated visitor sees.
 * Triggers OAuth via explicit user click (NOT useEffect — React 18
 * StrictMode would fire it twice, per Day 4 plan Pitfall 2).
 */
export default function Login() {
  return (
    <div className="flex min-h-screen flex-col bg-white dark:bg-din-navy">
      <header className="flex items-center justify-end p-3">
        <ColorModeToggle />
      </header>

      <main className="flex flex-1 flex-col items-center justify-center p-6">
        <div className="w-full max-w-lg text-center">
          <DinLogo width={260} className="mx-auto" />
          <div className="din-gold-rule mx-auto mt-3 max-w-xs" />

          <p className="mx-auto mt-4 max-w-md text-sm font-medium tracking-wide text-din-blue dark:text-din-cream">
            Connecting private capital to deep-tech and dual-use
            industrial builds.
          </p>

          <h1 className="mt-10">DIN Command Center</h1>
          <p className="mt-2 italic text-din-blue">People &amp; Contacts</p>

          <p className="mx-auto mt-8 max-w-md text-sm leading-relaxed">
            <span className="font-bold text-din-red dark:text-din-red-soft">
              Team Access Only:
            </span>{" "}
            Contacts, deal flow, and LP relationships — built for the speed of
            industrial mobilization.
          </p>

          <button
            type="button"
            onClick={() => auth.startLogin()}
            className="mt-10 inline-flex h-12 items-center justify-center gap-3 rounded bg-din-blue px-8 text-sm font-bold uppercase tracking-wide text-white hover:bg-din-blue-dark focus:outline-none focus:ring-2 focus:ring-din-gold dark:bg-din-cream dark:text-din-navy dark:hover:bg-din-cream/85"
          >
            <GoogleG />
            Sign in with Google
          </button>

          <p className="mt-4 text-xs italic opacity-60">
            Sign in with your @example.com Google account.
          </p>

          {import.meta.env.DEV && (
            <p className="mt-6">
              <button
                type="button"
                onClick={() => auth.devLogin()}
                className="text-xs underline opacity-60 hover:opacity-100"
              >
                Dev sign-in (local only)
              </button>
            </p>
          )}
        </div>
      </main>
    </div>
  );
}

/** Google "G" mark — official colors, kept as inline SVG. */
function GoogleG() {
  return (
    <svg
      width="18"
      height="18"
      viewBox="0 0 18 18"
      aria-hidden="true"
      className="shrink-0"
    >
      <path
        fill="#4285F4"
        d="M17.64 9.2c0-.64-.06-1.25-.17-1.84H9v3.48h4.84a4.14 4.14 0 0 1-1.79 2.71v2.26h2.9c1.7-1.57 2.69-3.88 2.69-6.61z"
      />
      <path
        fill="#34A853"
        d="M9 18c2.43 0 4.47-.81 5.96-2.18l-2.9-2.26c-.8.54-1.83.86-3.06.86-2.35 0-4.34-1.59-5.05-3.72H.96v2.33A8.997 8.997 0 0 0 9 18z"
      />
      <path
        fill="#FBBC05"
        d="M3.95 10.7A5.41 5.41 0 0 1 3.66 9c0-.59.1-1.16.29-1.7V4.97H.96A8.997 8.997 0 0 0 0 9c0 1.45.35 2.83.96 4.03l2.99-2.33z"
      />
      <path
        fill="#EA4335"
        d="M9 3.58c1.32 0 2.51.45 3.44 1.35l2.58-2.58C13.46.89 11.43 0 9 0A8.997 8.997 0 0 0 .96 4.97L3.95 7.3C4.66 5.17 6.65 3.58 9 3.58z"
      />
    </svg>
  );
}
