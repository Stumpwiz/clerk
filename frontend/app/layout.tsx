import type {Metadata} from "next";
import "./globals.css";
import type {ReactNode} from "react";

// Force dynamic rendering for authenticated application pages.
export const dynamic = 'force-dynamic';

export const metadata: Metadata = {
    title: "Retirement Community Admin",
    description: "Administrative system for retirement community management",
    icons: {
        icon: [
            { url: '/favicon.ico', sizes: 'any' },
            { url: '/icon.svg', type: 'image/svg+xml' },
        ],
        apple: '/apple-icon.png',
    },
};

export default function RootLayout({
  children,
}: Readonly<{
  children: ReactNode;
}>) {
    return (
        <html lang="en">
        <body>
        {children}
        </body>
        </html>
    );
}
