/**
 * Color mode management — per Brand_Mobile_Annex.md §6.
 * Default: mobile (≤768px) = dark, desktop = light.
 * User override persisted in localStorage["din-color-mode"].
 */
import { useEffect, useState } from "react";

export type ColorMode = "light" | "dark";

const STORAGE_KEY = "din-color-mode";
const MOBILE_BREAKPOINT_PX = 768;

function detectInitialMode(): ColorMode {
  // 1. Honor an explicit user override if it exists.
  const stored = window.localStorage.getItem(STORAGE_KEY);
  if (stored === "light" || stored === "dark") {
    return stored;
  }
  // 2. Fall back to viewport-based brand default.
  return window.innerWidth <= MOBILE_BREAKPOINT_PX ? "dark" : "light";
}

function applyDocumentClass(mode: ColorMode): void {
  const root = document.documentElement;
  if (mode === "dark") {
    root.classList.add("dark");
  } else {
    root.classList.remove("dark");
  }
}

export function useColorMode(): {
  mode: ColorMode;
  toggle: () => void;
  setMode: (m: ColorMode) => void;
} {
  const [mode, setModeState] = useState<ColorMode>(() => {
    const initial = detectInitialMode();
    applyDocumentClass(initial);
    return initial;
  });

  // Re-evaluate on window resize, but only if the user hasn't overridden.
  useEffect(() => {
    const stored = window.localStorage.getItem(STORAGE_KEY);
    if (stored === "light" || stored === "dark") return;

    const onResize = () => {
      const next: ColorMode =
        window.innerWidth <= MOBILE_BREAKPOINT_PX ? "dark" : "light";
      setModeState((current) => {
        if (current !== next) applyDocumentClass(next);
        return next;
      });
    };
    window.addEventListener("resize", onResize);
    return () => window.removeEventListener("resize", onResize);
  }, []);

  const setMode = (next: ColorMode) => {
    window.localStorage.setItem(STORAGE_KEY, next);
    applyDocumentClass(next);
    setModeState(next);
  };

  const toggle = () => setMode(mode === "dark" ? "light" : "dark");

  return { mode, toggle, setMode };
}
