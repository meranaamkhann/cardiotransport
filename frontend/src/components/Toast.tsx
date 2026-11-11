import { createContext, ReactNode, useCallback, useContext, useMemo, useState } from "react";

type Tone = "good" | "warn";
interface Item {
  id: number;
  tone: Tone;
  text: string;
}

interface ToastApi {
  success: (text: string) => void;
  error: (text: string) => void;
}

const ToastContext = createContext<ToastApi | null>(null);
let counter = 0;

export function ToastProvider({ children }: { children: ReactNode }) {
  const [items, setItems] = useState<Item[]>([]);
  const push = useCallback((tone: Tone, text: string) => {
    const id = ++counter;
    setItems((list) => [...list, { id, tone, text }]);
    window.setTimeout(() => setItems((list) => list.filter((i) => i.id !== id)), tone === "warn" ? 7000 : 4000);
  }, []);
  const api = useMemo<ToastApi>(() => ({ success: (t) => push("good", t), error: (t) => push("warn", t) }), [push]);
  return (
    <ToastContext.Provider value={api}>
      {children}
      <div className="toasts" role="status" aria-live="polite">
        {items.map((i) => (
          <div key={i.id} className={`toast ${i.tone}`}>
            <span aria-hidden="true">{i.tone === "good" ? "✓" : "!"}</span>
            <span>{i.text}</span>
            <button aria-label="Dismiss" onClick={() => setItems((list) => list.filter((x) => x.id !== i.id))}>×</button>
          </div>
        ))}
      </div>
    </ToastContext.Provider>
  );
}

export function useToast(): ToastApi {
  const value = useContext(ToastContext);
  if (!value) return { success: () => undefined, error: () => undefined };
  return value;
}
