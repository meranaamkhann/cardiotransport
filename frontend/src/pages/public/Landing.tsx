import { Link } from "react-router-dom";
import { useAuth, homeFor } from "../../auth/AuthContext";

const modules = [
  { icon: "🩺", title: "Symptom assessment", text: "A structured questionnaire that starts with an emergency screen. Rules decide urgency first, and a model estimate can only raise it." },
  { icon: "📈", title: "Health monitoring", text: "Track blood pressure, cholesterol, glucose, weight and heart rate over time and see trends you can share with your doctor." },
  { icon: "🌿", title: "Wellness assessment", text: "Guideline-based review of risk factors with clear next steps. It is labelled as a review, never as a disease prediction." },
  { icon: "🔍", title: "Explainable AI", text: "Every model estimate shows what pushed it up or down, how many similar patients had disease, and how much that varied between hospitals." },
  { icon: "🏥", title: "Clinical workspace", text: "Review queue sorted by urgency, patient records, encrypted notes, appointments, local calibration and PDF reports." },
  { icon: "🧪", title: "Research engine", text: "Cross-hospital validation with calibration, decision curves and recalibration experiments. Reproduce the paper or run your own data." },
];

export default function Landing() {
  const { user } = useAuth();
  return (
    <>
      <section className="landing-hero">
        <div>
          <p className="eyebrow">Heart health assessment, monitoring and clinical intelligence</p>
          <h1>Understand your heart health, and know how far to trust the answer.</h1>
          <p className="lead">
            CardioLens combines safe symptom triage, everyday health monitoring and an explainable research model that was validated on
            hospitals it never saw. It supports clinicians. It does not diagnose.
          </p>
          <div className="actions">
            {user ? <Link className="btn primary" to={homeFor(user.role)}>Open your workspace</Link>
              : <><Link className="btn primary" to="/register">Create a free account</Link><Link className="btn ghost" to="/quick-check">Try a quick check</Link></>}
          </div>
          <p className="muted small">Emergency signs such as chest pain at rest, fainting or sudden breathlessness always come first: call your local emergency number.</p>
        </div>
        <div className="hero-panel" aria-hidden="true">
          <div className="hero-row"><span>Symptom triage</span><b className="badge level-prompt">Within days</b></div>
          <div className="hero-row"><span>Research model</span><b className="badge level-soon">Worth getting checked</b></div>
          <div className="hero-row"><span>Clinician review</span><b className="badge level-routine">Pending</b></div>
          <p className="muted small">Three clearly separated layers, each with its own provenance label.</p>
        </div>
      </section>

      <section>
        <h2 className="section-title">One platform, three audiences</h2>
        <div className="cards three">
          <div className="card"><h3>Patients</h3><p>Check symptoms, log measurements, read understandable reports, and share your record with a clinic only when you choose to.</p></div>
          <div className="card"><h3>Clinicians</h3><p>See the most urgent assessments first, review them, write notes, schedule follow-ups and calibrate the model to your own patients.</p></div>
          <div className="card"><h3>Researchers</h3><p>Compare models across hospitals, inspect calibration and subgroup performance, and export reproducible reports.</p></div>
        </div>
      </section>

      <section>
        <h2 className="section-title">What is inside</h2>
        <div className="cards three">
          {modules.map((m) => (
            <div key={m.title} className="card"><span className="option-icon" aria-hidden="true">{m.icon}</span><h3>{m.title}</h3><p className="muted">{m.text}</p></div>
          ))}
        </div>
      </section>

      <section className="card trust">
        <h2>Built to be honest about its limits</h2>
        <ul>
          <li><strong>Historical, referred patients.</strong> The research model learned from 1980s angiography records. It estimates narrowed arteries, not heart attack risk, and it is not a screening tool for the general public.</li>
          <li><strong>Tested on other hospitals.</strong> Reported performance comes from training on some hospitals and testing on another. The differences between hospitals are shown, not averaged away.</li>
          <li><strong>Safety rules outrank the model.</strong> A low model score can never lower an emergency or urgent triage result.</li>
          <li><strong>Everything is labelled.</strong> Patient-reported, rule-based, model-generated and clinician-reviewed information are kept apart in the app and in every report.</li>
          <li><strong>Your data stays yours.</strong> Clinics only see records of patients who joined with their code, and patients can leave at any time.</li>
        </ul>
        <div className="actions"><Link className="btn ghost" to="/how-it-works">See the evidence</Link></div>
      </section>
    </>
  );
}
