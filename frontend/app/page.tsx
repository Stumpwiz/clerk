import Link from "next/link";

export default function Home() {
    return (
        <div className="min-h-screen flex flex-col items-center justify-center p-8">
            <main className="max-w-2xl text-center">
                <h1 className="text-4xl font-bold mb-4">
                    Retirement Community Management System
                </h1>
                <p className="text-lg mb-8 text-gray-600">
                    Administrative tools for managing community bodies, offices, and personnel
                </p>

                <div className="flex gap-4 justify-center">
                    <Link
                        href="/dashboard"
                        className="px-6 py-3 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition"
                    >
                        Go to Dashboard
                    </Link>
                    <Link
                        href="/sign-in"
                        className="px-6 py-3 border border-gray-300 rounded-lg hover:bg-gray-50 transition"
                    >
                        Sign In
                    </Link>
                </div>
            </main>
        </div>
    );
}
