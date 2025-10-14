import { auth } from "@clerk/nextjs/server";
import { redirect } from "next/navigation";
import { UserManagement } from "@/app/components/user-management";

export default async function UsersPage() {
  const { userId } = await auth();

  if (!userId) {
    redirect("/sign-in");
  }

  return (
    <div className="min-h-screen bg-gray-50">
      <div className="max-w-7xl mx-auto py-8 px-4 sm:px-6 lg:px-8">
        <div className="mb-8">
          <h1 className="text-3xl font-bold text-gray-900">User Management</h1>
          <p className="mt-2 text-sm text-gray-600">
            Manage authorized users and their roles. Only users listed here can access the application.
          </p>
        </div>
        
        <UserManagement />
      </div>
    </div>
  );
}
