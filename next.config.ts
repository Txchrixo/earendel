import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  output: "standalone",
  /* config options here */
  typescript: {
    ignoreBuildErrors: true,
  },
  reactStrictMode: false,
  async rewrites() {
    // Proxy all /api/v1/* calls to the FastAPI backend on port 8001.
    // The ?XTransformPort= query param is kept for Caddy compatibility but
    // Next.js dev server (port 3000) needs its own rewrite to reach the backend.
    const backendUrl = process.env.BACKEND_URL || "http://localhost:8001";
    return [
      {
        source: "/api/v1/:path*",
        destination: `${backendUrl}/api/v1/:path*`,
      },
    ];
  },
};

export default nextConfig;
