import type {NextConfig} from "next";

const API_URL = process.env.NEXT_PUBLIC_API_URL ||
    (process.env.NODE_ENV === 'production'
        ? (process.env.NEXT_PUBLIC_API_BASE_URL || 'https://api.mrrc.online')
        : '');

const nextConfig: NextConfig = {
    /* config options here */
    reactStrictMode: true,

    // Enable standalone output for Docker
    output: 'standalone',

    // Explicitly set environment variables for the build
    env: {
        NEXT_PUBLIC_API_URL: API_URL,
    },

    // Configure API proxy for development
    async rewrites() {
        // Only use rewrites in development mode
        if (process.env.NODE_ENV === 'development') {
            const apiUrl = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';
            return [
                {
                    source: '/api/:path*',
                    destination: `${apiUrl}/api/:path*`,
                },
            ];
        }
        return [];
    },
};

export default nextConfig;
