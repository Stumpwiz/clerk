"use client";

import {useEffect, useState} from "react";
import {AVATAR_FALLBACK, loadAvatar} from "@/lib/avatars";

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL ?? "";

export function Avatar({userId, path, className = "", alt = ""}: {
    userId: number; path: string | null; className?: string; alt?: string;
}) {
    const identity = String(userId) + ":" + (path ?? "");
    const [image, setImage] = useState({identity: "", src: AVATAR_FALLBACK});
    useEffect(() => loadAvatar(path, API_BASE_URL, src => {
        setImage({identity, src});
    }), [identity, path]);

    // Never render a previous user's blob while the effect catches up.
    const src = image.identity === identity ? image.src : AVATAR_FALLBACK;
    return (
        // eslint-disable-next-line @next/next/no-img-element
        <img src={src} alt={alt} className={className}
             onError={() => setImage({identity, src: AVATAR_FALLBACK})}/>
    );
}
