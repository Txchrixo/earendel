"use client";

import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Icon, type ErIconName } from "../icon";
import type {
  FieldSchema,
  TypedAction,
  AdapterType,
} from "@/lib/earendel/types";

/* ------------------------------------------------------------------ */
/* Shared helpers                                                      */
/* ------------------------------------------------------------------ */

export const ADAPTER_META: Record<
  AdapterType,
  { icon: ErIconName; name: string; desc: string; reliability: string; speed: string }
> = {
  api: {
    icon: "server",
    name: "Official API",
    desc: "First-party REST call against the vendor's published API.",
    reliability: "99%",
    speed: "~120ms",
  },
  internal_route: {
    icon: "link",
    name: "Internal route",
    desc: "Discovered internal endpoint reached via session cookies.",
    reliability: "94%",
    speed: "~180ms",
  },
  browser: {
    icon: "browser",
    name: "Browser automation",
    desc: "Headless browser replays the recorded click-flow.",
    reliability: "80%",
    speed: "~900ms",
  },
  bu_browser: {
    icon: "cloud",
    name: "Browser Use cloud",
    desc: "Optional — stealth + CAPTCHA + proxies. Activates only when the local browser fails AND the action opts in.",
    reliability: "88%",
    speed: "~1500ms",
  },
  vision: {
    icon: "eye",
    name: "Vision (OmniParser)",
    desc: "Grounded visual parsing when DOM selectors drift.",
    reliability: "70%",
    speed: "~1400ms",
  },
  human: {
    icon: "person",
    name: "Human review",
    desc: "Escalated to a human operator for authorisation.",
    reliability: "100%",
    speed: "minutes",
  },
};

export const FALLBACK_ORDER: AdapterType[] = [
  "api",
  "internal_route",
  "browser",
  "bu_browser",
  "vision",
  "human",
];

export function tsType(f: FieldSchema): string {
  switch (f.type) {
    case "string":
      return "string";
    case "number":
      return "number";
    case "boolean":
      return "boolean";
    case "date":
      return "string /* ISO date */";
    case "url":
      return "string /* URL */";
    case "file":
      return "Blob";
    case "enum":
      return f.enum && f.enum.length
        ? f.enum.map((e) => `"${e}"`).join(" | ")
        : "string";
    default:
      return "string";
  }
}

export function tsSignature(action: TypedAction): string {
  const params = action.contract.inputs
    .map((i) => `${i.name}${i.required ? "" : "?"}: ${tsType(i)}`)
    .join(", ");
  const out = action.contract.outputs
    .map((o) => `  ${o.name}: ${tsType(o)};`)
    .join("\n");
  return `async function ${action.name}(${params}): Promise<{\n${out}\n}>`;
}

export function timeAgo(iso: string): string {
  const diff = Date.now() - new Date(iso).getTime();
  const m = Math.floor(diff / 60000);
  if (m < 1) return "just now";
  if (m < 60) return `${m}m ago`;
  const h = Math.floor(m / 60);
  if (h < 24) return `${h}h ago`;
  return `${Math.floor(h / 24)}d ago`;
}

/* ------------------------------------------------------------------ */
/* Small shared components                                             */
/* ------------------------------------------------------------------ */

export function FieldList({ title, fields }: { title: string; fields: FieldSchema[] }) {
  return (
    <Card className="gap-3 p-4">
      <div className="flex items-center gap-2">
        <Icon name={title === "Inputs" ? "arrowDown" : "arrowRight"} size={14} aria-hidden />
        <h4 className="er-h3">{title}</h4>
        <Badge variant="secondary" className="ml-auto">
          {fields.length}
        </Badge>
      </div>
      <ul className="divide-y divide-border">
        {fields.map((f) => (
          <li key={f.name} className="py-2.5">
            <div className="flex flex-wrap items-center gap-2">
              <code className="font-mono text-sm text-foreground">{f.name}</code>
              <Badge variant="outline" className="er-caption">
                {f.type}
              </Badge>
              {f.required && (
                <span className="er-caption text-destructive">*</span>
              )}
            </div>
            {f.description && (
              <p className="er-caption mt-1 text-muted-foreground">{f.description}</p>
            )}
            {f.enum && f.enum.length > 0 && (
              <p className="er-caption mt-1 font-mono text-muted-foreground">
                enum: {f.enum.join(" | ")}
              </p>
            )}
          </li>
        ))}
      </ul>
    </Card>
  );
}

export function Checklist({
  title,
  items,
  icon,
}: {
  title: string;
  items: string[];
  icon: ErIconName;
}) {
  return (
    <Card className="gap-2 p-4">
      <div className="flex items-center gap-2">
        <Icon name={icon} size={14} aria-hidden />
        <h4 className="text-sm font-medium">{title}</h4>
      </div>
      <ul className="space-y-1.5">
        {items.length === 0 && (
          <li className="er-caption text-muted-foreground">None declared.</li>
        )}
        {items.map((c, i) => (
          <li key={i} className="flex items-start gap-2 er-caption">
            <Icon
              name={icon === "shieldCheck" ? "check" : "tasklist"}
              size={12}
              className="mt-0.5 shrink-0 text-accent"
              aria-hidden
            />
            <span className="text-muted-foreground">{c}</span>
          </li>
        ))}
      </ul>
    </Card>
  );
}
