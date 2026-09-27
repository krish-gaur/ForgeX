import type { Config } from "tailwindcss";

/**
 * ForgeX design tokens.
 *
 * The system is light-first: bright neutral surfaces, hairline borders, a single
 * restrained blue accent, and semantic colour reserved strictly for state
 * (severity, health, verification, execution status).
 *
 * The `void / abyss / panel / edge / grid` names are retained from the original
 * token set as *semantic aliases* so every screen resolves against the same
 * palette. Do not introduce new raw hex values in components — extend this map.
 */
const config: Config = {
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}", "./lib/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        /* ---- surfaces (light-first) ---- */
        void: "#F7F8FA", // application canvas
        abyss: "#FFFFFF", // chrome, top bar, sticky regions
        panel: "#FFFFFF", // primary surface (card, panel, table)
        panel2: "#F2F4F7", // muted surface, table header, hover
        grid: "#EDEFF3", // hairline divider
        edge: "#E5E7EB", // default border
        edge2: "#D0D5DD", // emphasised border / input hover

        /* ---- accent ---- */
        accent: "#2563EB", // primary action
        accentSoft: "#EFF4FF", // primary tint surface
        accentEdge: "#C7D7FE", // primary tint border

        /* ---- semantic state ---- */
        phosphor: "#16A34A", // success / verified / healthy
        phosphorDim: "#15803D", // success, emphasised
        phosphorSoft: "#ECFDF3",
        phosphorEdge: "#A9E5C0",

        cyanx: "#0284C7", // info / in-flight
        cyanSoft: "#F0F9FF",
        cyanEdge: "#BAE6FD",

        amber: "#D97706", // warning / needs review
        amberSoft: "#FFFAEB",
        amberEdge: "#FDE3A7",

        alarm: "#DC2626", // danger / failed / tampered
        alarmSoft: "#FEF3F2",
        alarmEdge: "#FBC7C3",

        violetx: "#475569", // tertiary / provenance (neutral slate, not purple)
        violetSoft: "#F1F5F9",
        violetEdge: "#CBD5E1",

        /* ---- type ---- */
        ink: "#111827", // primary text
        muted: "#667085", // secondary text
        faint: "#98A2B3", // tertiary text / metadata

        /* ---- code & log surfaces (light gray, never black) ---- */
        code: "#F8F9FB", // code / payload / console surface
        codeEdge: "#E5E7EB", // code surface border
        codeInk: "#1F2937", // code text
      },
      fontFamily: {
        sans: ["Inter", "ui-sans-serif", "system-ui", "-apple-system", "Segoe UI", "Roboto", "Helvetica Neue", "Arial", "sans-serif"],
        mono: ["ui-monospace", "SFMono-Regular", "Menlo", "Consolas", "Liberation Mono", "monospace"],
        display: ["Inter", "ui-sans-serif", "system-ui", "Segoe UI", "sans-serif"],
      },
      fontSize: {
        // Dense, precise type scale for information-dense workbenches.
        "2xs": ["10px", { lineHeight: "14px" }],
      },
      borderRadius: {
        DEFAULT: "6px",
        sm: "4px",
        md: "6px",
        lg: "8px",
      },
      boxShadow: {
        // Extremely subtle — borders carry the structure, shadows only lift.
        xs: "0 1px 2px 0 rgba(16,24,40,0.04)",
        panel: "0 1px 2px 0 rgba(16,24,40,0.05)",
        raised: "0 4px 12px -2px rgba(16,24,40,0.08), 0 2px 4px -2px rgba(16,24,40,0.04)",
        overlay: "0 16px 40px -8px rgba(16,24,40,0.16), 0 4px 8px -4px rgba(16,24,40,0.06)",
        focus: "0 0 0 3px rgba(37,99,235,0.10)",
      },
      maxWidth: {
        shell: "1600px",
      },
      spacing: {
        sidebar: "248px",
        topbar: "52px",
        statusbar: "26px",
      },
      transitionDuration: {
        DEFAULT: "150ms",
      },
      transitionTimingFunction: {
        swift: "cubic-bezier(0.2, 0, 0.2, 1)",
      },
      keyframes: {
        "fade-in": { from: { opacity: "0" }, to: { opacity: "1" } },
        "slide-down": {
          from: { opacity: "0", transform: "translateY(-4px)" },
          to: { opacity: "1", transform: "translateY(0)" },
        },
        "slide-left": {
          from: { transform: "translateX(100%)" },
          to: { transform: "translateX(0)" },
        },
        "pop-in": {
          from: { opacity: "0", transform: "scale(0.98)" },
          to: { opacity: "1", transform: "translate(0,0)" },
        },
        "pulse-dot": { "0%, 100%": { opacity: "1" }, "50%": { opacity: "0.35" } },
        shimmer: {
          "100%": { transform: "translateX(100%)" },
        },
      },
      animation: {
        "fade-in": "fade-in 150ms cubic-bezier(0.2,0,0.2,1)",
        "slide-down": "slide-down 150ms cubic-bezier(0.2,0,0.2,1)",
        "slide-left": "slide-left 180ms cubic-bezier(0.2,0,0.2,1)",
        "pop-in": "pop-in 150ms cubic-bezier(0.2,0,0.2,1)",
        // Replaces the old "pulseSlow" glow animation: a quiet opacity breath on
        // the status dot only. No colour cycling, no glow.
        "pulse-dot": "pulse-dot 2s ease-in-out infinite",
        "pulse-slow": "pulse-dot 2s ease-in-out infinite",
        shimmer: "shimmer 1.6s infinite",
      },
    },
  },
  plugins: [],
};

export default config;
