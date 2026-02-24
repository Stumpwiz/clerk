import type {NextConfig} from "next";

// Use HTTPS API URL if NEXT_PUBLIC_API_URL is not explicitly set
// This ensures production builds always use HTTPS
const API_URL = process.env.NEXT_PUBLIC_API_URL || 'https://api.mrrc.online';

const nextConfig: NextConfig = {
    /* config options here */
    reactStrictMode: true,

    // Enable standalone output for Docker
    output: 'standalone',

    // Explicitly set environment variables for the build
    env: {
        NEXT_PUBLIC_API_URL: API_URL,
        NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY: process.env.NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY || 'pk_test_Y3V0ZS1tb25rZXktMjUuY2xlcmsuYWNjb3VudHMuZGV2JA',
        NEXT_PUBLIC_CLERK_SIGN_IN_URL: process.env.NEXT_PUBLIC_CLERK_SIGN_IN_URL || '/sign-in',
        NEXT_PUBLIC_CLERK_SIGN_UP_URL: process.env.NEXT_PUBLIC_CLERK_SIGN_UP_URL || '/sign-up',
        NEXT_PUBLIC_CLERK_FALLBACK_REDIRECT_URL: process.env.NEXT_PUBLIC_CLERK_FALLBACK_REDIRECT_URL || '/dashboard',
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
