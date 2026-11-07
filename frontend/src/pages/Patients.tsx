import { useEffect, useState } from "react";
import { addNote, patientRecords, patients } from "../platformApi";
import type { PatientRow, RecordDetail } from "../platformApi";
import { Notice } from "../ui";
import { NoteList } from "./Record";

export default function Patients({ canReview }: { canReview: boolean }) {
  const [rows, setRows] = useState<PatientRow[] | null>(null);
  const [chosen, setChosen] = useState<PatientRow | null>(null);
  const [items, setItems] = useState<RecordDetail[]>([]);
  const [draft, setDraft] = useState<Record<number, string>>({});
  const [error, setError] = useState("");
  const fail = (e: Error) => setError(e.message);
  useEffect(() => {
    patients().then(setRows).catch(fail);
  }, []);

  const pick = (p: PatientRow) => {
    setChosen(p);
    setError("");
    patientRecords(p.id).then(setItems).catch(fail);
  };
  const save = async (id: number) => {
    try {
      const updated = await addNote(id, draft[id] ?? "");
      setItems(items.map((i) => (i.id === id ? updated : i)));
      setDraft({ ...draft, [id]: "" });
      patients().then(setRows).catch(fail);
    } catch (e) {
      fail(e as Error);
    }
  };

  return (
    <div className="grid2">
      <section className="card stack">
        <h2>Patient directory</h2>
        {error && <Notice tone="danger">{error}</Notice>}
        {rows && rows.length === 0 && <p className="muted">No patients have registered with your clinic code yet.</p>}
        <ul className="history">
          {rows?.map((p) => (
            <li key={p.id}>
              <button className="linklike" onClick={() => pick(p)}>
                <strong>{p.name}</strong>
                <span>{p.assessments} assessments · {p.pending_review} awaiting review</span>
              </button>
            </li>
          ))}
        </ul>
      </section>
      <section className="card stack">
        <h2>{chosen ? chosen.name : "Select a patient"}</h2>
        {chosen && items.length === 0 && <p className="muted">No assessments yet.</p>}
        {items.map((a) => (
          <div key={a.id} className="stack">
            <h3>{a.result.headline} <span className="chip">{a.status}</span></h3>
            {a.emergency && <Notice tone="danger">Patient reported emergency warning signs.</Notice>}
            <p>{a.result.summary}</p>
            <p className="muted small">Patient-reported inputs, model-generated score (version {a.model_version}). Not a diagnosis.</p>
            <NoteList item={a} />
            {canReview && (
              <>
                <textarea rows={3} maxLength={4000} aria-label="Clinical note" value={draft[a.id] ?? ""} onChange={(e) => setDraft({ ...draft, [a.id]: e.target.value })} />
                <button className="btn primary small" disabled={!(draft[a.id] ?? "").trim()} onClick={() => save(a.id)}>Save review note</button>
              </>
            )}
          </div>
        ))}
      </section>
    </div>
  );
}
