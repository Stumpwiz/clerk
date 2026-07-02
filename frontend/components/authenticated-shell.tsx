"use client";

import {useEffect, useState} from "react";
import {usePathname, useRouter} from "next/navigation";
import {Loader2} from "lucide-react";
import {Navigation} from "@/components/navigation";
import type {LocalUser} from "@/lib/auth";
import {getCurrentUser} from "@/lib/auth";

interface AuthenticatedShellProps {
    children: React.ReactNode;
}

export function AuthenticatedShell({children}: AuthenticatedShellProps) {
    const pathname = usePathname();
    const router = useRouter();
    const [user, setUser] = useState<LocalUser | null>(null);
    const [isLoading, setIsLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);

    useEffect(() => {
        let isMounted = true;

        async function loadCurrentUser() {
            try {
                const currentUser = await getCurrentUser();
                if (!isMounted) return;

                if (!currentUser) {
                    const nextPath = pathname || "/dashboard";
                    router.replace(`/local-login?next=${encodeURIComponent(nextPath)}`);
                    return;
                }

                setUser(currentUser);
            } catch (err) {
                if (!isMounted) return;
                setError(err instanceof Error ? err.message : "Unable to load local session");
            } finally {
                if (isMounted) {
                    setIsLoading(false);
                }
            }
        }

        loadCurrentUser();

        return () => {
            isMounted = false;
        };
    }, [pathname, router]);

    if (isLoading || !user) {
        return (
            <div className="min-h-screen bg-gray-50">
                <div className="flex h-screen items-center justify-center">
                    <Loader2 className="h-8 w-8 animate-spin text-blue-600"/>
                </div>
            </div>
        );
    }

    return (
        <div className="min-h-screen bg-gray-50">
            <Navigation user={user}/>
            <main className="max-w-7xl mx-auto py-6 sm:px-6 lg:px-8">
                {error && (
                    <div className="mb-4 rounded-md border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
                        {error}
                    </div>
                )}
                {children}
            </main>
        </div>
    );
}
