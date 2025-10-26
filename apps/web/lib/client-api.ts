// Client-side API helper for browser components.
// Routes requests through the Next.js proxy (/api/proxy) so Clerk auth is applied server-side
// before hitting the FastAPI backend.

export interface JsonErrorShape {
  error?: string;
  message?: string;
  detail?: string;
  [key: string]: unknown;
}

export async function clientApiCall<T = unknown>(
  path: string,
  init?: RequestInit
): Promise<T> {
  // Normalize path and strip leading /api if present to avoid double prefix
  let normalizedPath = path.startsWith("/") ? path : `/${path}`;
  if (normalizedPath.startsWith("/api/")) {
    normalizedPath = normalizedPath.substring(4); // Remove "/api"
  }
  const url = `/api/proxy${normalizedPath}`;

  const headers: HeadersInit = {
    "Content-Type": "application/json",
    ...(init?.headers || {}),
  };

  const res = await fetch(url, {
    ...init,
    headers,
  });

  // 204 No Content
  if (res.status === 204) {
    return undefined as unknown as T;
  }

  // Parse according to content-type
  const contentType = res.headers.get("content-type") || "";

  if (contentType.includes("application/json")) {
    const data = await res.json().catch(() => null);
    if (!res.ok) {
      const err = (data || {}) as JsonErrorShape;
      const msg =
        err.error ||
        err.message ||
        err.detail ||
        `Request failed with status ${res.status}`;
      throw new Error(msg);
    }
    return data as T;
  }

  // Non-JSON: treat as text for error context
  const text = await res.text().catch(() => "");
  if (!res.ok) {
    throw new Error(text?.trim() || `Request failed with status ${res.status}`);
  }

  return text as T;
}

// Letter Template Types
export interface LetterTemplate {
  id: number;
  header: string;
  body: string;
}

export interface LetterGenerateRequest {
  addressee: string;
  salutation: string;
  date: string;
  apartment: string;
}

export interface LetterGenerateResponse {
  success: boolean;
  filename?: string;
  error?: string;
}

export interface PDFListItem {
  filename: string;
  created: string;
  size: number;
}

// Letter Template API
export const letterApi = {
  getTemplate: () =>
    clientApiCall<LetterTemplate>("/v1/letters/template"),

  updateTemplate: (data: Omit<LetterTemplate, "id">) =>
    clientApiCall<LetterTemplate>("/v1/letters/template", {
      method: "PUT",
      body: JSON.stringify(data),
    }),

  generate: (data: LetterGenerateRequest) =>
    clientApiCall<LetterGenerateResponse>("/v1/letters/generate", {
      method: "POST",
      body: JSON.stringify(data),
    }),

  listPDFs: () => clientApiCall<PDFListItem[]>("/v1/letters/pdfs"),

  deletePDF: (filename: string) =>
    clientApiCall<{ success: boolean }>(
      `/v1/letters/pdfs/${encodeURIComponent(filename)}`,
      { method: "DELETE" }
    ),
  
  getPDFUrl: (filename: string) =>
    `/api/proxy/v1/letters/pdfs/${encodeURIComponent(filename)}`,
};
