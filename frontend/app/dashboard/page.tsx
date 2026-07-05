import Link from "next/link";
import {Briefcase, Users, UserCircle, Calendar, FileText, BarChart3, UsersRound, Settings, Mail} from "lucide-react";

const cards = [
    {
        title: "Bodies",
        description: "Manage administrative bodies and committees",
        href: "/dashboard/bodies",
        icon: Briefcase,
        color: "bg-blue-500",
    },
    {
        title: "Offices",
        description: "Manage committee positions and roles",
        href: "/dashboard/offices",
        icon: Users,
        color: "bg-green-500",
    },
    {
        title: "Persons",
        description: "Manage community members and residents",
        href: "/dashboard/persons",
        icon: UserCircle,
        color: "bg-purple-500",
    },
    {
        title: "Terms",
        description: "Manage person-office assignments",
        href: "/dashboard/terms",
        icon: Calendar,
        color: "bg-orange-500",
    },
    {
        title: "Letters",
        description: "Generate and manage welcome letters",
        href: "/dashboard/letters",
        icon: FileText,
        color: "bg-pink-500",
    },
    {
        title: "Rosters & Reports",
        description: "Generate rosters and reports from database",
        href: "/dashboard/reports",
        icon: BarChart3,
        color: "bg-indigo-500",
    },
    {
        title: "Mailing Lists",
        description: "Generate mailing lists from current terms",
        href: "/dashboard/mailing-lists",
        icon: Mail,
        color: "bg-cyan-600",
    },
  {
    title: "Users",
    description: "View local application users",
    href: "/dashboard/users",
    icon: UsersRound,
    color: "bg-teal-500",
  },
  {
    title: "My Profile",
    description: "Edit your profile and account settings",
    href: "/dashboard/profile",
    icon: Settings,
    color: "bg-gray-500",
  },
];

export default function DashboardPage() {
    return (
        <div className="px-4 sm:px-0">
            <div className="mb-8">
                <h1 className="text-3xl font-bold text-gray-900">Dashboard</h1>
                <p className="mt-2 text-gray-600">
                Welcome to the Community Administration System
                </p>
            </div>

            <div className="grid grid-cols-1 gap-6 sm:grid-cols-2 lg:grid-cols-4">
                {cards.map((card) => {
                    const Icon = card.icon;
                    return (
                        <Link
                            key={card.href}
                            href={card.href}
                            className="block p-6 bg-white border border-gray-200 rounded-lg shadow hover:shadow-lg transition"
                        >
                            <div className={`inline-flex p-3 rounded-lg ${card.color} text-white mb-4`}>
                                <Icon className="w-6 h-6"/>
                            </div>
                            <h2 className="text-xl font-semibold text-gray-900 mb-2">
                                {card.title}
                            </h2>
                            <p className="text-gray-600">{card.description}</p>
                        </Link>
                    );
                })}
            </div>
        </div>
    );
}
