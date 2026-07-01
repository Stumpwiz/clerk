"use client";

import {useEffect, useState} from "react";
import {useRouter} from "next/navigation";
import {CheckCircle2} from "lucide-react";
import {LocalUserMenu} from "@/components/local-user-menu";
import type {LocalUser} from "@/lib/auth";
import {getCurrentUser} from "@/lib/auth";

export default function LocalSessionPage() {
    const router = useRouter();
    const [user, setUser] = useState<LocalUser | null>(null);
    const [error, setError] = useState<string | null>(null);
    const [isLoading, setIsLoading] = useState(true);

    useEffect(() => {
        let isMounted = true;

        async function loadCurrentUser() {
            try {
                const currentUser = await getCurrentUser();
                if (!isMounted) return;
                if (!currentUser) {
                    router.replace("/local-login?next=/local-session");
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
    }, [router]);

    return (
        <main className="min-h-screen bg-gray-50 px-4 py-10 text-gray-900">
            <div className="mx-auto flex w-full max-w-md flex-col gap-6">
                <div>
                    <h1 className="text-2xl font-semibold tracking-normal text-gray-950">Local Session</h1>
                    <p className="mt-2 text-sm text-gray-600">
                        This page exercises the local authentication backend without replacing Clerk.com.
                    </p>
                </div>

                <section className="rounded-lg border border-gray-200 bg-white p-5 shadow-sm">
                    {isLoading && <p className="text-sm text-gray-600">Checking local session...</p>}
                    {error && (
                        <p className="rounded-md border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">
                            {error}
                        </p>
                    )}
                    {user && (
                        <div className="flex flex-col gap-5">
                            <div className="flex items-center gap-2 text-green-700">
                                <CheckCircle2 className="h-5 w-5"/>
                                <h2 className="text-base font-semibold tracking-normal">
                                    Local authentication successful
                                </h2>
                            </div>

                            <LocalUserMenu user={user}/>

                            <dl className="grid gap-3 border-t border-gray-100 pt-4 text-sm">
                                <div>
                                    <dt className="font-medium text-gray-500">Display name</dt>
                                    <dd className="mt-1 text-gray-950">{user.display_name}</dd>
                                </div>
                                <div>
                                    <dt className="font-medium text-gray-500">Email address</dt>
                                    <dd className="mt-1 text-gray-950">{user.email}</dd>
                                </div>
                                <div>
                                    <dt className="font-medium text-gray-500">Active status</dt>
                                    <dd className="mt-1 text-gray-950">{user.is_active ? "Active" : "Inactive"}</dd>
                                </div>
                            </dl>
                        </div>
                    )}
                </section>
            </div>
        </main>
    );
}
