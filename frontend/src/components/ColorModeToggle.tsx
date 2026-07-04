import { Moon, Sun } from "lucide-react";
import { useColorMode } from "../lib/colorMode";

/**
 * Sun/moon icon toggle for switching between light and dark modes.
 * Per Brand_Mobile_Annex.md §6.3 — 32×32 visual, 44×44 hit area.
 * Icons from Lucide (open-source, MIT, currentColor stroke).
 */
export function ColorModeToggle() {
  const { mode, toggle } = useColorMode();
  const isDark = mode === "dark";
  const label = isDark ? "Switch to light mode" : "Switch to dark mode";

  return (
    <button
      type="button"
      onClick={toggle}
      aria-label={label}
      title={label}
      className="inline-flex h-11 w-11 items-center justify-center rounded-full text-din-navy hover:bg-din-cream focus:outline-none focus:ring-2 focus:ring-din-gold dark:text-din-cream dark:hover:bg-din-navy-soft"
    >
      {isDark ? <Sun size={20} aria-hidden /> : <Moon size={20} aria-hidden />}
    </button>
  );
}
