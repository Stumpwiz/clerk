'use client';

import {useEffect, useState} from "react";
import type {LocalUser} from "@/lib/auth";
import {getCurrentUser} from "@/lib/auth";
import {Toast} from "@/components/toast";

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL ?? "";

interface PasswordFormData {
    currentPassword: string;
    newPassword: string;
    confirmPassword: string;
}

const emptyPasswordForm: PasswordFormData = {
    currentPassword: "",
    newPassword: "",
    confirmPassword: "",
};

function getApiErrorMessage(errorBody: unknown, fallback: string) {
    if (
        errorBody &&
        typeof errorBody === "object" &&
        "detail" in errorBody
    ) {
        const detail = (errorBody as {detail: unknown}).detail;
        if (typeof detail === "string") return detail;
        if (Array.isArray(detail) && detail.length > 0) {
            const firstError = detail[0] as {msg?: unknown};
            if (typeof firstError.msg === "string") return firstError.msg;
        }
    }
    return fallback;
}

export default function ProfilePage() {
    const [user, setUser] = useState<LocalUser | null>(null);
    const [passwordForm, setPasswordForm] = useState<PasswordFormData>(emptyPasswordForm);
    const [passwordError, setPasswordError] = useState<string | null>(null);
    const [submittingPassword, setSubmittingPassword] = useState(false);
    const [toast, setToast] = useState<{
        message: string;
        type: "success" | "error";
    } | null>(null);

    useEffect(() => {
        let isMounted = true;

        async function loadCurrentUser() {
            const currentUser = await getCurrentUser();
            if (isMounted) {
                setUser(currentUser);
            }
        }

        loadCurrentUser();

        return () => {
            isMounted = false;
        };
    }, []);

    const handlePasswordSubmit = async (event: React.FormEvent<HTMLFormElement>) => {
        event.preventDefault();
        setPasswordError(null);

        if (!passwordForm.currentPassword || !passwordForm.newPassword || !passwordForm.confirmPassword) {
            setPasswordError("Current password, new password, and confirmation are required.");
            return;
        }

        if (passwordForm.newPassword.length < 8) {
            setPasswordError("New password must be at least 8 characters.");
            return;
        }

        if (passwordForm.newPassword !== passwordForm.confirmPassword) {
            setPasswordError("New password and confirmation do not match.");
            return;
        }

        try {
            setSubmittingPassword(true);
            const response = await fetch(`${API_BASE_URL}/api/auth/change-password`, {
                method: "POST",
                credentials: "include",
                headers: {
                    "Content-Type": "application/json",
                },
                body: JSON.stringify({
                    current_password: passwordForm.currentPassword,
                    new_password: passwordForm.newPassword,
                    confirm_password: passwordForm.confirmPassword,
                }),
            });

            if (!response.ok) {
                const errorBody = await response.json().catch(() => null);
                throw new Error(getApiErrorMessage(errorBody, "Failed to change password"));
            }

            setPasswordForm(emptyPasswordForm);
            setToast({message: "Password changed successfully.", type: "success"});
        } catch (error) {
            setPasswordError(error instanceof Error ? error.message : "Failed to change password");
        } finally {
            setSubmittingPassword(false);
        }
    };

    return (
        <div className="space-y-6">
            <div>
                <h1 className="text-3xl font-bold text-gray-900">My Profile</h1>
                <p className="mt-2 text-sm text-gray-600">
                    View your local account details.
                </p>
            </div>

            <div className="bg-white shadow rounded-lg p-6">
                {user ? (
                    <dl className="grid gap-4 text-sm">
                        <div>
                            <dt className="font-medium text-gray-500">Display name</dt>
                            <dd className="mt-1 text-gray-950">{user.display_name}</dd>
                        </div>
                        <div>
                            <dt className="font-medium text-gray-500">Email address</dt>
                            <dd className="mt-1 text-gray-950">{user.email}</dd>
                        </div>
                        <div>
                            <dt className="font-medium text-gray-500">Status</dt>
                            <dd className="mt-1 text-gray-950">{user.is_active ? "Active" : "Inactive"}</dd>
                        </div>
                    </dl>
                ) : (
                    <p className="text-sm text-gray-600">Loading profile...</p>
                )}
            </div>

            <div className="bg-white shadow rounded-lg p-6">
                <h2 className="text-xl font-semibold text-gray-900">Change Password</h2>

                <form onSubmit={handlePasswordSubmit} className="mt-4 space-y-4">
                    {passwordError && (
                        <div className="bg-red-50 border border-red-200 text-red-700 px-3 py-2 rounded text-sm">
                            {passwordError}
                        </div>
                    )}

                    <div>
                        <label htmlFor="current-password" className="block text-sm font-medium text-gray-700 mb-1">
                            Current Password
                        </label>
                        <input
                            type="password"
                            id="current-password"
                            value={passwordForm.currentPassword}
                            onChange={(event) => setPasswordForm({...passwordForm, currentPassword: event.target.value})}
                            autoComplete="current-password"
                            className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 text-gray-900"
                            required
                        />
                    </div>

                    <div>
                        <label htmlFor="new-password" className="block text-sm font-medium text-gray-700 mb-1">
                            New Password
                        </label>
                        <input
                            type="password"
                            id="new-password"
                            value={passwordForm.newPassword}
                            onChange={(event) => setPasswordForm({...passwordForm, newPassword: event.target.value})}
                            autoComplete="new-password"
                            className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 text-gray-900"
                            required
                        />
                    </div>

                    <div>
                        <label htmlFor="confirm-password" className="block text-sm font-medium text-gray-700 mb-1">
                            Confirm New Password
                        </label>
                        <input
                            type="password"
                            id="confirm-password"
                            value={passwordForm.confirmPassword}
                            onChange={(event) => setPasswordForm({...passwordForm, confirmPassword: event.target.value})}
                            autoComplete="new-password"
                            className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 text-gray-900"
                            required
                        />
                    </div>

                    <div className="flex justify-end">
                        <button
                            type="submit"
                            className="px-4 py-2 text-sm font-medium text-white bg-blue-600 border border-transparent rounded-md hover:bg-blue-700 disabled:opacity-50"
                            disabled={submittingPassword}
                        >
                            {submittingPassword ? "Saving..." : "Change Password"}
                        </button>
                    </div>
                </form>
            </div>

            {toast && (
                <Toast
                    message={toast.message}
                    type={toast.type}
                    onClose={() => setToast(null)}
                />
            )}
        </div>
    );
}
