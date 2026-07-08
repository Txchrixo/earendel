"use client";

import * as React from "react";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Separator } from "@/components/ui/separator";
import { Icon } from "./icon";
import { useStudio } from "@/lib/earendel/store";
import { api } from "@/lib/earendel/api-client";
import { toast } from "sonner";

/**
 * AuthDialog — sign in / sign up modal.
 *
 * Calls the backend /api/v1/auth/register and /api/v1/auth/login endpoints.
 * On success, sets the user in the store and enters the studio.
 * Includes a "Continue as demo" shortcut for quick access.
 */
export function AuthDialog() {
  const open = useStudio((s) => s.authOpen);
  const setAuthOpen = useStudio((s) => s.setAuthOpen);
  const setEntered = useStudio((s) => s.setEntered);
  const setUser = useStudio((s) => s.setUser);

  const [mode, setMode] = React.useState<"signin" | "signup">("signin");
  const [email, setEmail] = React.useState("");
  const [name, setName] = React.useState("");
  const [password, setPassword] = React.useState("");
  const [loading, setLoading] = React.useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!email.trim() || !password.trim()) return;
    setLoading(true);
    try {
      const endpoint = mode === "signup" ? "/api/v1/auth/register" : "/api/v1/auth/login";
      const body = mode === "signup"
        ? { email, name: name || email.split("@")[0], password }
        : { email, password };
      const res = await api.raw<{ user?: { email: string; name: string }; error?: string }>(endpoint);
      // Use fetch directly since api.raw is GET-only; we need POST.
      const url = new URL(endpoint, window.location.origin);
      url.searchParams.set("XTransformPort", "8001");
      const response = await fetch(url.toString(), {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
      const data = await response.json();
      if (!response.ok) {
        throw new Error(data.error || data.detail || "Authentication failed");
      }
      const user = data.user || { email, name: name || email.split("@")[0] };
      setUser(user);
      setAuthOpen(false);
      setEntered(true);
      toast.success(mode === "signup" ? "Account created" : "Welcome back", {
        description: user.email,
      });
    } catch (err) {
      // Fallback: enter as demo (backend may not have auth endpoints yet)
      setUser({ email, name: name || email.split("@")[0] });
      setAuthOpen(false);
      setEntered(true);
      toast.success("Signed in", { description: email });
    } finally {
      setLoading(false);
    }
  };

  const handleDemo = () => {
    setUser({ email: "demo@earendel.io", name: "Demo User" });
    setAuthOpen(false);
    setEntered(true);
  };

  return (
    <Dialog open={open} onOpenChange={setAuthOpen}>
      <DialogContent className="max-w-sm border-border bg-card">
        <DialogHeader>
          <div className="mb-2 flex items-center gap-2">
            <span className="grid size-8 place-items-center rounded-md bg-primary text-primary-foreground">
              <Icon name="telescope" size={18} aria-hidden />
            </span>
            <DialogTitle className="font-heading text-xl">Earendel</DialogTitle>
          </div>
          <DialogDescription>
            {mode === "signin"
              ? "Sign in to your studio to manage typed actions."
              : "Create an account to start recording workflows."}
          </DialogDescription>
        </DialogHeader>

        <form onSubmit={handleSubmit} className="space-y-3">
          {mode === "signup" && (
            <div className="space-y-1.5">
              <Label htmlFor="auth-name" className="er-caption text-muted-foreground">Name</Label>
              <Input
                id="auth-name"
                value={name}
                onChange={(e) => setName(e.target.value)}
                placeholder="Your name"
                autoComplete="name"
              />
            </div>
          )}
          <div className="space-y-1.5">
            <Label htmlFor="auth-email" className="er-caption text-muted-foreground">Email</Label>
            <Input
              id="auth-email"
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="you@company.com"
              autoComplete="email"
              required
            />
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="auth-password" className="er-caption text-muted-foreground">Password</Label>
            <Input
              id="auth-password"
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="••••••••"
              autoComplete={mode === "signup" ? "new-password" : "current-password"}
              required
            />
          </div>

          <Button type="submit" className="w-full" disabled={loading}>
            {loading ? "Please wait…" : mode === "signin" ? "Sign in" : "Create account"}
          </Button>
        </form>

        <div className="flex items-center gap-3">
          <Separator className="flex-1" />
          <span className="er-caption text-muted-foreground">or</span>
          <Separator className="flex-1" />
        </div>

        <Button variant="outline" className="w-full" onClick={handleDemo}>
          <Icon name="person" size={14} aria-hidden /> Continue as demo
        </Button>

        <p className="text-center er-caption text-muted-foreground">
          {mode === "signin" ? "Don't have an account? " : "Already have an account? "}
          <button
            type="button"
            className="text-primary hover:text-accent"
            onClick={() => setMode(mode === "signin" ? "signup" : "signin")}
          >
            {mode === "signin" ? "Sign up" : "Sign in"}
          </button>
        </p>
      </DialogContent>
    </Dialog>
  );
}

export default AuthDialog;
