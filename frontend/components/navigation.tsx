"use client";

import Link from "next/link";
import Image from "next/image";
import {usePathname} from "next/navigation";
import {UserButton} from "@clerk/nextjs";
import {Home, Users, Briefcase, UserCircle, Calendar, FileText, BarChart3, UsersRound} from "lucide-react";

const navItems = [
    {href: "/dashboard", label: "Dashboard", icon: Home},
    {href: "/dashboard/bodies", label: "Bodies", icon: Briefcase},
    {href: "/dashboard/offices", label: "Offices", icon: Users},
    {href: "/dashboard/persons", label: "Persons", icon: UserCircle},
    {href: "/dashboard/terms", label: "Terms", icon: Calendar},
    {href: "/dashboard/letters", label: "Letters", icon: FileText},
    {href: "/dashboard/reports", label: "Reports", icon: BarChart3},
    {href: "/dashboard/users", label: "Users", icon: UsersRound},
];

export function Navigation() {
    const pathname = usePathname();

    return (
        <nav className="bg-white border-b border-gray-200">
            <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
                <div className="flex justify-between h-16">
                    <div className="flex">
                        <div className="flex-shrink-0 flex items-center">
                            <Link href="/dashboard" className="flex items-center gap-2">
                                <Image
                                    src="/logo.svg"
                                    alt="Clerk Logo"
                                    width={32}
                                    height={32}
                                    className="h-8 w-8"
                                />
                                <span className="text-xl font-bold text-blue-600">Clerk</span>
                            </Link>
                        </div>
                        <div className="hidden sm:ml-6 sm:flex sm:space-x-8">
                            {navItems.map((item) => {
                                const Icon = item.icon;
                                const isActive = pathname === item.href;
                                return (
                                    <Link
                                        key={item.href}
                                        href={item.href}
                                        className={`inline-flex items-center px-1 pt-1 border-b-2 text-sm font-medium ${
                                            isActive
                                                ? "border-blue-500 text-gray-900"
                                                : "border-transparent text-gray-500 hover:border-gray-300 hover:text-gray-700"
                                        }`}
                                    >
                                        <Icon className="w-4 h-4 mr-2"/>
                                        {item.label}
                                    </Link>
                                );
                            })}
                        </div>
                    </div>
                    <div className="flex items-center">
                        <UserButton
                            appearance={{
                                elements: {
                                    avatarBox: "h-10 w-10"
                                }
                            }}
                            afterSignOutUrl="/sign-in"
                            userProfileMode="navigation"
                            userProfileUrl="/dashboard/profile"
                        />
                    </div>
                </div>
            </div>
        </nav>
    );
}
