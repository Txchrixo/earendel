"use client";

import { useState } from "react";
import { signIn } from "next-auth/react";
import { useRouter } from "next/navigation";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Card } from "@/components/ui/card";
import { Icon } from "@/components/earendel/icon";
import { toast } from "sonner";

export default function SignUpPage() {
  const router = useRouter();

  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [loading, setLoading] = useState(false);
  const [errors, setErrors] = useState<{ name?: string; email?: string; password?: string }>({});

  const validate = (): boolean => {
    const e: typeof errors = {};
    if (!name.trim()) e.name = "Name is required";
    if (!email.trim()) {
      e.email = "Email is required";
    } else if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) {
      e.email = "Invalid email format";
    }
    if (!password) {
      e.password = "Password is required";
    } else if (password.length < 8) {
      e.password = "Password must be at least 8 characters";
    } else if (!/[A-Z]/.test(password) || !/[a-z]/.test(password) || !/[0-9]/.test(password)) {
      e.password = "Password must contain upper, lower, and a number";
    }
    setErrors(e);
    return Object.keys(e).length === 0;
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!validate()) return;
    setLoading(true);
    try {
      // Create the user via NextAuth API route
      const res = await fetch("/api/auth/signup", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name, email: email.toLowerCase(), password }),
      });
      const data = await res.json();
      if (!res.ok) {
        throw new Error(data.error || "Registration failed");
      }
      // Auto sign-in after signup
      const result = await signIn("credentials", {
        email,
        password,
        redirect: false,
      });
      if (result?.error) {
        toast.error("Account created but sign-in failed", {
          description: "Please sign in manually.",
        });
        router.push("/auth/signin");
      } else {
        toast.success("Account created", { description: "Welcome to Earendel" });
        router.push("/");
        router.refresh();
      }
    } catch (err) {
      toast.error("Registration failed", {
        description: err instanceof Error ? err.message : "Please try again",
      });
    } finally {
      setLoading(false);
    }
  };

  const handleGoogle = () => {
    signIn("google", { callbackUrl: "/" });
  };

  return (
    <div className="flex min-h-screen items-center justify-center bg-background px-4">
      <Card className="w-full max-w-sm p-8">
        {/* Logo */}
        <div className="mb-8 flex flex-col items-center gap-3">
          <span className="grid size-12 place-items-center rounded-md bg-primary text-primary-foreground">
            <Icon name="telescope" size={24} aria-hidden />
          </span>
          <h1 className="er-h2 font-heading">Create your account</h1>
          <p className="er-caption text-muted-foreground text-center">
            Start recording workflows in minutes
          </p>
        </div>

        {/* Google OAuth */}
        <Button
          variant="outline"
          className="w-full mb-4"
          onClick={handleGoogle}
          disabled={loading}
        >
          <Icon name="person" size={16} aria-hidden />
          Continue with Google
        </Button>

        {/* Divider */}
        <div className="flex items-center gap-3 mb-4">
          <div className="h-px flex-1 bg-border" />
          <span className="er-caption text-muted-foreground">or</span>
          <div className="h-px flex-1 bg-border" />
        </div>

        {/* Sign up form */}
        <form onSubmit={handleSubmit} className="space-y-4">
          <div className="space-y-1.5">
            <Label htmlFor="name" className="er-caption text-muted-foreground">
              Name
            </Label>
            <Input
              id="name"
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="Your name"
              autoComplete="name"
            />
            {errors.name && (
              <p className="er-caption text-destructive">{errors.name}</p>
            )}
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="email" className="er-caption text-muted-foreground">
              Email
            </Label>
            <Input
              id="email"
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="you@company.com"
              autoComplete="email"
            />
            {errors.email && (
              <p className="er-caption text-destructive">{errors.email}</p>
            )}
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="password" className="er-caption text-muted-foreground">
              Password
            </Label>
            <Input
              id="password"
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="Min 8 chars, 1 upper, 1 lower, 1 number"
              autoComplete="new-password"
            />
            {errors.password && (
              <p className="er-caption text-destructive">{errors.password}</p>
            )}
          </div>
          <Button type="submit" className="w-full" disabled={loading}>
            {loading ? "Creating account…" : "Create account"}
          </Button>
        </form>

        {/* Sign in link */}
        <p className="mt-6 text-center er-caption text-muted-foreground">
          Already have an account?{" "}
          <button
            type="button"
            className="text-primary hover:text-accent font-medium"
            onClick={() => router.push("/auth/signin")}
          >
            Sign in
          </button>
        </p>
      </Card>
    </div>
  );
}
