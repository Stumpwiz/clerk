import { auth } from "@clerk/nextjs/server";
import { NextRequest, NextResponse } from "next/server";

// Prefer internal URL when running server-side (e.g., in Docker), fall back to public, then localhost
const API_PUBLIC_BASE = process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000";
const API_INTERNAL_BASE = process.env.API_INTERNAL_BASE_URL || API_PUBLIC_BASE;

export async function GET(
  request: NextRequest,
  context: { params: Promise<{ path: string[] }> }
) {
  const params = await context.params;
  return handleRequest(request, params, "GET");
}

export async function POST(
  request: NextRequest,
  context: { params: Promise<{ path: string[] }> }
) {
  const params = await context.params;
  return handleRequest(request, params, "POST");
}

export async function PUT(
  request: NextRequest,
  context: { params: Promise<{ path: string[] }> }
) {
  const params = await context.params;
  return handleRequest(request, params, "PUT");
}

export async function DELETE(
  request: NextRequest,
  context: { params: Promise<{ path: string[] }> }
) {
  const params = await context.params;
  return handleRequest(request, params, "DELETE");
}

export async function PATCH(
  request: NextRequest,
  context: { params: Promise<{ path: string[] }> }
) {
  const params = await context.params;
  return handleRequest(request, params, "PATCH");
}

async function handleRequest(
  request: NextRequest,
  params: { path: string[] },
  method: string
) {
  try {
    // Join path segments, default to empty string if no path
    const path = params.path?.join("/") || "";

    // Allow unauthenticated passthrough for public endpoints (health checks)
    const unauthAllowed = path === "health" || path === "health/";

    let token: string | null = null;
    if (!unauthAllowed) {
      const authResult = await auth();
      token = await authResult.getToken({ template: "Default" });

      if (!token) {
        return NextResponse.json(
          { error: "Unauthorized" },
          { status: 401 }
        );
      }
    }

    // Preserve the query string from the original request
    const search = request.nextUrl?.search || "";

    // Add /api prefix for FastAPI routes (except bare health check)
    let apiPath = (path === "health" || path === "health/") ? path : `api/${path}`;

    // FastAPI requires trailing slashes for most endpoints
    // Add trailing slash if not already present and not health endpoint
    if (path !== "health" && path !== "health/" && !apiPath.endsWith('/')) {
      apiPath += '/';
    }

    const url = `${API_INTERNAL_BASE}/${apiPath}${search}`;

    console.log(`[API Proxy] ${method} -> ${url}`);

    const headers: HeadersInit = {
      "Content-Type": "application/json",
    };
    if (token) {
      (headers as any).Authorization = `Bearer ${token}`;
    }

    let body: string | undefined;
    if (["POST", "PUT", "PATCH"].includes(method)) {
      body = await request.text();
    }

    const response = await fetch(url, {
      method,
      headers,
      body,
    });

    // Handle 204 No Content - no body to parse
    if (response.status === 204) {
      return new NextResponse(null, { status: 204 });
    }

    // Check content type
    const contentType = response.headers.get('content-type') || '';

    // Handle PDF and other binary responses
    if (
      contentType.includes('application/pdf') ||
      contentType.includes('image/') ||
      contentType.includes('application/octet-stream')
    ) {
      const blob = await response.blob();
      return new Response(blob, {
        status: response.status,
        headers: {
          'Content-Type': contentType,
          'Content-Disposition': response.headers.get('content-disposition') || 'inline',
        },
      });
    }

    // Return JSON when JSON, otherwise return text
    if (contentType.includes('application/json')) {
      const data = await response.json();
      return Response.json(data, {
        status: response.status,
        headers: {},
      });
    } else {
      const text = await response.text();
      return new Response(text, {
        status: response.status,
        headers: { 'Content-Type': contentType || 'text/plain; charset=utf-8' },
      });
    }
  } catch (error) {
    console.error("[API Proxy Error]:", error);
    return NextResponse.json(
      { error: "Internal Server Error", details: String(error) },
      { status: 500 }
    );
  }
}