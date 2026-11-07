import { useEffect, useState } from "react";
import { downloadHistory, myRecord, myRecords } from "../platformApi";
import type { RecordDetail, RecordRow } from "../platformApi";
import { Notice } from "../ui";

export function NoteList({ item }: { item: RecordDetail }) {
  return (
    <>
      {item.notes.map((n) => (
        <Notice key={n.id} tone="info" title={`Clinician review by ${n.author}`}>
          {n.body}
          <p className="muted small">Clinician-reviewed note, {new Date(n.created_at).toLocaleString()}</p>
        </Notice>
      ))}
    </>
  );
}

export default function Record() {
  const [rows, setRows] = useState<RecordRow[] | null>(null);
  const [open, setOpen] = useState<RecordDetail | null>(null);
  const [error, setError] = useState("");
  useEffect(() => {
    myRecords().then(setRows).catch((e: Error) => setError(e.message));
  }, []);
  const show = (id: number) => myRecord(id).then(setOpen).catch((e: Error) => setError(e.message));

  return (
    <section className="card stack">
      <div className="row between">
        <h2>My record</h2>
        <button className="btn ghost small" onClick={() => downloadHistory().catch((e: Error) => setError(e.message))}>Download CSV</button>
      </div>
      <p className="muted">Assessments you complete while signed in are saved here. Inputs are patient-reported, scores are model-generated, and notes are written by clinicians.</p>
      {error && <Notice tone="danger">{error}</Notice>}
      {rows && rows.length === 0 && <p className="muted">Nothing saved yet. Start a symptom check or a risk-factor check from the home page.</p>}
      <ul className="history">
        {rows?.map((r) => (
          <li key={r.id}>
            <button className="linklike" onClick={() => show(r.id)}>
              <strong>{r.kind === "symptom" ? "Symptom check" : "Risk-factor check"}{r.band ? ` · ${r.band} concern` : ""}</strong>
              <span>{r.emergency ? "Emergency warning reported · " : ""}{r.status === "reviewed" ? "Reviewed by a clinician" : "Awaiting review"}</span>
              <time dateTime={r.created_at}>{new Date(r.created_at).toLocaleString()}</time>
            </button>
          </li>
        ))}
      </ul>
      {open && (
        <div className="stack">
          <h3>{open.result.headline}</h3>
          {open.result.emergency?.active && <Notice tone="danger" title="Emergency warning">{open.result.emergency.message}</Notice>}
          <p>{open.result.summary}</p>
          {open.result.action && <p><strong>What to do:</strong> {open.result.action}</p>}
          <NoteList item={open} />
        </div>
      )}
    </section>
  );
}
