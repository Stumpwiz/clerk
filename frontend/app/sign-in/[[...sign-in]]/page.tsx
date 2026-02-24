import { SignIn } from "@clerk/nextjs";

const FALLBACK_REDIRECT = process.env.NEXT_PUBLIC_CLERK_FALLBACK_REDIRECT_URL || "/dashboard";
const FORCE_REDIRECT = process.env.NEXT_PUBLIC_CLERK_FORCE_REDIRECT_URL;

export default function SignInPage() {
  return (
    <div className="min-h-screen flex items-center justify-center bg-gray-50">
      <SignIn
        fallbackRedirectUrl={FALLBACK_REDIRECT}
        {...(FORCE_REDIRECT ? { forceRedirectUrl: FORCE_REDIRECT } : {})}
      />
    </div>
  );
}
