"use client";

import {FormEvent, useMemo, useState} from "react";
import {useRouter, useSearchParams} from "next/navigation";
import {LogIn} from "lucide-react";
import {login} from "@/lib/auth";

function safeNext(rawNext: string | null): string {
    if (!rawNext || !rawNext.startsWith("/") || rawNext.startsWith("//")) {
        return "/dashboard";
    }
    return rawNext;
}

export default function LocalLoginPage() {
    const router = useRouter();
    const searchParams = useSearchParams();
    const nextPath = useMemo(() => safeNext(searchParams.get("next")), [searchParams]);
    const [email, setEmail] = useState("");
    const [password, setPassword] = useState("");
    const [error, setError] = useState<string | null>(null);
    const [isSubmitting, setIsSubmitting] = useState(false);

    const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
        event.preventDefault();
        setError(null);

        const trimmedEmail = email.trim();
        if (!trimmedEmail || !password) {
            setError("Enter your email and password.");
            return;
        }

        setIsSubmitting(true);
        try {
            await login(trimmedEmail, password);
            router.replace(nextPath);
            router.refresh();
        } catch (err) {
            setError(err instanceof Error ? err.message : "Login failed");
        } finally {
            setIsSubmitting(false);
        }
    };

    return (
        <main className="min-h-screen bg-gray-50 px-4 py-10 text-gray-900">
            <div className="mx-auto flex w-full max-w-md flex-col gap-6">
                <div>
                    <h1 className="text-2xl font-semibold tracking-normal text-gray-950">Local Login</h1>
                    <p className="mt-2 text-sm text-gray-600">
                        Sign in with your local account to access the administration dashboard.
                    </p>
                </div>

                <form onSubmit={handleSubmit} className="space-y-4 rounded-lg border border-gray-200 bg-white p-5 shadow-sm">
                    {error && (
                        <div className="rounded-md border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">
                            {error}
                        </div>
                    )}

                    <div>
                        <label htmlFor="email" className="block text-sm font-medium text-gray-700">
                            Email
                        </label>
                        <input
                            id="email"
                            type="email"
                            value={email}
                            onChange={(event) => setEmail(event.target.value)}
                            autoComplete="email"
                            className="mt-1 block w-full rounded-md border border-gray-300 px-3 py-2 text-sm text-gray-900 shadow-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
                            required
                        />
                    </div>

                    <div>
                        <label htmlFor="password" className="block text-sm font-medium text-gray-700">
                            Password
                        </label>
                        <input
                            id="password"
                            type="password"
                            value={password}
                            onChange={(event) => setPassword(event.target.value)}
                            autoComplete="current-password"
                            className="mt-1 block w-full rounded-md border border-gray-300 px-3 py-2 text-sm text-gray-900 shadow-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
                            required
                        />
                    </div>

                    <button
                        type="submit"
                        disabled={isSubmitting}
                        className="inline-flex w-full items-center justify-center gap-2 rounded-md bg-blue-600 px-4 py-2 text-sm font-medium text-white shadow-sm hover:bg-blue-700 disabled:cursor-not-allowed disabled:opacity-60"
                    >
                        <LogIn className="h-4 w-4"/>
                        {isSubmitting ? "Signing in..." : "Login"}
                    </button>
                </form>
            </div>
        </main>
    );
}
