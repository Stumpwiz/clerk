"use client";

import { useState } from "react";
import { clientApiCall } from "@/lib/client-api";

export function ApiTest() {
  // Health check states
  const [healthResponse, setHealthResponse] = useState<string>("");
  const [healthLoading, setHealthLoading] = useState(false);
  const [healthError, setHealthError] = useState<string>("");

  // Protected /me states
  const [meResponse, setMeResponse] = useState<Record<string, any> | null>(null);
  const [meLoading, setMeLoading] = useState(false);
  const [meError, setMeError] = useState<string>("");

  const testHealth = async () => {
    setHealthLoading(true);
    setHealthError("");
    setHealthResponse("");

    try {
      const data = await clientApiCall<{ status: string }>("/health");
      setHealthResponse(JSON.stringify(data, null, 2));
    } catch (err: any) {
      setHealthError(err.message || "Failed to connect to API");
    } finally {
      setHealthLoading(false);
    }
  };

  const testProtected = async () => {
    setMeLoading(true);
    setMeError("");
    setMeResponse(null);

    try {
      const data = await clientApiCall<{
        user_id: string;
        email?: string | null;
        email_verified?: boolean | null;
        first_name?: string | null;
        last_name?: string | null;
        full_name?: string | null;
      }>("/api/v1/me");
      console.log("/api/v1/me response:", data);
      console.log("About to set meResponse:", data);
      console.log("Keys:", Object.keys(data));
      setMeResponse(data as Record<string, any>);
    } catch (err: any) {
      console.error("/api/v1/me error:", err);
      setMeError(err?.message || "Failed to access protected endpoint");
    } finally {
      setMeLoading(false);
    }
  };

  const anyLoading = healthLoading || meLoading;

  return (
    <div className="rounded-lg bg-white p-6 shadow">
      <h3 className="text-lg font-semibold text-gray-900 mb-4">
        API Connection Test
      </h3>

      <div className="flex flex-wrap gap-3">
        <button
          onClick={testHealth}
          disabled={anyLoading}
          className="rounded-lg bg-blue-600 px-4 py-2 text-white font-semibold hover:bg-blue-700 transition disabled:opacity-50"
        >
          {healthLoading ? "Testing..." : "Test Health (/health)"}
        </button>

        <button
          onClick={testProtected}
          disabled={anyLoading}
          className="rounded-lg bg-emerald-600 px-4 py-2 text-white font-semibold hover:bg-emerald-700 transition disabled:opacity-50"
        >
          {meLoading ? "Testing..." : "Test Protected Endpoint (/me)"}
        </button>
      </div>

      {/* Health result */}
      {healthResponse && (
        <div className="mt-4">
          <p className="text-sm font-medium text-green-600 mb-2">✅ Success - Health check</p>
          <pre className="bg-gray-100 p-3 rounded text-sm overflow-auto text-gray-900">
            {healthResponse}
          </pre>
        </div>
      )}
      {healthError && (
        <div className="mt-4">
          <p className="text-sm font-medium text-red-600 mb-2">❌ Error (Health):</p>
          <p className="bg-red-50 p-3 rounded text-sm text-red-700">
            {healthError}
          </p>
        </div>
      )}

      {/* Protected /me result */}
      {meResponse && (
        <div className="mt-4">
          <p className="text-sm font-medium text-green-600 mb-2">✅ Success - Protected /me</p>
          <pre className="bg-gray-100 p-3 rounded text-sm overflow-auto text-gray-900">
            {JSON.stringify(meResponse, null, 2)}
          </pre>
        </div>
      )}
      {meError && (
        <div className="mt-4">
          <p className="text-sm font-medium text-red-600 mb-2">❌ Error (Protected):</p>
          <p className="bg-red-50 p-3 rounded text-sm text-red-700">
            {meError}
          </p>
        </div>
      )}
    </div>
  );
}
