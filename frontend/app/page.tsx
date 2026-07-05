"use client";

import {useEffect} from "react";
import {useRouter} from "next/navigation";
import {Loader2} from "lucide-react";
import {getCurrentUser} from "@/lib/auth";

export default function Home() {
    const router = useRouter();

    useEffect(() => {
        let isMounted = true;

        async function routeBySession() {
            const currentUser = await getCurrentUser();
            if (!isMounted) return;

            router.replace(currentUser ? "/dashboard" : "/local-login");
        }

        routeBySession();

        return () => {
            isMounted = false;
        };
    }, [router]);

    return (
        <main className="min-h-screen bg-gray-50">
            <div className="flex h-screen items-center justify-center">
                <Loader2 className="h-8 w-8 animate-spin text-blue-600"/>
            </div>
        </main>
    );
}
