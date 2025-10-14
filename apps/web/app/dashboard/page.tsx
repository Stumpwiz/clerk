import { auth } from "@clerk/nextjs/server";
import { redirect } from "next/navigation";
import { DashboardHeader } from "../components/dashboard-header";
import { ApiTest } from "../components/api-test";
import { AuthTest } from "@/app/components/auth-test";

export default async function DashboardPage() {
  const { userId } = await auth();

  if (!userId) {
    redirect("/sign-in");
  }

  return (
    <div className="min-h-screen bg-gray-50">
      <DashboardHeader />

      <main className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8 py-8">
        <div className="space-y-6 mb-8">
          <ApiTest />
          <AuthTest />
        </div>

        <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-6">
          {/* User Management card */}
          <a
            href="/users"
            className="bg-white rounded-lg shadow-md p-6 hover:shadow-lg transition-shadow"
          >
            <h2 className="text-xl font-semibold text-gray-900 mb-2">
              👥 User Management
            </h2>
            <p className="text-gray-600">
              Manage authorized users and roles (Admin only)
            </p>
          </a>

          {/* Existing cards */}
          <a
            href="/letters"
            className="bg-purple-50 rounded-lg shadow-md p-6 hover:bg-purple-100 transition"
          >
            <h2 className="text-xl font-semibold text-purple-600 mb-2">
              ✉️ Letters
            </h2>
            <p className="text-gray-600">
              Generate welcome letters with LaTeX templates
            </p>
          </a>
  
          <div className="bg-white rounded-lg shadow-md p-6">
            <h2 className="text-xl font-semibold text-gray-900 mb-2">
              Rosters
            </h2>
            <p className="text-gray-600">
              Manage committee rosters and memberships
            </p>
          </div>
  
          <div className="bg-white rounded-lg shadow-md p-6">
            <h2 className="text-xl font-semibold text-gray-900 mb-2">
              Reports
            </h2>
            <p className="text-gray-600">
              View vacancy and expiring term reports
            </p>
          </div>
        </div>
      </main>
    </div>
  );
}
