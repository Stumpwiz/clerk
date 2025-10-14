"use client";

import { UserButton } from "@clerk/nextjs";

export function DashboardHeader() {
  return (
    <nav className="bg-white shadow-sm">
      <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
        <div className="flex h-16 justify-between items-center">
          <h1 className="text-xl font-semibold text-gray-900">
            Community Admin Dashboard
          </h1>
          <UserButton afterSignOutUrl="/" />
        </div>
      </div>
    </nav>
  );
}
