/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  output: "standalone",
  experimental: {
    serverActions: {
      bodySizeLimit: "10mb",
    },
  },
  async rewrites() {
    // The browser calls relative /api/v1/* (same-origin). Next proxies that,
    // SERVER-SIDE from inside the web container, to the FastAPI backend.
    //
    // IMPORTANT: rewrite destinations are frozen at BUILD time, so the value
    // here is what gets compiled in. Inside Docker the API is always reachable
    // as the compose service name `api:8000`, so that's the default.
    //
    // For local dev OUTSIDE Docker (npm run dev), set API_PROXY_TARGET=http://localhost:8000.
    const target = process.env.API_PROXY_TARGET || "http://api:8000";
    return [
      {
        source: "/api/v1/:path*",
        destination: `${target}/api/v1/:path*`,
      },
    ];
  },
};

export default nextConfig;
