import type { ContactCardData } from "../api/client";
import {
  CardPatina,
  PATINA_SLOTS,
  type Patina,
} from "../components/CardPatina";
import { ColorModeToggle } from "../components/ColorModeToggle";
import { ContactCard } from "../components/ContactCard";
import { COUNTRY_CODES, CountryFlag } from "../components/CountryFlag";
import { DinLogo } from "../components/DinLogo";

/**
 * Public brand reference for the DIN contact card. No auth — anyone with
 * the URL can inspect every card variant. Sample data is fictional and
 * uses only sample fields the public schema documents.
 *
 * Update this page when the card visual changes; static screenshots in
 * Docs/brand_assets/ are exported FROM this page so they stay in sync.
 *
 * The headshot in the "With headshot" example uses an inline neutral
 * placeholder (DIN navy circle + initials). The production card
 * intentionally renders nothing when image_url is null — see the "No
 * headshot" sample below.
 */

const HEADSHOT_DATA_URL =
  "data:image/svg+xml;utf8," +
  encodeURIComponent(
    `<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 56 56'>
      <rect width='56' height='56' fill='#4A6B8A'/>
      <text x='28' y='35' font-family='Arial, sans-serif' font-size='20'
            font-weight='bold' fill='#F5EEE0' text-anchor='middle'>EX</text>
    </svg>`,
  );

function makeContact(overrides: Partial<ContactCardData>): ContactCardData {
  return {
    id: 1,
    name: "Example Contact",
    company_name: "Example Company",
    title: "Title Here",
    email: null,
    cell_phone: null,
    office_phone: null,
    primary_fund: "General",
    contact_type: "Other",
    sectors: [],
    is_private: false,
    gender: "Unknown",
    country: null,
    lp_subtype: null,
    fly_status: "Maybe Must Fly",
    image_url: null,
    ex_government: "Don't Know",
    patina_overrides: null,
    ...overrides,
  };
}

const FLY_STATUS_SAMPLES: ContactCardData[] = [
  makeContact({
    id: 101,
    name: "Marcus Sterling",
    title: "Managing Partner",
    company_name: "Ironclad Capital Partners",
    primary_fund: "Maritime",
    contact_type: "LP",
    sectors: ["Defense", "Maritime"],
    fly_status: "Must Fly",
  }),
  makeContact({
    id: 102,
    name: "Diana Cho",
    title: "Principal",
    company_name: "Catalur Capital",
    primary_fund: "Critical Minerals",
    contact_type: "LP",
    sectors: ["Critical Minerals", "Lithium"],
    fly_status: "Fly List",
  }),
  makeContact({
    id: 103,
    name: "Dr. Jonathan Minerals",
    title: "Senior Geologist",
    company_name: "USGS Critical Minerals Group",
    primary_fund: "Critical Minerals",
    contact_type: "Advisor",
    sectors: ["Critical Minerals"],
    fly_status: "Maybe Must Fly",
  }),
  makeContact({
    id: 104,
    name: "Removed Example",
    title: "Former Contact",
    company_name: "Old Affiliation",
    primary_fund: "General",
    contact_type: "Other",
    sectors: [],
    fly_status: "Off Fly List",
  }),
];

const FUND_SAMPLES: ContactCardData[] = [
  makeContact({
    id: 201,
    name: "Critical Minerals — A",
    title: "Sample Title",
    company_name: "Sample Co",
    primary_fund: "Critical Minerals",
    contact_type: "Portfolio",
    fly_status: "Fly List",
    sectors: ["Mining"],
  }),
  makeContact({
    id: 202,
    name: "Critical Minerals — B",
    title: "Sample Title",
    company_name: "Sample Co",
    primary_fund: "Critical Minerals",
    contact_type: "Portfolio",
    fly_status: "Fly List",
    sectors: ["Rare Earth"],
  }),
  makeContact({
    id: 203,
    name: "Maritime",
    title: "Sample Title",
    company_name: "Sample Co",
    primary_fund: "Maritime",
    contact_type: "Portfolio",
    fly_status: "Must Fly",
    sectors: ["Shipbuilding"],
  }),
  makeContact({
    id: 204,
    name: "Energy",
    title: "Sample Title",
    company_name: "Sample Co",
    primary_fund: "Energy",
    contact_type: "Portfolio",
    fly_status: "Fly List",
    sectors: ["Data Centers"],
  }),
  makeContact({
    id: 205,
    name: "General",
    title: "Sample Title",
    company_name: "Sample Co",
    primary_fund: "General",
    contact_type: "Intermediary",
    fly_status: "Maybe Must Fly",
    sectors: ["Investment Banking"],
  }),
];

const HEADSHOT_SAMPLES: [ContactCardData, ContactCardData] = [
  makeContact({
    id: 301,
    name: "With Headshot",
    title: "Investment Director",
    company_name: "Example Holdings",
    primary_fund: "Energy",
    contact_type: "LP",
    fly_status: "Must Fly",
    sectors: ["Capital"],
    image_url: HEADSHOT_DATA_URL,
  }),
  makeContact({
    id: 302,
    name: "Without Headshot",
    title: "Investment Director",
    company_name: "Example Holdings",
    primary_fund: "Energy",
    contact_type: "LP",
    fly_status: "Must Fly",
    sectors: ["Capital"],
  }),
];

const EX_GOV_SAMPLE = makeContact({
  id: 601,
  name: "Admiral William Barrett (Ret.)",
  title: "CEO",
  company_name: "Mare Island Naval Shipyard LLC",
  primary_fund: "Maritime",
  contact_type: "Portfolio",
  fly_status: "Must Fly",
  sectors: ["Shipbuilding", "Defense"],
  ex_government: "Yes",
});

const PRIVACY_SAMPLE = makeContact({
  id: 401,
  name: "Private Contact",
  title: "Confidential",
  company_name: "Confidential Holdings",
  primary_fund: "Critical Minerals",
  contact_type: "LP",
  fly_status: "Must Fly",
  sectors: ["Strategic"],
  is_private: true,
});

const ANATOMY_SAMPLE = makeContact({
  id: 501,
  name: "Anatomy Example",
  title: "Sample Title",
  company_name: "Sample Holdings",
  primary_fund: "Maritime",
  contact_type: "LP",
  fly_status: "Must Fly",
  sectors: ["Defense", "Shipbuilding"],
});

export default function BrandCardReference() {
  return (
    <div className="min-h-screen bg-white text-din-navy dark:bg-din-navy dark:text-din-cream">
      <header className="flex items-center justify-between border-b border-din-blue/20 p-3 dark:border-din-cream/15">
        <div className="flex items-center gap-3 px-2">
          <DinLogo width={100} />
          <span className="text-xs uppercase tracking-wide opacity-60">
            Brand Reference
          </span>
        </div>
        <ColorModeToggle />
      </header>

      <main className="mx-auto max-w-5xl space-y-12 px-6 py-10">
        <section>
          <h1>Contact Card</h1>
          <p className="mt-2 italic text-din-blue">
            DIN rolodex card — visual reference and anatomy
          </p>
          <p className="mx-auto mt-4 max-w-2xl text-sm leading-relaxed">
            The contact card is the primary surface for any person in the DIN
            CRM. Inspired by 1940s rolodex cards in the firm&apos;s brand
            colors. This page shows every variant so screenshots in the brand
            annex stay accurate — it is the single source of truth for the card
            visual.
          </p>
        </section>

        <Section title="Anatomy">
          <p className="mb-4 max-w-2xl text-sm">
            One card, with the structural elements numbered.
          </p>
          <div className="grid grid-cols-1 gap-6 md:grid-cols-[minmax(0,420px)_1fr]">
            <div>
              <ContactCard contact={ANATOMY_SAMPLE} />
            </div>
            <ol className="space-y-2 text-sm">
              <Anatomy
                n={1}
                label="Fund tab stripe"
                detail="Top edge, fund-colored. Maritime = blue, Critical Minerals = red, Energy = gold, General = navy/cream."
              />
              <Anatomy
                n={2}
                label="Fly-status badge"
                detail="Top-right, 18px airplane. Solid = Must Fly, outline = Fly List, dotted = Maybe Must Fly. Unknown shows no plane; Off Fly List shows no plane plus ripped channels."
              />
              <Anatomy
                n={3}
                label="Headshot (optional)"
                detail="56px square, left of identity. Renders only when image_url is set. No stand-in when absent — identity block fills the width."
              />
              <Anatomy
                n={4}
                label="Name"
                detail="Oswald display font, uppercase, din-navy / din-cream. Truncates if too long."
              />
              <Anatomy
                n={5}
                label="Gold rule"
                detail="2px × 12 width, din-gold / din-gold-soft. Brand consistency with H1 underline pattern."
              />
              <Anatomy
                n={6}
                label="Title and company"
                detail="Title in body font; company_name italic in din-blue."
              />
              <Anatomy
                n={7}
                label="Fund pictogram in pill"
                detail="12px brand icon inline with the fund-name pill. Critical Minerals rotates rare-earth and pickaxes by contact ID."
              />
              <Anatomy
                n={8}
                label="Type / fund / sector pills"
                detail="10px uppercase. Wraps on narrow viewports."
              />
              <Anatomy
                n={9}
                label="Spindle holes"
                detail="Two 8px circles bottom-center. The 1940s rolodex card-file detail."
              />
              <Anatomy
                n={10}
                label="Paper-grain texture"
                detail="Inline SVG fractal noise at 3% opacity. Per Brand Guide §7.3."
              />
            </ol>
          </div>
        </Section>

        <Section title="Fly status — all four variants">
          <p className="mb-4 max-w-2xl text-sm">
            Same card, different fly_status. Order in real search results: Must
            Fly first, then Fly List, then Not Sure Yet, then Off Fly List
            (still visible, just last).
          </p>
          <div className="grid gap-4 sm:grid-cols-2">
            {FLY_STATUS_SAMPLES.map((c) => (
              <ContactCard key={c.id} contact={c} />
            ))}
          </div>
        </Section>

        <Section title="Headshot present vs. absent">
          <p className="mb-4 max-w-2xl text-sm">
            Headshot is strictly optional. When absent the identity block fills
            the card — there is no placeholder silhouette.
          </p>
          <div className="grid gap-4 sm:grid-cols-2">
            {HEADSHOT_SAMPLES.map((c) => (
              <ContactCard key={c.id} contact={c} />
            ))}
          </div>
        </Section>

        <Section title="Funds and pictograms">
          <p className="mb-4 max-w-2xl text-sm">
            Each fund has its own top-stripe color and pictogram (inline in the
            fund pill). Critical Minerals rotates between rare-earth and
            pickaxes; the others have a single pictogram.
          </p>
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {FUND_SAMPLES.map((c) => (
              <ContactCard key={c.id} contact={c} />
            ))}
          </div>
        </Section>

        <Section title="Ex-government indicator">
          <p className="mb-4 max-w-2xl text-sm">
            The <code className="font-mono">ex_government</code> field stores
            Yes / No / Don&apos;t Know but is hidden on the card by default. It
            only appears as a small red Ex-Gov pill when the user&apos;s search
            explicitly filtered on it — e.g. &ldquo;show me all ex-government
            contacts.&rdquo; Below shows the pill rendered (left) vs. hidden
            (right) for the same contact.
          </p>
          <div className="grid gap-4 sm:grid-cols-2">
            <ContactCard contact={EX_GOV_SAMPLE} showExGov />
            <ContactCard contact={EX_GOV_SAMPLE} />
          </div>
        </Section>

        <Section title="Privacy indicator">
          <p className="mb-4 max-w-2xl text-sm">
            Private contacts get a small lock icon next to the name. Visibility
            is enforced server-side; the icon is the visual cue.
          </p>
          <div className="max-w-md">
            <ContactCard contact={PRIVACY_SAMPLE} />
          </div>
        </Section>

        <Section title="Country flags — full catalog">
          <p className="mb-4 max-w-2xl text-sm">
            Tiny circular country flags appear inline-left of the company_name
            on every card. Sourced from the HatScripts/circle-flags repo (MIT).
            Add new countries via <code>scripts/fetch_country_flags.py</code>.
          </p>
          <div className="flex flex-wrap gap-3">
            {COUNTRY_CODES.map((code) => (
              <div
                key={code}
                className="flex items-center gap-1.5 rounded border border-din-navy/10 bg-white/60 px-2 py-1 text-xs"
              >
                <CountryFlag code={code} size={18} />
                <span className="font-mono uppercase">{code}</span>
              </div>
            ))}
          </div>
        </Section>

        <Section title="Mobile width (375px)">
          <p className="mb-4 max-w-2xl text-sm">
            The card at the smallest target viewport. Pills wrap; name
            truncates; airplane stays out of the way.
          </p>
          <div className="w-[375px] max-w-full rounded border border-din-blue/15 bg-white/40 p-2 dark:border-din-cream/10 dark:bg-din-navy-soft/30">
            <ContactCard contact={ANATOMY_SAMPLE} />
          </div>
        </Section>

        <Section title="Patina overrides — user customization">
          <p className="mb-4 max-w-2xl text-sm">
            Users can override the auto-pick via voice. Three states:
            <code className="mx-1 font-mono">null</code> (default — auto picks
            one), <code className="mx-1 font-mono">[]</code> (no patina), or up
            to <strong>3</strong> explicit items. Owner-only; non-owners get{" "}
            <code className="font-mono">forbidden_owner_only</code>.
          </p>
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            <ContactCard
              contact={makeContact({
                id: 901,
                name: "Auto-pick (default)",
                title: "patina_overrides: null",
                primary_fund: "General",
                contact_type: "Other",
                fly_status: "Fly List",
                patina_overrides: null,
              })}
            />
            <ContactCard
              contact={makeContact({
                id: 902,
                name: "Cleared",
                title: "patina_overrides: []",
                primary_fund: "General",
                contact_type: "Other",
                fly_status: "Fly List",
                patina_overrides: [],
              })}
            />
            <ContactCard
              contact={makeContact({
                id: 903,
                name: "Smiley sticker",
                title: '"add smiley sticker on X"',
                primary_fund: "Energy",
                contact_type: "LP",
                fly_status: "Must Fly",
                patina_overrides: [{ kind: "sticker", shape: "smiley" }],
              })}
            />
            <ContactCard
              contact={makeContact({
                id: 904,
                name: "Typewritten Nashville",
                title: '"typewritten Nashville"',
                primary_fund: "Maritime",
                contact_type: "Portfolio",
                fly_status: "Fly List",
                patina_overrides: [
                  { kind: "typewritten", text: "Nashville", color: "darkRed" },
                ],
              })}
            />
            <ContactCard
              contact={makeContact({
                id: 905,
                name: "Two pencil notes",
                title: '"Ghostbusters" + "ha ha ha"',
                primary_fund: "Critical Minerals",
                contact_type: "Advisor",
                fly_status: "Maybe Must Fly",
                patina_overrides: [
                  { kind: "pencilNote", text: "Ghostbusters" },
                  { kind: "pencilNote", text: "ha ha ha" },
                ],
              })}
            />
            <ContactCard
              contact={makeContact({
                id: 906,
                name: "Three items max",
                title: "sticker + check + dogear",
                primary_fund: "Maritime",
                contact_type: "LP",
                fly_status: "Must Fly",
                patina_overrides: [
                  { kind: "sticker", shape: "star", color: "#E8A82A" },
                  { kind: "check" },
                  { kind: "dogear", corner: "bottom-right" },
                ],
              })}
            />
          </div>
        </Section>

        <Section title="Patina gallery — every variant">
          <p className="mb-4 max-w-2xl text-sm">
            Every patina mark Alex Rivera's deck can wear. Each is rendered on a
            standalone card-tinted tile so you can compare side-by-side. On real
            cards these are picked deterministically per contact ID and never
            appear two at a time.
          </p>
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {PATINA_SLOTS.filter((p): p is Patina => p !== null).map((p, i) => (
              <PatinaTile key={i} patina={p} />
            ))}
          </div>
        </Section>

        <Section title="Color tokens">
          <p className="mb-4 max-w-2xl text-sm">
            Every color used in the card. Sourced from
            <code className="mx-1 font-mono">tailwind.config.js</code>; do not
            hardcode hex values in the component.
          </p>
          <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 md:grid-cols-5">
            <Swatch name="din-red" hex="#C8202F" />
            <Swatch name="din-red-soft" hex="#D43545" />
            <Swatch name="din-gold" hex="#E8A82A" />
            <Swatch name="din-gold-soft" hex="#F0BB52" />
            <Swatch name="din-blue" hex="#4A6B8A" />
            <Swatch name="din-blue-dark" hex="#3A5670" />
            <Swatch name="din-navy" hex="#1A2332" />
            <Swatch name="din-navy-soft" hex="#2A3548" />
            <Swatch name="din-cream" hex="#F5EEE0" />
            <Swatch name="din-cream-soft" hex="#FAF6EC" />
          </div>
        </Section>

        <footer className="border-t border-din-blue/20 pt-6 text-xs opacity-60 dark:border-din-cream/15">
          Source of truth for screenshots in
          <code className="mx-1 font-mono">
            Docs/brand_assets/contact-card/
          </code>
          and the &quot;Contact Card&quot; section of
          <code className="mx-1 font-mono">Docs/Brand_Mobile_Annex.md</code>.
        </footer>
      </main>
    </div>
  );
}

function Section({
  title,
  children,
}: {
  title: string;
  children: React.ReactNode;
}) {
  return (
    <section>
      <h2 className="border-b border-din-blue/20 pb-2 dark:border-din-cream/15">
        {title}
      </h2>
      <div className="mt-4">{children}</div>
    </section>
  );
}

function Anatomy({
  n,
  label,
  detail,
}: {
  n: number;
  label: string;
  detail: string;
}) {
  return (
    <li className="flex gap-3">
      <span className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-din-blue text-[11px] font-bold text-white dark:bg-din-cream dark:text-din-navy">
        {n}
      </span>
      <div>
        <span className="font-bold">{label}</span> — {detail}
      </div>
    </li>
  );
}

function PatinaTile({ patina }: { patina: Patina }) {
  // Best-effort label so the tile is self-explanatory. Includes the
  // sub-variant so similar entries can be told apart at a glance.
  const label = (() => {
    switch (patina.kind) {
      case "smudge":
        return `smudge · ${patina.ink} · v${patina.variant}`;
      case "dogear":
        return `dog-ear · ${patina.corner} · ${patina.size}px`;
      case "pencilNote":
        return `pencil note · "${patina.text}"`;
      case "doodle":
        return `doodle · ${patina.shape}`;
      case "check":
        return `check mark · size ${patina.size}`;
      case "typewritten":
        return `typewritten · "${patina.text}"`;
      case "mailingLabel":
        return `mailing label · "${patina.text}"`;
      case "sticker":
        return `sticker · ${patina.shape}`;
    }
  })();

  return (
    <div>
      <div className="relative h-28 w-full overflow-hidden rounded-sm border border-din-blue/20 bg-din-cream-soft dark:border-din-cream/15 dark:bg-din-navy-soft">
        <CardPatina patina={patina} />
      </div>
      <div className="mt-1 truncate font-mono text-[10px] opacity-60">
        {label}
      </div>
    </div>
  );
}

function Swatch({ name, hex }: { name: string; hex: string }) {
  return (
    <div className="rounded border border-din-blue/20 p-2 text-xs dark:border-din-cream/15">
      <div
        className="mb-2 h-12 w-full rounded-sm border border-din-blue/10 dark:border-din-cream/10"
        style={{ backgroundColor: hex }}
      />
      <div className="font-mono">{name}</div>
      <div className="font-mono opacity-60">{hex}</div>
    </div>
  );
}
