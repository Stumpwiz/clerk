import { auth } from "@clerk/nextjs/server";
import { NextRequest, NextResponse } from "next/server";

const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000";

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
    const authResult = await auth();
    const token = await authResult.getToken({ template: "Default" });

    if (!token) {
      return NextResponse.json(
        { error: "Unauthorized" },
        { status: 401 }
      );
    }

    // Join path segments, default to empty string if no path
    const path = params.path?.join("/") || "";

    // Preserve the query string from the original request
    const search = request.nextUrl?.search || "";

    const url = `${API_BASE_URL}/${path}${search}`;

    console.log(`[API Proxy] ${method} -> ${url}`);

    const headers: HeadersInit = {
      "Content-Type": "application/json",
      Authorization: `Bearer ${token}`,
    };

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

    // For JSON responses
    const data = await response.json();
    return Response.json(data, {
      status: response.status,
      headers: {},
    });
  } catch (error) {
    console.error("[API Proxy Error]:", error);
    return NextResponse.json(
      { error: "Internal Server Error", details: String(error) },
      { status: 500 }
    );
  }
}