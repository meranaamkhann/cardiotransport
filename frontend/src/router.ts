import { useEffect, useState } from "react";

const current = () => window.location.hash.replace(/^#/, "") || "/";

export function useRoute(): [string, (path: string) => void] {
  const [path, setPath] = useState(current());
  useEffect(() => {
    const handler = () => {
      setPath(current());
      window.scrollTo({ top: 0 });
    };
    window.addEventListener("hashchange", handler);
    return () => window.removeEventListener("hashchange", handler);
  }, []);
  return [path, (next) => { window.location.hash = next; }];
}
