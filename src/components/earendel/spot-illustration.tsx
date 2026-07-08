"use client";

import * as React from "react";

/* ------------------------------------------------------------------ */
/* SpotIllustration — small inline SVG spot illustrations for          */
/* empty states. Hand-drawn feel using the Earendel palette.           */
/* ------------------------------------------------------------------ */

export type SpotVariant =
  | "connectors"
  | "recorder"
  | "actions"
  | "executions"
  | "monitoring"
  | "publishing"
  | "playground"
  | "empty";

const STROKE = "#A5A19B";
const ACCENT = "#7A8548";
const PRIMARY = "#6B5876";
const MUTED = "#42403D";

export function SpotIllustration({
  variant,
  size = 96,
  className,
}: {
  variant: SpotVariant;
  size?: number;
  className?: string;
}) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 96 96"
      fill="none"
      className={className}
      aria-hidden
    >
      <defs>
        <linearGradient id="er-spot-bg" x1="0" y1="0" x2="1" y2="1">
          <stop offset="0%" stopColor="#6B5876" stopOpacity="0.18" />
          <stop offset="100%" stopColor="#7A8548" stopOpacity="0.08" />
        </linearGradient>
        <linearGradient id="er-spot-accent" x1="0" y1="0" x2="1" y2="1">
          <stop offset="0%" stopColor={PRIMARY} stopOpacity="0.6" />
          <stop offset="100%" stopColor={ACCENT} stopOpacity="0.5" />
        </linearGradient>
      </defs>
      {render(variant)}
    </svg>
  );
}

function render(variant: SpotVariant): React.ReactNode {
  switch (variant) {
    case "connectors":
      return (
        <>
          <circle cx="48" cy="48" r="40" fill="url(#er-spot-bg)" stroke={MUTED} strokeWidth="1" strokeDasharray="3 3" />
          <rect x="30" y="34" width="36" height="28" rx="4" fill="#1F1A17" stroke={STROKE} strokeWidth="1.5" />
          <circle cx="40" cy="48" r="3" fill={ACCENT} />
          <circle cx="56" cy="48" r="3" fill={PRIMARY} />
          <path d="M43 48 L53 48" stroke={STROKE} strokeWidth="1.5" strokeLinecap="round" />
          <path d="M36 68 L60 68" stroke={STROKE} strokeWidth="1.5" strokeLinecap="round" opacity="0.5" />
        </>
      );
    case "recorder":
      return (
        <>
          <circle cx="48" cy="48" r="40" fill="url(#er-spot-bg)" stroke={MUTED} strokeWidth="1" strokeDasharray="3 3" />
          <circle cx="48" cy="48" r="14" fill="url(#er-spot-accent)" stroke={ACCENT} strokeWidth="1.5" />
          <circle cx="48" cy="48" r="5" fill="#1F1A17" />
          <path d="M48 28 L48 34 M48 62 L48 68 M28 48 L34 48 M62 48 L68 48" stroke={ACCENT} strokeWidth="1.5" strokeLinecap="round" />
        </>
      );
    case "actions":
      return (
        <>
          <circle cx="48" cy="48" r="40" fill="url(#er-spot-bg)" stroke={MUTED} strokeWidth="1" strokeDasharray="3 3" />
          <rect x="28" y="36" width="40" height="8" rx="2" fill={PRIMARY} opacity="0.4" />
          <rect x="28" y="48" width="40" height="8" rx="2" fill={ACCENT} opacity="0.5" />
          <rect x="28" y="60" width="24" height="8" rx="2" fill={STROKE} opacity="0.3" />
          <circle cx="62" cy="64" r="4" fill={ACCENT} />
        </>
      );
    case "executions":
      return (
        <>
          <circle cx="48" cy="48" r="40" fill="url(#er-spot-bg)" stroke={MUTED} strokeWidth="1" strokeDasharray="3 3" />
          <path d="M30 60 L30 44 M42 60 L42 36 M54 60 L54 48 M66 60 L66 32" stroke="url(#er-spot-accent)" strokeWidth="2" strokeLinecap="round" />
          <circle cx="30" cy="44" r="2.5" fill={ACCENT} />
          <circle cx="42" cy="36" r="2.5" fill={PRIMARY} />
          <circle cx="54" cy="48" r="2.5" fill={ACCENT} />
          <circle cx="66" cy="32" r="2.5" fill={PRIMARY} />
        </>
      );
    case "monitoring":
      return (
        <>
          <circle cx="48" cy="48" r="40" fill="url(#er-spot-bg)" stroke={MUTED} strokeWidth="1" strokeDasharray="3 3" />
          <path d="M28 56 Q36 40 44 48 T60 44 T72 36" stroke={ACCENT} strokeWidth="2" fill="none" strokeLinecap="round" />
          <circle cx="72" cy="36" r="3" fill={ACCENT} />
          <path d="M28 64 L72 64" stroke={MUTED} strokeWidth="1" opacity="0.4" />
          <path d="M44 28 L44 24 M44 24 L40 28 M44 24 L48 28" stroke={PRIMARY} strokeWidth="1.5" strokeLinecap="round" />
        </>
      );
    case "publishing":
      return (
        <>
          <circle cx="48" cy="48" r="40" fill="url(#er-spot-bg)" stroke={MUTED} strokeWidth="1" strokeDasharray="3 3" />
          <path d="M48 28 L62 42 L48 56 L34 42 Z" fill="url(#er-spot-accent)" stroke={PRIMARY} strokeWidth="1.5" />
          <path d="M48 56 L48 68" stroke={PRIMARY} strokeWidth="1.5" strokeLinecap="round" />
          <path d="M40 64 L56 64" stroke={PRIMARY} strokeWidth="1.5" strokeLinecap="round" />
        </>
      );
    case "playground":
      return (
        <>
          <circle cx="48" cy="48" r="40" fill="url(#er-spot-bg)" stroke={MUTED} strokeWidth="1" strokeDasharray="3 3" />
          <rect x="26" y="38" width="44" height="24" rx="4" fill="#1F1A17" stroke={STROKE} strokeWidth="1.5" />
          <path d="M32 50 L36 46 L32 50 L36 54" stroke={ACCENT} strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" fill="none" />
          <path d="M44 54 L48 46 L52 54" stroke={PRIMARY} strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" fill="none" />
          <circle cx="62" cy="50" r="2" fill={ACCENT} />
        </>
      );
    case "empty":
    default:
      return (
        <>
          <circle cx="48" cy="48" r="40" fill="url(#er-spot-bg)" stroke={MUTED} strokeWidth="1" strokeDasharray="3 3" />
          <rect x="36" y="40" width="24" height="18" rx="2" fill="none" stroke={STROKE} strokeWidth="1.5" strokeDasharray="2 2" />
          <path d="M42 49 L48 54 L56 44" stroke={ACCENT} strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" fill="none" opacity="0" />
        </>
      );
  }
}

export default SpotIllustration;
