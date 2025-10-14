"use client";

import { useState } from "react";
import { clientApiCall } from "@/lib/client-api";

interface UserInfo {
  user_id: string;
  email: string;
  username: string;
  role: string;
}

export function AuthTest() {
  const [userInfo, setUserInfo] = useState<UserInfo | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string>("");

  const testAuthorization = async () => {
    setLoading(true);
    setError("");
    setUserInfo(null);

    try {
      const data = await clientApiCall<UserInfo>("/api/v1/auth/me");
      setUserInfo(data);
    } catch (err: any) {
      // Build a helpful error including status code if available
      const status = err?.status ? ` (${err.status})` : "";
      setError((err?.message || "Failed to fetch user info") + status);
      console.error("Authorization test error:", err);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="rounded-lg bg-white p-6 shadow">
      <h3 className="text-lg font-semibold text-gray-900 mb-4">
        Authorization Test
      </h3>
      
      <p className="text-sm text-gray-600 mb-4">
        Test the new authorization system. This verifies that:
      </p>
      <ul className="text-sm text-gray-600 mb-4 list-disc list-inside space-y-1">
        <li>Your Clerk JWT is valid (authentication)</li>
        <li>Your email exists in the users table (authorization)</li>
        <li>Your role is correctly retrieved from the database</li>
      </ul>

      <button
        onClick={testAuthorization}
        disabled={loading}
        className="rounded-lg bg-indigo-600 px-4 py-2 text-white font-semibold hover:bg-indigo-700 transition disabled:opacity-50 disabled:cursor-not-allowed"
      >
        {loading ? "Testing Authorization..." : "Test Authorization"}
      </button>

      {/* Success state */}
      {userInfo && (
        <div className="mt-4 bg-green-50 border border-green-200 rounded-lg p-4">
          <p className="text-sm font-semibold text-green-800 mb-3">
            ✅ Authorization Successful
          </p>
          <dl className="space-y-2">
            <div>
              <dt className="text-xs font-medium text-green-700">Email:</dt>
              <dd className="text-sm text-green-900">{userInfo.email}</dd>
            </div>
            <div>
              <dt className="text-xs font-medium text-green-700">Username:</dt>
              <dd className="text-sm text-green-900">{userInfo.username}</dd>
            </div>
            <div>
              <dt className="text-xs font-medium text-green-700">Role:</dt>
              <dd className="text-sm text-green-900">
                <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${
                  userInfo.role === 'admin' 
                    ? 'bg-purple-100 text-purple-800' 
                    : 'bg-blue-100 text-blue-800'
                }`}>
                  {userInfo.role.toUpperCase()}
                </span>
              </dd>
            </div>
            <div>
              <dt className="text-xs font-medium text-green-700">Clerk User ID:</dt>
              <dd className="text-sm text-green-900 font-mono text-xs break-all">
                {userInfo.user_id}
              </dd>
            </div>
          </dl>
        </div>
      )}

      {/* Error state */}
      {error && (
        <div className="mt-4 bg-red-50 border border-red-200 rounded-lg p-4">
          <p className="text-sm font-semibold text-red-800 mb-2">
            ❌ Authorization Failed
          </p>
          <p className="text-sm text-red-700">{error}</p>
          
          {error.includes("403") && (
            <div className="mt-3 text-xs text-red-600">
              <p className="font-medium">Possible reasons:</p>
              <ul className="list-disc list-inside mt-1 space-y-1">
                <li>Your email is not in the users table</li>
                <li>Contact an administrator to request access</li>
              </ul>
            </div>
          )}
          
          {error.includes("401") && (
            <div className="mt-3 text-xs text-red-600">
              <p className="font-medium">Possible reasons:</p>
              <ul className="list-disc list-inside mt-1 space-y-1">
                <li>Your Clerk session has expired</li>
                <li>Try signing out and signing back in</li>
              </ul>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
