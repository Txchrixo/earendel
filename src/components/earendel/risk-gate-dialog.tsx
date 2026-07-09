"use client";

import * as React from "react";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog";
import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";
import { Icon } from "./icon";
import { RiskBadge } from "./primitives";
import type { RiskLevel, PermissionScope } from "@/lib/earendel/types";

interface RiskGateDialogProps {
  /** Risk level of the action being run. */
  riskLevel: RiskLevel;
  /** Permission scope of the action. */
  permission: PermissionScope;
  /** Action name / signature for context. */
  actionLabel: string;
  /** The inputs that will be sent, rendered as a small summary. */
  inputs?: Record<string, unknown>;
  /** Children = the trigger button. We clone it to open the dialog. */
  children: React.ReactNode;
  /** Called when the user confirms. */
  onConfirm: () => void | Promise<void>;
}

/**
 * RiskGateDialog — gates execution of high/critical/destructive actions
 * behind an explicit confirmation. Low/medium read-only actions run directly.
 *
 * This implements the risk-based autonomy policy from the research:
 *   read-only      → auto-run
 *   read_write     → auto-run + log
 *   submit         → human confirmation
 *   destructive    → strict approval (typed confirmation)
 */
export function RiskGateDialog({
  riskLevel,
  permission,
  actionLabel,
  inputs,
  children,
  onConfirm,
}: RiskGateDialogProps) {
  const [open, setOpen] = React.useState(false);
  const [busy, setBusy] = React.useState(false);
  const [confirmText, setConfirmText] = React.useState("");

  // Gate only fires for high/critical risk OR submit/destructive permission.
  const needsGate =
    riskLevel === "high" ||
    riskLevel === "critical" ||
    permission === "submit" ||
    permission === "destructive";

  const isDestructive = permission === "destructive" || riskLevel === "critical";
  const expectedConfirm = isDestructive ? actionLabel.toUpperCase() : "";

  const trigger = React.Children.only(children) as React.ReactElement<{
    onClick?: (e: React.MouseEvent) => void;
  }>;

  const handleClick = (e: React.MouseEvent) => {
    e.preventDefault();
    if (needsGate) {
      setOpen(true);
    } else {
      // Low/medium read-only — run directly.
      void onConfirm();
    }
  };

  const handleConfirm = async () => {
    if (isDestructive && confirmText !== expectedConfirm) return;
    setBusy(true);
    try {
      await onConfirm();
      setOpen(false);
    } finally {
      setBusy(false);
      setConfirmText("");
    }
  };

  return (
    <>
      {React.cloneElement(trigger, { onClick: handleClick })}
      <AlertDialog open={open} onOpenChange={setOpen}>
        <AlertDialogContent className="border-border bg-card">
          <AlertDialogHeader>
            <AlertDialogTitle className="flex items-center gap-2 font-heading text-xl">
              <span
                className={cn(
                  "grid size-8 place-items-center rounded-md",
                  isDestructive
                    ? "bg-destructive/15 text-destructive"
                    : "bg-secondary text-muted-foreground",
                )}
              >
                <Icon name={isDestructive ? "alertFill" : "shield"} size={18} aria-hidden />
              </span>
              {isDestructive ? "Destructive action" : "High-risk action"}
            </AlertDialogTitle>
            <AlertDialogDescription asChild>
              <div className="space-y-3 text-muted-foreground">
                <p>
                  You are about to run <code className="font-mono text-foreground">{actionLabel}</code>.
                  This action is{" "}
                  <span className="text-foreground font-medium">{permission.replace("_", " ")}</span>{" "}
                  scoped and rated{" "}
                  <RiskBadge level={riskLevel} className="ml-1" />.
                </p>
                <div className="rounded-md border border-border bg-background/40 p-3">
                  <p className="er-caption uppercase tracking-wide mb-1.5">
                    Inputs
                  </p>
                  {inputs && Object.keys(inputs).length > 0 ? (
                    <pre className="er-scroll max-h-32 overflow-auto font-mono text-xs text-foreground">
                      {JSON.stringify(inputs, null, 2)}
                    </pre>
                  ) : (
                    <p className="er-caption text-muted-foreground">No inputs.</p>
                  )}
                </div>
                <p className="er-caption">
                  <Icon name="lightbulb" size={12} aria-hidden className="inline mr-1" />
                  Per Earendel&apos;s risk-gating policy,{" "}
                  {isDestructive ? "destructive" : "submit-level"} actions require
                  explicit human authorisation. The execution will be logged with a
                  full audit trail and flagged for review.
                </p>
                {isDestructive && (
                  <div className="rounded-md border border-destructive/40 bg-destructive/10 p-3">
                    <p className="er-caption text-foreground">
                      Type{" "}
                      <code className="font-mono font-bold">{expectedConfirm}</code>{" "}
                      to confirm this destructive action.
                    </p>
                    <input
                      type="text"
                      value={confirmText}
                      onChange={(e) => setConfirmText(e.target.value)}
                      className="mt-2 w-full rounded-md border border-border bg-background px-3 py-1.5 font-mono text-sm text-foreground outline-none focus:border-primary"
                      placeholder={expectedConfirm}
                      aria-label="Type the action name to confirm"
                    />
                  </div>
                )}
              </div>
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel
              disabled={busy}
              className="border-border"
              onClick={() => setConfirmText("")}
            >
              Cancel
            </AlertDialogCancel>
            <AlertDialogAction
              onClick={handleConfirm}
              disabled={busy || (isDestructive && confirmText !== expectedConfirm)}
              className={
                isDestructive
                  ? "bg-destructive text-white hover:bg-destructive/90"
                  : "bg-primary text-primary-foreground hover:bg-primary/90"
              }
            >
              {busy ? (
                <>
                  <Icon name="sync" size={14} aria-hidden className="er-pulse" />
                  Authorising…
                </>
              ) : (
                <>
                  <Icon name="shieldCheck" size={14} aria-hidden />
                  {isDestructive ? "I understand — run it" : "Authorise & run"}
                </>
              )}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </>
  );
}

export default RiskGateDialog;
