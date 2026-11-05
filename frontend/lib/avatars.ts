import type {LocalUser} from "./auth";

export const AVATAR_FALLBACK = "/logo.svg";

export function validateAvatar(file: Pick<File, "size" | "type">): void {
    if (file.size > 2 * 1024 * 1024) throw new Error("Choose an image no larger than 2 MiB.");
    if (!["image/jpeg", "image/png", "image/webp"].includes(file.type)) {
        throw new Error("Choose a JPEG, PNG, or WebP image.");
    }
}

export function avatarUrl(path: string, base: string): string {
    // Only the backend's avatar route may receive credentialed requests.
    if (!/^\/api\/avatars\/\d+\/[a-f0-9]{32}\.png$/.test(path)) {
        throw new Error("Invalid avatar URL");
    }
    return base.replace(/\/$/, "") + path;
}

export function loadAvatar(
    path: string | null, base: string, publish: (url: string) => void,
    fetcher: typeof fetch = fetch, urls = URL,
): () => void {
    const controller = new AbortController();
    let active = true;
    let objectUrl: string | null = null;
    publish(AVATAR_FALLBACK);
    if (path) {
        void (async () => {
            try {
                const response = await fetcher(avatarUrl(path, base), {
                    credentials: "include", signal: controller.signal, cache: "no-store",
                    redirect: "error",
                });
                if (!response.ok) return;
                const blob = await response.blob();
                if (!active) return;
                objectUrl = urls.createObjectURL(blob);
                publish(objectUrl);
            } catch {
                if (active) publish(AVATAR_FALLBACK);
            }
        })();
    }
    return () => {
        active = false;
        controller.abort();
        if (objectUrl) urls.revokeObjectURL(objectUrl);
    };
}

export async function mutateAvatar(
    file: File | null, base: string, update: (user: LocalUser) => void,
    signal?: AbortSignal, fetcher: typeof fetch = fetch,
): Promise<void> {
    if (file) validateAvatar(file);
    const response = await fetcher(base.replace(/\/$/, "") + "/api/auth/me/avatar", {
        method: file ? "PUT" : "DELETE", credentials: "include", signal,
        ...(file ? {headers: {"Content-Type": "application/octet-stream"}, body: file} : {}),
    });
    if (!response.ok) {
        const error = await response.json().catch(() => null);
        throw new Error(typeof error?.detail === "string" ? error.detail : "Unable to save avatar.");
    }
    const user = await response.json() as LocalUser;
    if (!signal?.aborted) update(user);
}
