'use client';

import {UserProfile} from '@clerk/nextjs';

export default function ProfilePage() {
    return (
        <div className="space-y-6">
            <div>
                <h1 className="text-3xl font-bold text-gray-900">My Profile</h1>
                <p className="mt-2 text-sm text-gray-600">
                    Manage your account settings, password, and personal information
                </p>
            </div>

            <div className="bg-white shadow rounded-lg p-6">
                <UserProfile
                    routing="hash"
                    appearance={{
                        elements: {
                            rootBox: "w-full",
                            card: "shadow-none",
                        }
                    }}
                />
            </div>
        </div>
    );
}
