/**
 * NextAuth.js configuration — production-grade auth for Earendel.
 *
 * Providers:
 *   - Google OAuth (for SSO)
 *   - Credentials (email/password with bcrypt)
 *
 * Session: JWT strategy (stateless, works with FastAPI backend)
 * Adapter: Prisma (stores users/accounts in the DB)
 *
 * The JWT callback mints a separate `backendToken` (signed with
 * BACKEND_SECRET) that the FastAPI middleware verifies on every
 * protected API call.
 */
import type { NextAuthOptions } from "next-auth";
import GoogleProvider from "next-auth/providers/google";
import CredentialsProvider from "next-auth/providers/credentials";
import { PrismaAdapter } from "@auth/prisma-adapter";
import { PrismaClient } from "@prisma/client";
import bcrypt from "bcryptjs";
import jwt from "jsonwebtoken";
import type { Adapter } from "next-auth/adapters";

const prisma = new PrismaClient();

const BACKEND_SECRET = process.env.BACKEND_SECRET || process.env.NEXTAUTH_SECRET || "dev-secret-change-me";

/** Mint a short-lived JWT that the FastAPI backend can verify. */
function mintBackendToken(userId: string, email: string): string {
  return jwt.sign({ uid: userId, email }, BACKEND_SECRET, {
    expiresIn: "7d",
    issuer: "earendel-studio",
    audience: "earendel-api",
  });
}

export const authOptions: NextAuthOptions = {
  adapter: PrismaAdapter(prisma) as Adapter,
  session: { strategy: "jwt" },
  providers: [
    GoogleProvider({
      clientId: process.env.GOOGLE_CLIENT_ID!,
      clientSecret: process.env.GOOGLE_CLIENT_SECRET!,
    }),
    CredentialsProvider({
      name: "credentials",
      credentials: {
        email: { label: "Email", type: "email" },
        password: { label: "Password", type: "password" },
        demo: { label: "Demo", type: "text" },
      },
      async authorize(credentials) {
        // Demo mode: skip password check, create/use a demo user
        if (credentials?.demo === "true") {
          const demoEmail = "demo@earendel.io";
          let demoUser = await prisma.user.findUnique({
            where: { email: demoEmail },
          });
          if (!demoUser) {
            demoUser = await prisma.user.create({
              data: {
                email: demoEmail,
                name: "Demo User",
                role: "owner",
              },
            });
          }
          return {
            id: demoUser.id,
            email: demoUser.email,
            name: demoUser.name ?? "Demo User",
          };
        }

        if (!credentials?.email || !credentials?.password) return null;

        const user = await prisma.user.findUnique({
          where: { email: credentials.email.toLowerCase() },
        });

        if (!user || !user.passwordHash) return null;

        const valid = await bcrypt.compare(credentials.password, user.passwordHash);
        if (!valid) return null;

        return {
          id: user.id,
          email: user.email,
          name: user.name ?? undefined,
          image: user.image ?? undefined,
        };
      },
    }),
  ],
  callbacks: {
    async jwt({ token, user, account }) {
      // On first sign-in (user is defined), add the backend token.
      if (user) {
        token.uid = user.id;
        token.backendToken = mintBackendToken(
          user.id,
          user.email ?? "",
        );
      }
      // On Google OAuth first sign-in, account is defined.
      if (account?.provider === "google" && user) {
        token.backendToken = mintBackendToken(
          user.id,
          user.email ?? "",
        );
      }
      return token;
    },
    async session({ session, token }) {
      // Expose uid + backendToken to the client session.
      if (session.user) {
        (session.user as { id?: string }).id = token.uid as string;
        (session as { backendToken?: string }).backendToken = token.backendToken as string;
      }
      return session;
    },
  },
  pages: {
    signIn: "/auth/signin",
    signOut: "/",
    error: "/auth/signin",
  },
  cookies: {
    sessionToken: {
      name: "next-auth.session-token",
      options: {
        httpOnly: true,
        sameSite: "lax",
        path: "/",
        secure: process.env.NODE_ENV === "production",
      },
    },
  },
  secret: process.env.NEXTAUTH_SECRET,
};

export default authOptions;
