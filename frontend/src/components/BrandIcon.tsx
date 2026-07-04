/**
 * The DIN brand icon library — domain-specific pictograms covering the
 * three funds (Critical Minerals, Maritime, Energy) plus shared symbols
 * (anchor, ship, document, etc.). Distinct from Lucide UI icons (per
 * Brand_Mobile_Annex.md §12).
 *
 * Icons are loaded dynamically from `assets/brand-icons/din-*.svg` via
 * Vite's `import.meta.glob`, so adding a new icon = drop the SVG in
 * the folder. No code change required.
 *
 * The din-logo*.svg files are excluded from the icon map — they're used
 * standalone via the DinLogo component.
 */

import type { BrandIconName } from "./brandIconNames";
export { BRAND_ICON_NAMES, type BrandIconName } from "./brandIconNames";

const iconModules = import.meta.glob<string>(
  "../assets/brand-icons/din-*.svg",
  { eager: true, query: "?url", import: "default" },
);

function pathToName(path: string): string {
  const match = path.match(/din-(.+)\.svg$/);
  return match ? match[1] : "";
}

const ICON_MAP: Record<string, string> = Object.fromEntries(
  Object.entries(iconModules)
    .map(([path, url]) => [pathToName(path), url])
    .filter(([name]) => name && !name.startsWith("logo")),
);

interface BrandIconProps {
  name: BrandIconName;
  size?: number;
  className?: string;
  alt?: string;
}

export function BrandIcon({
  name,
  size = 48,
  className = "",
  alt,
}: BrandIconProps) {
  const src = ICON_MAP[name];
  if (!src) {
    return null;
  }
  return (
    <img
      src={src}
      alt={alt ?? `${name} icon`}
      width={size}
      height={size}
      className={`select-none ${className}`}
      draggable={false}
    />
  );
}
