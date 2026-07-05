// lib/auth.ts - Local authentication service boundary

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL ?? "";

export interface LocalUser {
    id: number;
    email: string;
    display_name: string;
    avatar_path: string | null;
    is_active: boolean;
    last_login_at: string | null;
}

export interface LoginResult {
    user: LocalUser;
}

interface ApiError {
    detail?: string;
}

async function parseError(response: Response): Promise<string> {
    const error = await response.json().catch(() => null) as ApiError | null;
    return error?.detail || `HTTP ${response.status}`;
}

export async function login(email: string, password: string): Promise<LoginResult> {
    const response = await fetch(`${API_BASE_URL}/api/auth/login`, {
        method: "POST",
        headers: {
            "Content-Type": "application/json",
        },
        credentials: "include",
        body: JSON.stringify({email, password}),
    });

    if (!response.ok) {
        throw new Error(await parseError(response));
    }

    return response.json() as Promise<LoginResult>;
}

export async function logout(): Promise<void> {
    const response = await fetch(`${API_BASE_URL}/api/auth/logout`, {
        method: "POST",
        credentials: "include",
    });

    if (!response.ok) {
        throw new Error(await parseError(response));
    }
}

export async function getCurrentUser(): Promise<LocalUser | null> {
    const response = await fetch(`${API_BASE_URL}/api/auth/me`, {
        method: "GET",
        credentials: "include",
        cache: "no-store",
    });

    if (response.status === 401) {
        return null;
    }

    if (!response.ok) {
        throw new Error(await parseError(response));
    }

    return response.json() as Promise<LocalUser>;
}
