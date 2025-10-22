import { auth } from "@clerk/nextjs/server";

const API_PUBLIC_BASE =
  process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000";
// Prefer internal base when available (e.g., in Docker/ECS)
const API_INTERNAL_BASE = process.env.API_INTERNAL_BASE_URL || API_PUBLIC_BASE;

export interface ApiError {
  message: string;
  status: number;
}

/**
 * Server-side API client for authenticated requests to FastAPI.
 * Use this in Server Components, Route Handlers, and Server Actions.
 */
export async function apiClient<T>(
  endpoint: string,
  options: RequestInit = {}
): Promise<T> {
  const { getToken } = await auth();
  const token = await getToken();

  // Build headers from any incoming headers and ensure defaults
  const headers = new Headers(options.headers as HeadersInit);
  if (!headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json");
  }
  if (token) {
    headers.set("Authorization", `Bearer ${token}`);
  }

  const url = `${API_INTERNAL_BASE}${endpoint.startsWith("/") ? "" : "/"}${endpoint}`;

  const res = await fetch(url, {
    ...options,
    headers,
  });

  const contentType = res.headers.get("content-type") || "";

  if (!res.ok) {
    // Try to surface JSON error body
    let msg = res.statusText || `API Error`;
    if (contentType.includes("application/json")) {
      try {
        const j = await res.json();
        msg = j?.error || j?.message || j?.detail || msg;
      } catch {
        // ignore JSON parse error
      }
    } else {
      try {
        const t = await res.text();
        msg = t?.trim() || msg;
      } catch {
        // ignore
      }
    }
    const error: ApiError = { message: msg, status: res.status };
    throw error;
  }

  // 204 No Content
  if (res.status === 204) {
    return undefined as unknown as T;
  }

  if (contentType.includes("application/json")) {
    return (await res.json()) as T;
  }

  // Fallback: return text if non-JSON
  return (await res.text()) as unknown as T;
}
