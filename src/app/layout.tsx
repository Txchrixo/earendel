import type { Metadata } from "next";
import { Cormorant_Garamond, Hanken_Grotesk } from "next/font/google";
import "./globals.css";
import { Toaster } from "@/components/ui/toaster";

const heading = Cormorant_Garamond({
  variable: "--font-heading",
  subsets: ["latin"],
  weight: ["400", "500", "600"],
  display: "swap",
});

const body = Hanken_Grotesk({
  variable: "--font-body",
  subsets: ["latin"],
  weight: ["400", "500"],
  display: "swap",
});

export const metadata: Metadata = {
  title: "Earendel — Typed Actions for Agents",
  description:
    "Earendel is a reliability layer that turns repeated authorized business workflows into typed, monitored, repairable tools for AI agents. Record once, compile to a typed action, validate continuously, repair automatically.",
  keywords: [
    "Earendel",
    "NoAPI",
    "typed actions",
    "web verbs",
    "MCP",
    "agent tools",
    "RPA",
    "AutoRPA",
    "workflow automation",
  ],
  authors: [{ name: "Earendel" }],
  icons: {
    icon: "/logo.svg",
  },
  openGraph: {
    title: "Earendel — Typed Actions for Agents",
    description:
      "Record authorized human workflows. Compile to typed, monitored, repairable tools agents can call.",
    type: "website",
  },
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" className="dark" suppressHydrationWarning>
      <head>
        <link rel="preconnect" href="https://fonts.googleapis.com" />
        <link
          rel="preconnect"
          href="https://fonts.gstatic.com"
          crossOrigin="anonymous"
        />
      </head>
      <body
        className={`${heading.variable} ${body.variable} antialiased bg-background text-foreground`}
      >
        {children}
        <Toaster />
      </body>
    </html>
  );
}
