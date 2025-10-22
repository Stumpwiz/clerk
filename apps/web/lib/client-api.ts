export interface ApiError {
  message: string;
  status: number;
}

/**
 * Client-side API client for authenticated requests
 * Use this in Client Components
 * Calls through Next.js API proxy which adds authentication
 */
export async function clientApiCall<T = any>(
  endpoint: string,
  options: RequestInit = {}
): Promise<T> {
  // Ensure endpoint starts with /
  const path = endpoint.startsWith("/") ? endpoint : `/${endpoint}`;
  const url = `/api/proxy${path}`;

  const response = await fetch(url, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      ...options.headers,
    },
  });

  // Handle 204 No Content - no body to parse
  if (response.status === 204) {
    return undefined as T;
  }

  let data: any = null;
  try {
    data = await response.json();
  } catch (e) {
    // If response isn't JSON and it's an error, construct a proper message
    if (!response.ok) {
      const error: ApiError = {
        message: `API Error: ${response.statusText}`,
        status: response.status,
      };
      throw Object.assign(new Error(error.message), { status: error.status });
    }
    // Otherwise, return a text message wrapper
    const text = await response.text().catch(() => "");
    return ({ message: text } as unknown) as T;
  }

  if (!response.ok) {
    const errorMessage = data?.detail || data?.message || `API request failed`;
    const err: any = new Error(errorMessage);
    err.status = response.status;
    throw err;
  }

  return data as T;
}

// Letter Template Types
export interface LetterTemplate {
  id: number;
  header: string;
  body: string;
}
// Lightweight client-side API helper for browser components.
// It prefixes requests with the internal API proxy route (/api/proxy)
// so that Clerk auth is applied server-side before hitting the FastAPI backend.

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
  const normalizedPath = path.startsWith("/") ? path : `/${path}`;
  const url = `/api/proxy${normalizedPath}`;

  const mergedHeaders: HeadersInit = {
    "Content-Type": "application/json",
    ...(init?.headers || {}),
  };

  const res = await fetch(url, {
    ...init,
    headers: mergedHeaders,
  });

  // 204 No Content
  if (res.status === 204) {
    return undefined as unknown as T;
  }

  // Content-Type to decide how to parse
  const contentType = res.headers.get("content-type") || "";

  // Try to parse JSON when possible
  if (contentType.includes("application/json")) {
    const data = await res.json().catch(() => null);
    if (!res.ok) {
      const errShape = (data || {}) as JsonErrorShape;
      const msg =
        errShape.error ||
        errShape.message ||
        errShape.detail ||
        `Request failed with status ${res.status}`;
      throw new Error(msg);
    }
    return data as T;
  }

  // Non-JSON responses: read as text for error context
  const text = await res.text().catch(() => "");
  if (!res.ok) {
    const msg =
      text?.trim() ||
      `Request failed with status ${res.status}`;
    throw new Error(msg);
  }

  // @ts-expect-error returning text for non-JSON callers if needed
  return text as T;
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
    clientApiCall<LetterTemplate>("/api/v1/letters/template"),
  
  updateTemplate: (data: Omit<LetterTemplate, "id">) =>
    clientApiCall<LetterTemplate>("/api/v1/letters/template", {
      method: "PUT",
      body: JSON.stringify(data),
    }),
  
  generate: (data: LetterGenerateRequest) =>
    clientApiCall<LetterGenerateResponse>("/api/v1/letters/generate", {
      method: "POST",
      body: JSON.stringify(data),
    }),
  
  listPDFs: () =>
    clientApiCall<PDFListItem[]>("/api/v1/letters/pdfs"),
  
  deletePDF: (filename: string) =>
    clientApiCall<{ success: boolean }>(`/api/v1/letters/pdfs/${filename}`, {
      method: "DELETE",
    }),
  
  getPDFUrl: (filename: string) =>
    `/api/proxy/api/v1/letters/pdfs/${encodeURIComponent(filename)}`,
};
