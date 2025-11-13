import type {Metadata} from "next";
import {ClerkProvider} from "@clerk/nextjs";
import "./globals.css";
import type {ReactNode} from "react";

// Force dynamic rendering - required for Clerk authentication
export const dynamic = 'force-dynamic';

export const metadata: Metadata = {
    title: "Retirement Community Admin",
    description: "Administrative system for retirement community management",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: ReactNode;
}>) {
    return (
        <ClerkProvider>
            <html lang="en">
            <body>
            {children}
            </body>
            </html>
        </ClerkProvider>
    );
}
