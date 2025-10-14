import { auth } from "@clerk/nextjs/server";
import { redirect } from "next/navigation";
import Link from "next/link";

export default async function HomePage() {
  const { userId } = await auth();

  if (userId) {
    redirect("/dashboard");
  }

  return (
    <div className="flex min-h-screen flex-col items-center justify-center bg-gray-50">
      <div className="text-center">
        <h1 className="text-4xl font-bold text-gray-900 mb-4">
          Community Admin
        </h1>
        <p className="text-lg text-gray-600 mb-8">
          Retirement community administrative functions
        </p>
        <div className="space-x-4">
          <Link
            href="/sign-in"
            className="inline-block rounded-lg bg-blue-600 px-6 py-3 text-white font-semibold hover:bg-blue-700 transition"
          >
            Sign In
          </Link>
          <Link
            href="/sign-up"
            className="inline-block rounded-lg bg-gray-200 px-6 py-3 text-gray-900 font-semibold hover:bg-gray-300 transition"
          >
            Sign Up
          </Link>
        </div>
      </div>
    </div>
  );
}
