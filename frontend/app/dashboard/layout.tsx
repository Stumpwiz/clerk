import {AuthenticatedShell} from "@/components/authenticated-shell";

// Force dynamic rendering for all dashboard pages
export const dynamic = 'force-dynamic';

export default function DashboardLayout({
                                            children,
                                        }: {
    children: React.ReactNode;
}) {
    return (
        <AuthenticatedShell>
            {children}
        </AuthenticatedShell>
    );
}
