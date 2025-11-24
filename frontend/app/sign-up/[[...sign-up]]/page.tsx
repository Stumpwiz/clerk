import { SignUp } from "@clerk/nextjs";
import Link from "next/link";

const FALLBACK_REDIRECT = process.env.NEXT_PUBLIC_CLERK_FALLBACK_REDIRECT_URL || "/dashboard";
const FORCE_REDIRECT = process.env.NEXT_PUBLIC_CLERK_FORCE_REDIRECT_URL;

export default function SignUpPage() {
  return (
    <div className="min-h-screen flex items-center justify-center bg-gray-50 p-4">
      <div className="w-full max-w-md">
        <SignUp
          fallbackRedirectUrl={FALLBACK_REDIRECT}
          signInUrl="/sign-in"
          {...(FORCE_REDIRECT ? { forceRedirectUrl: FORCE_REDIRECT } : {})}
        />
        <div className="mt-4 text-center text-sm text-gray-600">
          <p className="mb-2">
            💡 <strong>Note:</strong> If you already have an account, please{" "}
            <Link href="/sign-in" className="text-blue-600 hover:underline">
              sign in
            </Link>{" "}
            instead.
          </p>
          <p className="text-xs text-gray-500">
            Accepting an invitation? Make sure you&apos;re logged out first or use a private/incognito window.
          </p>
        </div>
      </div>
    </div>
  );
}
