export type Role = "patient" | "clinician" | "admin" | "researcher";
export interface Session {
  token: string;
  role: Role;
  name: string;
}

const KEY = "cardiolens.session.v1";

export function getSession(): Session | null {
  try {
    const raw = window.sessionStorage.getItem(KEY);
    return raw ? (JSON.parse(raw) as Session) : null;
  } catch {
    return null;
  }
}

export function setSession(session: Session | null) {
  try {
    if (session) window.sessionStorage.setItem(KEY, JSON.stringify(session));
    else window.sessionStorage.removeItem(KEY);
  } catch {
    return;
  }
}

export function authHeader(): Record<string, string> {
  const session = getSession();
  return session ? { Authorization: `Bearer ${session.token}` } : {};
}
