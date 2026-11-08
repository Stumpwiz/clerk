"use client";

import {createContext, useContext} from "react";
import type {LocalUser} from "./auth";

export const CurrentUserContext = createContext<LocalUser | null>(null);

export const UpdateCurrentUserContext = createContext<(user: LocalUser) => void>(() => {});

export function useUpdateCurrentUser() {
    return useContext(UpdateCurrentUserContext);
}

export function useCurrentUser() {
    return useContext(CurrentUserContext);
}
