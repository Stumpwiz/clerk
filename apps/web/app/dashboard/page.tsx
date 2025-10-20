import { auth } from "@clerk/nextjs/server";
import { redirect } from "next/navigation";
import { DashboardHeader } from "../components/dashboard-header";
import { ApiTest } from "../components/api-test";
import { AuthTest } from "@/app/components/auth-test";
import AdminUsersCard from "./AdminUsersCard";

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
          {/* Row 1 */}
          <a
            href="/letters"
            className="bg-purple-50 rounded-lg shadow-md p-6 hover:bg-purple-100 transition"
          >
            <h2 className="text-xl font-semibold text-purple-600 mb-2">✉️ Letters</h2>
            <p className="text-gray-600">Generate welcome letters with LaTeX templates</p>
          </a>

          <a
            href="/terms"
            className="bg-green-50 rounded-lg shadow-md p-6 hover:bg-green-100 transition"
          >
            <h2 className="text-xl font-semibold text-green-600 mb-2">Terms</h2>
            <p className="text-gray-600">Assign people to offices and manage term dates</p>
          </a>

          <a
            href="/rosters"
            className="bg-indigo-50 rounded-lg shadow-md p-6 hover:bg-indigo-100 transition"
          >
            <h2 className="text-xl font-semibold text-indigo-600 mb-2">Rosters</h2>
            <p className="text-gray-600">Manage committee rosters and memberships</p>
          </a>

          {/* Row 2 */}
          <a
            href="/people"
            className="bg-teal-50 rounded-lg shadow-md p-6 hover:bg-teal-100 transition"
          >
            <h2 className="text-xl font-semibold text-teal-600 mb-2">People</h2>
            <p className="text-gray-600">Manage community members</p>
          </a>

          <a
            href="/reports"
            className="bg-blue-50 rounded-lg shadow-md p-6 hover:bg-blue-100 transition"
          >
            <h2 className="text-xl font-semibold text-blue-600 mb-2">Reports</h2>
            <p className="text-gray-600">View vacancy and expiring term reports</p>
          </a>

          <a
            href="/bodies-offices"
            className="bg-amber-50 rounded-lg shadow-md p-6 hover:bg-amber-100 transition"
          >
            <h2 className="text-xl font-semibold text-amber-600 mb-2">Bodies & Offices</h2>
            <p className="text-gray-600">Manage bodies and offices</p>
          </a>

          {/* Row 3 (admin only) */}
          <AdminUsersCard />
        </div>
      </main>
    </div>
  );
}
