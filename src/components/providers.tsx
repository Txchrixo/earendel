"use client";

import { SessionProvider } from "next-auth/react";
import type { ReactNode } from "react";
import { TokenSync } from "@/components/earendel/token-sync";

export function Providers({ children }: { children: ReactNode }) {
  return (
    <SessionProvider>
      <TokenSync />
      {children}
    </SessionProvider>
  );
}
