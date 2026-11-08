"use client";

import {useEffect, useRef, useState} from "react";
import type {LocalUser} from "@/lib/auth";
import {mutateAvatar, validateAvatar} from "@/lib/avatars";
import {Avatar} from "./avatar";

export function AvatarManager({user, onUpdate}: {user: LocalUser; onUpdate: (user: LocalUser) => void}) {
    const [file, setFile] = useState<File | null>(null);
    const [preview, setPreview] = useState<{file: File; url: string} | null>(null);
    const [busy, setBusy] = useState(false);
    const [error, setError] = useState<string | null>(null);
    const [message, setMessage] = useState("");
    const input = useRef<HTMLInputElement>(null);
    const request = useRef<AbortController | null>(null);

    useEffect(() => () => request.current?.abort(), []);
    useEffect(() => {
        if (!file) return;
        const url = URL.createObjectURL(file);
        setPreview({file, url});
        return () => URL.revokeObjectURL(url);
    }, [file]);

    async function save(remove = false) {
        if (busy || (!remove && !file)) return;
        const controller = new AbortController();
        request.current = controller;
        setBusy(true);
        setError(null);
        setMessage("");
        try {
            await mutateAvatar(remove ? null : file, process.env.NEXT_PUBLIC_API_URL ?? "", onUpdate, controller.signal);
            if (controller.signal.aborted) return;
            setFile(null);
            if (input.current) input.current.value = "";
            setMessage(remove ? "Avatar removed." : "Avatar saved.");
        } catch (err) {
            if (!controller.signal.aborted) setError(err instanceof Error ? err.message : "Unable to save avatar.");
        } finally {
            if (!controller.signal.aborted) setBusy(false);
        }
    }

    return (
        <section className="bg-white shadow rounded-lg p-6 space-y-4" aria-labelledby="avatar-title" aria-busy={busy}>
            <h2 id="avatar-title" className="text-xl font-semibold text-gray-900">Profile photo</h2>
            <Avatar userId={user.id} path={user.avatar_path} alt="Current profile photo"
                    className="h-20 w-20 rounded-full border border-gray-200 bg-white object-cover"/>
            <label htmlFor="avatar-file" className="block text-sm font-medium text-gray-700">Choose a photo</label>
            <p id="avatar-help" className="text-sm text-gray-600">JPEG, PNG, or WebP, up to 2 MiB. Photos are cropped centrally to a square.</p>
            <input ref={input} id="avatar-file" type="file" accept="image/jpeg,image/png,image/webp"
                   aria-describedby="avatar-help" disabled={busy} className="block text-sm text-gray-700"
                   onChange={event => {
                       setFile(null);
                       setError(null);
                       setMessage("");
                       const selected = event.target.files?.[0];
                       if (!selected) return;
                       try {
                           validateAvatar(selected);
                           setFile(selected);
                       } catch (err) {
                           event.target.value = "";
                           setError(err instanceof Error ? err.message : "Invalid image.");
                       }
                   }}/>
            {file && preview?.file === file && (
                // eslint-disable-next-line @next/next/no-img-element
                <img src={preview.url} alt="Selected photo preview"
                     className="h-32 w-32 rounded-full object-cover" onError={() => {
                         setFile(null);
                         if (input.current) input.current.value = "";
                         setError("This image could not be previewed. Choose another image.");
                     }}/>
            )}
            <div className="flex gap-3">
                <button type="button" disabled={busy || !file} onClick={() => void save()}
                        className="px-4 py-2 text-sm font-medium text-white bg-blue-600 rounded-md disabled:opacity-50">
                    {user.avatar_path ? "Replace photo" : "Upload photo"}
                </button>
                <button type="button" disabled={busy || !user.avatar_path} onClick={() => void save(true)}
                        className="px-4 py-2 text-sm font-medium text-gray-700 border border-gray-300 rounded-md disabled:opacity-50">
                    Remove photo
                </button>
            </div>
            <p role="status" aria-live="polite" className="text-sm text-gray-600">{busy ? "Saving avatar…" : message}</p>
            {error && <p role="alert" className="text-sm text-red-700">{error}</p>}
        </section>
    );
}
