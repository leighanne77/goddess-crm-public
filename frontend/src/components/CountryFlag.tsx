/**
 * Tiny circular country flag — Phase 2 Slice 6.7.
 *
 * Renders one of the SVGs vendored under
 * `frontend/src/assets/country-flags/<code>.svg` (sourced from the
 * HatScripts/circle-flags repo — already circular, MIT-licensed).
 *
 * Default size is 14px so it sits inline next to `company_name` on a
 * contact card without dominating. Returns null if `code` doesn't
 * resolve to a known flag in the catalog — keeps the component safe
 * to drop in anywhere even if `countryToFlag()` returns null for an
 * uncatalogued country.
 *
 * Mirror of BrandIcon — same Vite `import.meta.glob` pattern, same
 * runtime guard against missing files, same typed-name contract via
 * the auto-generated `CountryCode` union.
 */

import type { CountryCode } from "./countryCodes";
export { COUNTRY_CODES, type CountryCode } from "./countryCodes";

const flagModules = import.meta.glob<string>("../assets/country-flags/*.svg", {
  eager: true,
  query: "?url",
  import: "default",
});

function pathToCode(path: string): string {
  const match = path.match(/country-flags\/(.+)\.svg$/);
  return match ? match[1] : "";
}

const FLAG_MAP: Record<string, string> = Object.fromEntries(
  Object.entries(flagModules)
    .map(([path, url]) => [pathToCode(path), url])
    .filter(([code]) => Boolean(code)),
);

interface CountryFlagProps {
  /** ISO 3166-1 alpha-2 code (lowercase), or the special `european_union`
   *  slug. Use `countryToFlag(canonicalName)` to get this. */
  code: CountryCode | null | undefined;
  size?: number;
  /** Optional full country name for the tooltip / a11y label. */
  countryName?: string;
  className?: string;
}

export function CountryFlag({
  code,
  size = 14,
  countryName,
  className = "",
}: CountryFlagProps) {
  if (!code) return null;
  const src = FLAG_MAP[code];
  if (!src) return null;
  return (
    <img
      src={src}
      alt={countryName ? `${countryName} flag` : `${code} flag`}
      title={countryName ?? code.toUpperCase()}
      width={size}
      height={size}
      className={`inline-block shrink-0 rounded-full ring-1 ring-din-navy/15 select-none ${className}`}
      draggable={false}
    />
  );
}
