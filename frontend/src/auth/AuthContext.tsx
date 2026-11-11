import { createContext, ReactNode, useCallback, useContext, useEffect, useMemo } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { api, tokenStore } from "../api/client";
import type { User } from "../api/types";

interface Session {
  access_token: string;
  user: User;
}

interface AuthValue {
  user: User | null;
  loading: boolean;
  signIn: (email: string, password: string) => Promise<User>;
  register: (body: Record<string, unknown>, clinic?: boolean) => Promise<User>;
  signOut: () => void;
  refresh: () => Promise<unknown>;
}

const AuthContext = createContext<AuthValue | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const queryClient = useQueryClient();
  const hasToken = Boolean(tokenStore.get());
  const query = useQuery({ queryKey: ["me"], queryFn: () => api<User>("/auth/me"), enabled: hasToken, retry: false, staleTime: 60_000 });

  const accept = useCallback((session: Session) => {
    tokenStore.set(session.access_token);
    queryClient.setQueryData(["me"], session.user);
    return session.user;
  }, [queryClient]);

  const signOut = useCallback(() => {
    tokenStore.clear();
    queryClient.clear();
    queryClient.setQueryData(["me"], null);
  }, [queryClient]);

  useEffect(() => {
    window.addEventListener("cardiolens:signed-out", signOut);
    return () => window.removeEventListener("cardiolens:signed-out", signOut);
  }, [signOut]);

  const value = useMemo<AuthValue>(() => ({
    user: tokenStore.get() ? query.data ?? null : null,
    loading: hasToken && query.isLoading,
    signIn: async (email, password) => accept(await api<Session>("/auth/login", { method: "POST", body: { email, password } })),
    register: async (body, clinic = false) =>
      accept(await api<Session>(clinic ? "/auth/register-clinic" : "/auth/register", { method: "POST", body })),
    signOut,
    refresh: () => queryClient.invalidateQueries({ queryKey: ["me"] }),
  }), [query.data, query.isLoading, hasToken, accept, signOut, queryClient]);

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthValue {
  const value = useContext(AuthContext);
  if (!value) throw new Error("useAuth must be used inside AuthProvider");
  return value;
}

export const homeFor = (role: User["role"]) =>
  role === "patient" ? "/app" : role === "researcher" ? "/research" : "/clinic";
