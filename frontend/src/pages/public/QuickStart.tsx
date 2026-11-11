import { useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import type { ModelEstimate, WellnessResult } from "../../api/types";
import { QuickResult, QuickWellnessResult } from "../../components/ModelResult";
import { Notice } from "../../components/ui";
import QuickCheck from "./QuickCheck";
import QuickWellness from "./QuickWellness";

export function QuickHome() {
  const options = [
    { to: "/quick-check/symptomatic", icon: "💢", title: "I have chest pain or related symptoms", text: "Plain-language questions, then a band with the share of similar patients who had blockage." },
    { to: "/quick-check/referred", icon: "📋", title: "A doctor or test told me to get my heart checked", text: "For people sent for a heart evaluation without chest pain." },
    { to: "/quick-check/wellness", icon: "🌿", title: "I feel fine and want to review my risk factors", text: "Blood pressure, cholesterol, sugar, weight, smoking and activity against guideline cut-offs." },
  ];
  return (
    <div className="stack">
      <h1>Quick check</h1>
      <p className="lead">No account needed and nothing is saved. Create an account to keep a history and share it with a clinic.</p>
      <Notice tone="danger" title="Chest pain right now?">
        Pain at rest, pain spreading to the arm or jaw, fainting, or sudden breathlessness can be a heart attack. Call your local emergency number (112 in India) first.
      </Notice>
      <div className="cards">
        {options.map((o) => (
          <Link key={o.to} to={o.to} className="card option">
            <span className="option-icon" aria-hidden="true">{o.icon}</span>
            <span className="option-title">{o.title}</span>
            <span className="option-text">{o.text}</span>
            <span className="option-go">Start →</span>
          </Link>
        ))}
      </div>
    </div>
  );
}

export function QuickRun() {
  const { kind } = useParams();
  const navigate = useNavigate();
  const [check, setCheck] = useState<ModelEstimate | null>(null);
  const [wellness, setWellness] = useState<WellnessResult | null>(null);
  const reset = () => { setCheck(null); setWellness(null); navigate("/quick-check"); };
  if (check) return <QuickResult r={check} onAgain={reset} />;
  if (wellness) return <QuickWellnessResult r={wellness} onAgain={reset} />;
  if (kind === "symptomatic" || kind === "referred") return <QuickCheck key={kind} pathway={kind} onResult={setCheck} />;
  if (kind === "wellness") return <QuickWellness onResult={(r) => setWellness(r)} />;
  return <QuickHome />;
}
