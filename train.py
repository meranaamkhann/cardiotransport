"""Reproduces the paper: develop on Cleveland, validate WITHOUT refitting on Hungary/Switzerland/Long Beach.
Run once:  python train.py   (downloads UCI data, writes model/*.joblib and static/data/metrics.json)"""
import json, joblib, numpy as np, pandas as pd, statsmodels.api as sm
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import RandomForestClassifier
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (roc_auc_score, average_precision_score, brier_score_loss,
                             confusion_matrix, f1_score, accuracy_score)
from sklearn.calibration import calibration_curve
from sklearn.model_selection import RepeatedStratifiedKFold
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

SEED, BASE = 20260904, "https://archive.ics.uci.edu/ml/machine-learning-databases/heart-disease/processed."
COLS = "age sex cp trestbps chol fbs restecg thalach exang oldpeak slope ca thal num".split()
NUM = ["age", "trestbps", "chol", "thalach", "oldpeak"]
FULL = COLS[:-1]; PORT = [c for c in FULL if c not in ("slope", "ca", "thal")]
SITES = {"Cleveland": "cleveland", "Hungary": "hungarian", "Switzerland": "switzerland", "Long Beach VA": "va"}
rng = np.random.default_rng(SEED)

def load(f):
    d = pd.read_csv(f"{BASE}{f}.data", header=None, names=COLS, na_values="?")
    d["y"] = (d.num > 0).astype(int); return d
data = {k: load(v) for k, v in SITES.items()}

def pipe(feats, model):
    pre = ColumnTransformer([
        ("num", Pipeline([("i", SimpleImputer(strategy="median")), ("s", StandardScaler())]), [c for c in feats if c in NUM]),
        ("cat", Pipeline([("i", SimpleImputer(strategy="most_frequent")),
                          ("o", OneHotEncoder(handle_unknown="ignore"))]), [c for c in feats if c not in NUM])])
    return Pipeline([("pre", pre), ("m", model)])
LR = lambda: LogisticRegression(penalty="l2", C=1.0, max_iter=2000)
RF = lambda: RandomForestClassifier(500, max_depth=5, min_samples_leaf=5, max_features="sqrt", random_state=SEED, n_jobs=-1)
MODELS = {"full_lr": (FULL, LR), "port_lr": (PORT, LR), "full_rf": (FULL, RF), "port_rf": (PORT, RF)}

logit = lambda p: np.log(np.clip(p, 1e-6, 1 - 1e-6) / (1 - np.clip(p, 1e-6, 1 - 1e-6)))
def calib(y, p):
    z = logit(p)
    slope = sm.Logit(y, sm.add_constant(z)).fit(disp=0).params[1]
    inter = sm.GLM(y, np.ones_like(z), family=sm.families.Binomial(), offset=z).fit().params[0]
    return round(float(inter), 3), round(float(slope), 3)
def metrics(y, p, boot=True):
    y, p = np.asarray(y), np.asarray(p); yh = (p >= .5).astype(int)
    tn, fp, fn, tp = confusion_matrix(y, yh, labels=[0, 1]).ravel()
    m = dict(n=len(y), prev=round(y.mean(), 3), auc=roc_auc_score(y, p), ap=average_precision_score(y, p),
             brier=brier_score_loss(y, p), sens=tp / max(tp + fn, 1), spec=tn / max(tn + fp, 1),
             f1=f1_score(y, yh), acc=accuracy_score(y, yh))
    m["cal_intercept"], m["cal_slope"] = calib(y, p)
    if boot:
        a = []
        for _ in range(2000):
            i = rng.integers(0, len(y), len(y))
            if y[i].min() != y[i].max(): a.append(roc_auc_score(y[i], p[i]))
        m["auc_ci"] = np.percentile(a, [2.5, 97.5]).tolist()
    return {k: (round(v, 3) if isinstance(v, float) else v) for k, v in m.items()}

dev = data["Cleveland"]; ext = {k: v for k, v in data.items() if k != "Cleveland"}
out = dict(dev_prev=float(dev.y.mean()), internal={}, external={}, calib={}, sex={}, coefs={}, missing={}, cohorts={})
for k, d in data.items():
    out["cohorts"][k] = dict(n=len(d), disease=int(d.y.sum()), prev=round(d.y.mean() * 100, 1),
                             age=float(d.age.median()), female=int((d.sex == 0).sum()))
    out["missing"][k] = {c: round(float(d[c].isna().mean() * 100), 1) for c in FULL}

for name, (feats, mk) in MODELS.items():
    oof = np.zeros(len(dev)); cv = RepeatedStratifiedKFold(n_splits=5, n_repeats=10, random_state=SEED)
    for tr, te in cv.split(dev[feats], dev.y):                      # preprocessing fitted inside each training fold
        oof_fold = pipe(feats, mk()).fit(dev.iloc[tr][feats], dev.y.iloc[tr]).predict_proba(dev.iloc[te][feats])[:, 1]
        oof[te] += oof_fold / 10
    out["internal"][name] = metrics(dev.y, oof)
    final = pipe(feats, mk()).fit(dev[feats], dev.y)               # one refit on all 303 Cleveland records
    joblib.dump(final, f"model/{name}.joblib")
    if name.startswith("port"):
        out["external"][name] = {}
        pool_y, pool_p = [], []
        for site, d in ext.items():
            p = final.predict_proba(d[feats])[:, 1]; pool_y += list(d.y); pool_p += list(p)
            out["external"][name][site] = metrics(d.y, p)
            if name == "port_lr":
                fy, fx = calibration_curve(d.y, p, n_bins=5, strategy="quantile"); out["calib"][site] = dict(x=fx.round(3).tolist(), y=fy.round(3).tolist())
        out["external"][name]["Pooled"] = metrics(pool_y, pool_p)
        if name == "port_lr":
            pool = pd.concat(ext.values()); pp = final.predict_proba(pool[feats])[:, 1]
            for lab, s in (("Female", 0), ("Male", 1)):
                for cohort, dd, pr in (("Cleveland", dev, final.predict_proba(dev[feats])[:, 1]), ("External pooled", pool, pp)):
                    mk_ = (dd.sex == s).values; out["sex"][f"{cohort}|{lab}"] = metrics(dd.y[mk_], pr[mk_], boot=False)
            names = final.named_steps["pre"].get_feature_names_out()
            out["coefs"] = {n: round(float(c), 3) for n, c in zip(names, final.named_steps["m"].coef_[0])}
    print(name, "internal AUC", out["internal"][name]["auc"])
json.dump(out, open("static/data/metrics.json", "w"), indent=1)
print("done -> model/*.joblib, static/data/metrics.json")
