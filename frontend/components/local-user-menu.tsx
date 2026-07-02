"use client";

import {LogOut} from "lucide-react";
import {useRouter} from "next/navigation";
import {useState} from "react";
import type {LocalUser} from "@/lib/auth";
import {logout} from "@/lib/auth";

interface LocalUserMenuProps {
    user: LocalUser;
    variant?: "default" | "compact";
}

function avatarSrc(user: LocalUser): string {
    return user.avatar_path || "/logo.svg";
}

export function LocalUserMenu({user, variant = "default"}: LocalUserMenuProps) {
    const router = useRouter();
    const [error, setError] = useState<string | null>(null);
    const [isLoggingOut, setIsLoggingOut] = useState(false);

    const handleLogout = async () => {
        setIsLoggingOut(true);
        setError(null);
        try {
            await logout();
            router.replace("/local-login");
            router.refresh();
        } catch (err) {
            setError(err instanceof Error ? err.message : "Logout failed");
        } finally {
            setIsLoggingOut(false);
        }
    };

    if (variant === "compact") {
        return (
            <div className="flex items-center gap-3">
                {/* eslint-disable-next-line @next/next/no-img-element */}
                <img
                    src={avatarSrc(user)}
                    alt=""
                    className="h-9 w-9 rounded-full border border-gray-200 bg-white object-cover"
                />
                <div className="hidden min-w-0 text-right sm:block">
                    <div className="max-w-40 truncate text-sm font-medium text-gray-900">{user.display_name}</div>
                    <div className="max-w-40 truncate text-xs text-gray-500">{user.email}</div>
                </div>
                <button
                    type="button"
                    onClick={handleLogout}
                    disabled={isLoggingOut}
                    className="inline-flex h-9 w-9 items-center justify-center rounded-md border border-gray-300 bg-white text-gray-700 hover:bg-gray-50 disabled:cursor-not-allowed disabled:opacity-60"
                    title="Logout"
                    aria-label="Logout"
                >
                    <LogOut className="h-4 w-4"/>
                </button>
                {error && <span className="sr-only">{error}</span>}
            </div>
        );
    }

    return (
        <div className="flex flex-col gap-3">
            <div className="flex items-center gap-3">
                {/* eslint-disable-next-line @next/next/no-img-element */}
                <img
                    src={avatarSrc(user)}
                    alt=""
                    className="h-11 w-11 rounded-full border border-gray-200 bg-white object-cover"
                />
                <div className="min-w-0">
                    <div className="truncate text-sm font-semibold text-gray-900">{user.display_name}</div>
                    <div className="truncate text-xs text-gray-500">{user.email}</div>
                </div>
            </div>
            {error && (
                <p className="rounded-md border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">
                    {error}
                </p>
            )}
            <button
                type="button"
                onClick={handleLogout}
                disabled={isLoggingOut}
                className="inline-flex items-center justify-center gap-2 rounded-md bg-gray-900 px-3 py-2 text-sm font-medium text-white hover:bg-gray-700 disabled:cursor-not-allowed disabled:opacity-60"
            >
                <LogOut className="h-4 w-4"/>
                {isLoggingOut ? "Signing out..." : "Logout"}
            </button>
        </div>
    );
}
