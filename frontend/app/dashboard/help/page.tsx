"use client";

import {useState} from "react";
import Link from "next/link";
import {ExternalLink, Loader2} from "lucide-react";

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL ?? "";

const tasks = [
    {
        task: "Add or correct someone's name, email, phone, or apartment",
        links: [{label: "Persons", href: "/dashboard/persons"}],
    },
    {
        task: "Assign someone to an office or change service dates",
        links: [{label: "Terms", href: "/dashboard/terms"}],
    },
    {
        task: "Show that an office is empty",
        note: "Use (Vacant)",
        links: [{label: "Terms", href: "/dashboard/terms"}],
    },
    {
        task: "Create a welcome letter",
        links: [{label: "Letters", href: "/dashboard/letters"}],
    },
    {
        task: "Create or update a roster/report",
        links: [{label: "Rosters & Reports", href: "/dashboard/reports"}],
    },
    {
        task: "Create an email address list",
        links: [{label: "Mailing Lists", href: "/dashboard/mailing-lists"}],
    },
    {
        task: "Change the organizational structure",
        links: [
            {label: "Bodies", href: "/dashboard/bodies"},
            {label: "Offices", href: "/dashboard/offices"},
        ],
    },
    {
        task: "Add, deactivate, or reset a Clerk login",
        links: [{label: "Users", href: "/dashboard/users"}],
    },
    {
        task: "Change your own password",
        links: [{label: "My Profile", href: "/dashboard/profile"}],
    },
];

export default function HelpPage() {
    const [isOpeningGuide, setIsOpeningGuide] = useState(false);
    const [guideError, setGuideError] = useState<string | null>(null);

    const handleOpenGuide = async () => {
        try {
            setIsOpeningGuide(true);
            setGuideError(null);

            const response = await fetch(
                `${API_BASE_URL}/api/help/administrative-assistant-user-guide`,
                {credentials: "include"},
            );
            if (!response.ok) {
                throw new Error(`HTTP ${response.status}: ${response.statusText}`);
            }

            const blob = await response.blob();
            const url = URL.createObjectURL(blob);
            window.open(url, "_blank", "noopener,noreferrer");
            setTimeout(() => URL.revokeObjectURL(url), 60_000);
        } catch (error) {
            console.error("Error opening Administrative Assistant User Guide:", error);
            setGuideError("The full guide could not be opened. Please try again.");
        } finally {
            setIsOpeningGuide(false);
        }
    };

    return (
        <div className="px-4 sm:px-0">
            <div className="mb-8">
                <h1 className="text-3xl font-bold text-gray-900">Help</h1>
                <p className="mt-2 text-gray-600">
                    Choose what you want to do, then open the right area of Clerk.
                </p>
            </div>

            <section className="mb-6 overflow-hidden rounded-lg bg-white shadow">
                <div className="border-b border-gray-200 px-6 py-4">
                    <h2 className="text-xl font-semibold text-gray-900">What do you want to do?</h2>
                </div>
                <ul className="divide-y divide-gray-200">
                    {tasks.map((item) => (
                        <li key={item.task} className="px-6 py-4 sm:flex sm:items-center sm:justify-between sm:gap-6">
                            <div>
                                <p className="font-medium text-gray-900">{item.task}</p>
                                {item.note && <p className="mt-1 text-sm text-gray-600">{item.note}</p>}
                            </div>
                            <div className="mt-3 flex flex-wrap gap-2 sm:mt-0 sm:flex-shrink-0">
                                {item.links.map((link) => (
                                    <Link
                                        key={link.href}
                                        href={link.href}
                                        className="inline-flex items-center rounded-md bg-blue-600 px-3 py-2 text-sm font-medium text-white hover:bg-blue-700"
                                    >
                                        {link.label}
                                    </Link>
                                ))}
                            </div>
                        </li>
                    ))}
                </ul>
            </section>

            <section className="rounded-lg bg-white p-6 shadow">
                <h2 className="text-xl font-semibold text-gray-900">Detailed and Printable Guide</h2>
                <p className="mt-2 text-gray-600">
                    Open the complete Administrative Assistant User Guide for detailed instructions or printing.
                </p>
                {guideError && (
                    <div className="mt-4 rounded-md border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
                        {guideError}
                    </div>
                )}
                <button
                    type="button"
                    onClick={handleOpenGuide}
                    disabled={isOpeningGuide}
                    className="mt-4 inline-flex items-center gap-2 rounded-md bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700 disabled:opacity-50"
                >
                    {isOpeningGuide ? (
                        <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true"/>
                    ) : (
                        <ExternalLink className="h-4 w-4" aria-hidden="true"/>
                    )}
                    {isOpeningGuide ? "Opening Guide..." : "Open Full Guide"}
                </button>
            </section>
        </div>
    );
}
