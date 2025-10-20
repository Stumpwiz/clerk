"use client";

import { useEffect, useState } from "react";
import { clientApiCall } from "@/lib/client-api";

export default function AdminUsersCard() {
  const [isAdmin, setIsAdmin] = useState<boolean>(false);
  const [checked, setChecked] = useState<boolean>(false);

  useEffect(() => {
    let cancelled = false;
    async function checkAdmin() {
      try {
        // Admin-only endpoint; if it succeeds, user is admin
        await clientApiCall("/api/v1/users");
        if (!cancelled) {
          setIsAdmin(true);
        }
      } catch {
        // Not admin or error; silently ignore
      } finally {
        if (!cancelled) setChecked(true);
      }
    }
    checkAdmin();
    return () => {
      cancelled = true;
    };
  }, []);

  if (!checked || !isAdmin) return null;

  return (
    <a
      href="/users"
      className="bg-rose-50 rounded-lg shadow-md p-6 hover:bg-rose-100 transition"
    >
      <h2 className="text-xl font-semibold text-rose-600 mb-2">👥 Users</h2>
      <p className="text-gray-600">Manage authorized users and roles (Admin only)</p>
    </a>
  );
}
