import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  reactStrictMode: true,
  output: "standalone",          // ✅ enables small runtime image
  swcMinify: true,
  trailingSlash: false,          // optional: consistent URLs
  poweredByHeader: false,        // removes "x-powered-by"
  eslint: { ignoreDuringBuilds: true },
  typescript: { ignoreBuildErrors: true },
  // Optional: for API prefix consistency
  async rewrites() {
    return [
      {
        source: "/api/proxy/:path*",
        destination: "http://api:8000/api/v1/:path*",  // internal docker host
      },
    ];
  },
};

export default nextConfig;
