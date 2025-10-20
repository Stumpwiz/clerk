/** @type {import('next').NextConfig} */
const nextConfig = {
  // Do not fail the production build on ESLint errors
  eslint: {
    ignoreDuringBuilds: true,
  },
  // Do not fail the production build on TypeScript errors
  typescript: {
    ignoreBuildErrors: true,
  },
};

module.exports = nextConfig;
