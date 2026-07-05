"use client";

import Link from "next/link";
import Image from "next/image";
import {usePathname} from "next/navigation";
import {LocalUserMenu} from "@/components/local-user-menu";
import type {LocalUser} from "@/lib/auth";
import {Home, Users, Briefcase, UserCircle, Calendar, FileText, BarChart3, UsersRound, Mail} from "lucide-react";

const navItems = [
    {href: "/dashboard", label: "Dashboard", icon: Home},
    {href: "/dashboard/bodies", label: "Bodies", icon: Briefcase},
    {href: "/dashboard/offices", label: "Offices", icon: Users},
    {href: "/dashboard/persons", label: "Persons", icon: UserCircle},
    {href: "/dashboard/terms", label: "Terms", icon: Calendar},
    {href: "/dashboard/letters", label: "Letters", icon: FileText},
    {href: "/dashboard/reports", label: "Rosters & Reports", icon: BarChart3},
    {href: "/dashboard/mailing-lists", label: "Mailing Lists", icon: Mail},
    {href: "/dashboard/users", label: "Users", icon: UsersRound},
];

interface NavigationProps {
    user: LocalUser;
}

export function Navigation({user}: NavigationProps) {
    const pathname = usePathname();

    return (
        <nav className="border-b border-gray-200 bg-white shadow-sm">
            <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
                <div className="flex flex-col gap-3 py-3">
                    <div className="flex min-w-0 items-center justify-between gap-4">
                        <Link href="/dashboard" className="flex flex-shrink-0 items-center gap-2">
                            <span className="flex h-9 w-9 flex-shrink-0 items-center justify-center rounded-md border border-blue-100 bg-blue-50">
                                <Image
                                    src="/logo.svg"
                                    alt="Application logo"
                                    width={28}
                                    height={28}
                                    className="h-7 w-7"
                                />
                            </span>
                            <span className="whitespace-nowrap text-lg font-semibold tracking-normal text-gray-950">
                                Community Admin
                            </span>
                        </Link>
                        <div className="flex min-w-0 items-center justify-end">
                            <LocalUserMenu user={user} variant="compact"/>
                        </div>
                    </div>

                    <div className="flex min-w-0 flex-nowrap gap-1 overflow-x-auto pb-1 md:flex-wrap md:overflow-visible md:pb-0">
                        {navItems.map((item) => {
                            const Icon = item.icon;
                            const isActive = pathname === item.href;
                            return (
                                <Link
                                    key={item.href}
                                    href={item.href}
                                    className={`inline-flex flex-shrink-0 items-center gap-2 rounded-md px-3 py-2 text-sm font-medium transition ${
                                        isActive
                                            ? "bg-blue-50 text-blue-700"
                                            : "text-gray-600 hover:bg-gray-50 hover:text-gray-900"
                                    }`}
                                >
                                    <Icon className="h-4 w-4"/>
                                    {item.label}
                                </Link>
                            );
                        })}
                    </div>
                </div>
            </div>
        </nav>
    );
}
