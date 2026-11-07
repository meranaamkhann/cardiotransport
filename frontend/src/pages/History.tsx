import { useState } from "react";
import { clearHistory, loadHistory, removeHistory } from "../storage";
import type { HistoryEntry } from "../types";

export default function History({ onOpen }: { onOpen: (e: HistoryEntry) => void }) {
  const [items, setItems] = useState(loadHistory());
  const refresh = () => setItems(loadHistory());
  if (items.length === 0) {
    return <section className="card"><h2>Your history</h2><p className="muted">Nothing saved yet. Results you generate are kept on this device only.</p></section>;
  }
  return (
    <section className="card">
      <div className="row between">
        <h2>Your history</h2>
        <button className="btn ghost small" onClick={() => { clearHistory(); refresh(); }}>Clear all</button>
      </div>
      <p className="muted">Stored only in this browser. The server never keeps your answers.</p>
      <ul className="history">
        {items.map((e) => (
          <li key={e.id}>
            <button className="linklike" onClick={() => onOpen(e)}>
              <strong>{e.title}</strong>
              <span>{e.subtitle}</span>
              <time dateTime={e.createdAt}>{new Date(e.createdAt).toLocaleString()}</time>
            </button>
            <button className="btn ghost small" aria-label={`Delete ${e.title}`} onClick={() => { removeHistory(e.id); refresh(); }}>Delete</button>
          </li>
        ))}
      </ul>
    </section>
  );
}
