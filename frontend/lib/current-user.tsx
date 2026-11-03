"use client";

import {createContext, useContext} from "react";
import type {LocalUser} from "./auth";

export const CurrentUserContext = createContext<LocalUser | null>(null);

export function useCurrentUser() {
    return useContext(CurrentUserContext);
}
