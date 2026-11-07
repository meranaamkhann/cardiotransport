const R = window.R;
const COL = ["#0e6b73", "#b04030", "#8a5a00", "#4d6a6f", "#6a4c93"];
const NAMES = { logistic_full: "Logistic (all features)", logistic_portable: "Logistic (portable)", forest_portable: "Forest (portable)" };
const sites = Object.keys(R.external.logistic_portable);
const axis = text => ({ title: { display: true, text } });
new Chart(document.getElementById("auc"), {
  type: "bar",
  data: { labels: sites, datasets: Object.keys(NAMES).map((k, i) => ({ label: NAMES[k], backgroundColor: COL[i], data: sites.map(s => R.external[k][s].auc) })) },
  options: { scales: { y: { min: 0.4, max: 1, ...axis("AUC") } } }
});
const ideal = { label: "Ideal", borderColor: "#999", borderDash: [5, 5], pointRadius: 0, data: [{ x: 0, y: 0 }, { x: 1, y: 1 }] };
new Chart(document.getElementById("cal"), {
  type: "line",
  data: { datasets: [...Object.entries(R.calib).map(([k, v], i) => ({ label: k, borderColor: COL[i % 5], backgroundColor: COL[i % 5], data: v.x.map((x, j) => ({ x, y: v.y[j] })) })), ideal] },
  options: { scales: { x: { type: "linear", min: 0, max: 1, ...axis("Mean predicted probability") }, y: { min: 0, max: 1, ...axis("Observed proportion") } } }
});
const pick = document.getElementById("siteSel");
Object.keys(R.dca).forEach(s => pick.add(new Option(s, s)));
let a, b;
function draw() {
  const s = pick.value, d = R.dca[s], u = R.update[s], ns = Object.keys(u);
  if (a) a.destroy();
  if (b) b.destroy();
  const line = (label, data, borderColor, extra = {}) => ({ label, data, borderColor, pointRadius: 0, ...extra });
  a = new Chart(document.getElementById("dca"), {
    type: "line",
    data: { labels: d.t, datasets: [line("Model", d.raw, COL[0]), line("Model, prevalence-adjusted", d.adjusted, COL[1]), line("Treat all", d.all, COL[3]), line("Treat none", d.t.map(() => 0), "#999", { borderDash: [4, 4] })] },
    options: { scales: { x: axis("Risk threshold"), y: axis("Net benefit") } }
  });
  b = new Chart(document.getElementById("upd"), {
    type: "line",
    data: { labels: ns, datasets: ["No update", "Intercept only", "Intercept and slope"].map((l, i) => line(l, ns.map(n => u[n][i]), [COL[3], COL[0], COL[1]][i], { pointRadius: 3 })) },
    options: { scales: { x: axis("Local labelled cases used"), y: axis("Brier score") } }
  });
}
pick.onchange = draw;
draw();
