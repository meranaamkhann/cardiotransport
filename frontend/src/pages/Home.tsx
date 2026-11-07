import { Disclaimer, Notice } from "../ui";

export default function Home({ go }: { go: (path: string) => void }) {
  const options = [
    { path: "/check/symptomatic", icon: "💢", title: "I have chest pain or related symptoms", text: "Answer a few plain-language questions and see how closely your situation resembles patients who were found to have heart artery blockage." },
    { path: "/check/referred", icon: "📋", title: "A doctor or test told me to get my heart checked", text: "For people sent for a heart evaluation without chest pain, for example after an abnormal ECG or test result." },
    { path: "/wellness", icon: "🌿", title: "I feel fine and want to know my risk factors", text: "A quick check of blood pressure, cholesterol, sugar, weight, smoking, and activity, with simple things to improve." },
  ];
  return (
    <>
      <section className="hero">
        <h1>Does your heart need a closer look?</h1>
        <p>CardioLens turns your symptoms and everyday numbers into a clear, honest next step, and tells you how much to trust it.</p>
      </section>
      <Notice tone="danger" title="Chest pain right now?">
        Pain at rest, pain spreading to the arm or jaw, fainting, or sudden breathlessness can be a heart attack. Call your local emergency number (112 in India) before using this tool.
      </Notice>
      <h2 className="section-title">What brings you here?</h2>
      <div className="cards">
        {options.map((o) => (
          <button key={o.path} className="card option" onClick={() => go(o.path)}>
            <span className="option-icon" aria-hidden="true">{o.icon}</span>
            <span className="option-title">{o.title}</span>
            <span className="option-text">{o.text}</span>
            <span className="option-go">Start →</span>
          </button>
        ))}
      </div>
      <section className="card trust">
        <h2>Why this is different from a typical heart-disease predictor</h2>
        <ul>
          <li><strong>Tested on other hospitals.</strong> Many tools only report accuracy on the hospital they learned from. This one is judged on hospitals it never saw.</li>
          <li><strong>Honest numbers.</strong> You see how often people with similar answers actually had blockage, and how much that varied between hospitals, not a made-up percentage.</li>
          <li><strong>Works with what you know.</strong> It does not need lab-only measurements. Leave out anything you do not have and it tells you how that affects confidence.</li>
          <li><strong>Private.</strong> Nothing you enter is stored on the server. Your history stays on this device.</li>
        </ul>
      </section>
      <Disclaimer />
    </>
  );
}
