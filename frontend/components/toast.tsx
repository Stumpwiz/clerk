"use client";

import {useEffect} from "react";
import {CheckCircle, XCircle, X} from "lucide-react";

interface ToastProps {
    message: string;
    type: "success" | "error";
    onClose: () => void;
}

export function Toast({message, type, onClose}: ToastProps) {
    useEffect(() => {
        const timer = setTimeout(() => {
            onClose();
        }, 5000);

        return () => clearTimeout(timer);
    }, [onClose]);

    return (
        <div className="fixed bottom-4 right-4 z-50 animate-in slide-in-from-bottom-5">
            <div
                className={`flex items-center gap-3 px-4 py-3 rounded-lg shadow-lg ${
                    type === "success"
                        ? "bg-green-50 border border-green-200"
                        : "bg-red-50 border border-red-200"
                }`}
            >
                {type === "success" ? (
                    <CheckCircle className="w-5 h-5 text-green-600"/>
                ) : (
                    <XCircle className="w-5 h-5 text-red-600"/>
                )}
                <p
                    className={`text-sm font-medium ${
                        type === "success" ? "text-green-900" : "text-red-900"
                    }`}
                >
                    {message}
                </p>
                <button
                    onClick={onClose}
                    className={`ml-2 ${
                        type === "success" ? "text-green-600" : "text-red-600"
                    } hover:opacity-70`}
                >
                    <X className="w-4 h-4"/>
                </button>
            </div>
        </div>
    );
}
