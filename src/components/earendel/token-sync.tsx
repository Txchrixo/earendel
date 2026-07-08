"use client";

import { useEffect } from "react";
import { useSession } from "next-auth/react";
import { setAuthToken } from "@/lib/earendel/api-client";

/**
 * TokenSync — invisible component that reads the NextAuth session and
 * syncs the backendToken to the API client's module-level cache.
 *
 * Mount this once near the root of the app (inside SessionProvider).
 */
export function TokenSync() {
  const { data: session } = useSession();

  useEffect(() => {
    const token = (session as { backendToken?: string } | null)?.backendToken ?? null;
    setAuthToken(token);
  }, [session]);

  return null;
}
