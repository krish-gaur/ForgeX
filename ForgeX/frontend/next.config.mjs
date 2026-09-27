/** @type {import('next').NextConfig} */
const BACKEND = (process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000").replace(/\/+$/, "");

const nextConfig = {
  reactStrictMode: true,
  // Self-contained production server for the Docker image (infrastructure/docker).
  output: "standalone",
  // The browser only ever talks to the Next.js origin; it proxies to FastAPI.
  async rewrites() {
    return [
      { source: "/api/:path*", destination: `${BACKEND}/api/:path*` },
      { source: "/ws", destination: `${BACKEND}/ws` },
      { source: "/health", destination: `${BACKEND}/health` },
    ];
  },
  allowedDevOrigins: ["*.e2b.app", "localhost"],
};

export default nextConfig;
