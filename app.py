import json, os, joblib, numpy as np, pandas as pd
from flask import Flask, jsonify, render_template, request
app = Flask(__name__)
M = json.load(open("static/data/metrics.json")); FULL = joblib.load("model/full_lr.joblib"); PORT = joblib.load("model/port_lr.joblib")
RF = joblib.load("model/port_rf.joblib")
FEATS = "age sex cp trestbps chol fbs restecg thalach exang oldpeak slope ca thal".split()
EXTRA = ["slope", "ca", "thal"]; LIM = dict(age=(28, 77), trestbps=(90, 200), chol=(100, 600), thalach=(60, 202), oldpeak=(0, 6.2))
sig = lambda z: 1 / (1 + np.exp(-z)); lgt = lambda p: np.log(p / (1 - p))

def explain(model, row):
    pre, clf = model.named_steps["pre"], model.named_steps["m"]
    x = pre.transform(row); x = x.toarray() if hasattr(x, "toarray") else x
    agg = {}
    for n, v in zip(pre.get_feature_names_out(), x[0] * clf.coef_[0]):
        k = n.split("__")[1]; k = k.rsplit("_", 1)[0] if n.startswith("cat__") else k
        agg[k] = agg.get(k, 0) + float(v)
    return sorted(({"feature": k, "effect": round(v, 3)} for k, v in agg.items()), key=lambda d: -abs(d["effect"]))[:8]

def run(form):
    row = {f: pd.to_numeric(form.get(f) or np.nan, errors="coerce") for f in FEATS}
    df = pd.DataFrame([row]); target = float(form.get("site_prev") or M["dev_prev"] * 100) / 100
    target = min(max(target, .02), .98)
    use_full = all(not pd.isna(row[c]) for c in EXTRA); model = FULL if use_full else PORT
    raw = float(model.predict_proba(df[[c for c in FEATS if use_full or c not in EXTRA]])[:, 1][0])
    shift = lgt(target) - lgt(M["dev_prev"])                       # prior-shift (calibration-in-the-large) update
    adj = float(sig(lgt(np.clip(raw, 1e-4, 1 - 1e-4)) + shift))
    rf = float(RF.predict_proba(df[[c for c in FEATS if c not in EXTRA]])[:, 1][0])
    flags = []
    miss = [c for c in FEATS if pd.isna(row[c]) and c not in EXTRA]
    if miss: flags.append(f"Missing inputs ({', '.join(miss)}) were filled with Cleveland medians/modes; treat the estimate as weaker.")
    if not use_full: flags.append("Portable 10-predictor model used (slope, vessels, thal not all supplied).")
    for k, (lo, hi) in LIM.items():
        if not pd.isna(row[k]) and not lo <= row[k] <= hi: flags.append(f"{k} is outside the development range ({lo}-{hi}).")
    if row["sex"] == 0: flags.append("Women: external sensitivity was only 0.40 in this study (97 records, exploratory).")
    if abs(shift) > .8: flags.append("Large prevalence gap vs Cleveland: unadjusted probabilities are unreliable here.")
    gap = abs(raw - rf)
    if gap > .25: flags.append("Logistic and random-forest estimates disagree strongly.")
    return dict(model="full" if use_full else "portable", raw=round(raw, 3), adjusted=round(adj, 3), rf=round(rf, 3),
                target_prev=target, contributions=explain(model, df[[c for c in FEATS if use_full or c not in EXTRA]]),
                flags=flags, disclaimer="Research prototype on 1980s angiography cohorts. Not for clinical use.")

@app.route("/")
def index(): return render_template("index.html", sites=M["cohorts"], dev=M["dev_prev"] * 100)
@app.route("/performance")
def perf(): return render_template("performance.html", m=M)
@app.route("/about")
def about(): return render_template("about.html")
@app.route("/predict", methods=["POST"])
def predict(): return jsonify(run(request.form))
@app.route("/api/predict", methods=["POST"])
def api(): return jsonify(run({k: str(v) for k, v in (request.get_json(force=True) or {}).items()}))
if __name__ == "__main__": app.run(port=int(os.environ.get("PORT", 5000)), debug=True)
