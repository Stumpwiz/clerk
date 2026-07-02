'use client';

import {useEffect, useState} from "react";
import type {LocalUser} from "@/lib/auth";
import {getCurrentUser} from "@/lib/auth";

export default function ProfilePage() {
    const [user, setUser] = useState<LocalUser | null>(null);

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
        </div>
    );
}
