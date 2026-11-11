import math
import warnings

import numpy as np
import pandas as pd
import statsmodels.api as sm
from scipy.stats import rankdata
from sklearn.metrics import average_precision_score, roc_curve

warnings.filterwarnings("ignore", category=RuntimeWarning)
warnings.filterwarnings("ignore", module="statsmodels")

THRESHOLDS = np.round(np.arange(0.05, 0.81, 0.05), 2)


def sig(z):
    return 1 / (1 + np.exp(-np.clip(z, -30, 30)))


def logit(p):
    p = np.clip(p, 1e-6, 1 - 1e-6)
    return np.log(p / (1 - p))


def rnd(value, digits=3):
    if value is None:
        return None
    value = float(value)
    return None if math.isnan(value) else round(value, digits)


def auc(y, p):
    n1 = int(y.sum())
    n0 = len(y) - n1
    if n1 == 0 or n0 == 0:
        return float("nan")
    ranks = rankdata(p)
    return (ranks[y == 1].sum() - n1 * (n1 + 1) / 2) / (n1 * n0)


def brier(y, p):
    return float(np.mean((p - y) ** 2))


def classification(y, p, threshold=0.5):
    predicted = p >= threshold
    tp = int((predicted & (y == 1)).sum())
    fp = int((predicted & (y == 0)).sum())
    fn = int((~predicted & (y == 1)).sum())
    tn = int((~predicted & (y == 0)).sum())
    sensitivity = tp / max(tp + fn, 1)
    specificity = tn / max(tn + fp, 1)
    precision = tp / max(tp + fp, 1)
    f1 = 2 * precision * sensitivity / max(precision + sensitivity, 1e-12)
    return {"sensitivity": sensitivity, "specificity": specificity, "precision": precision, "f1": f1,
            "balanced_accuracy": (sensitivity + specificity) / 2, "accuracy": (tp + tn) / max(len(y), 1)}


def calibration_terms(y, p):
    z = logit(p)
    try:
        slope = sm.Logit(y, sm.add_constant(z)).fit(disp=0).params[1]
        intercept = sm.GLM(y, np.ones((len(z), 1)), family=sm.families.Binomial(), offset=z).fit().params[0]
        return float(intercept), float(slope)
    except Exception:
        return None, None


def bootstrap_intervals(y, p, rng, draws):
    index = rng.integers(0, len(y), (draws, len(y)))
    keys = ("auc", "brier", "sensitivity", "specificity")
    store = {k: [] for k in keys}
    for row in index:
        yb, pb = y[row], p[row]
        if yb.min() == yb.max():
            continue
        c = classification(yb, pb)
        store["auc"].append(auc(yb, pb))
        store["brier"].append(brier(yb, pb))
        store["sensitivity"].append(c["sensitivity"])
        store["specificity"].append(c["specificity"])
    return {k: ([rnd(v) for v in np.percentile(vals, [2.5, 97.5])] if vals else None) for k, vals in store.items()}


def metric_set(y, p, rng, draws=0):
    y = np.asarray(y).astype(int)
    p = np.asarray(p, dtype=float)
    two = len(set(y.tolist())) == 2
    c = classification(y, p)
    out = {"n": int(len(y)), "events": int(y.sum()), "prevalence": rnd(y.mean()),
           "auc": rnd(auc(y, p)) if two else None,
           "average_precision": rnd(average_precision_score(y, p)) if two else None,
           "brier": rnd(brier(y, p)), **{k: rnd(v) for k, v in c.items()},
           "cal_intercept": None, "cal_slope": None, "auc_ci": None, "brier_ci": None,
           "sensitivity_ci": None, "specificity_ci": None}
    if two:
        intercept, slope = calibration_terms(y, p)
        out["cal_intercept"], out["cal_slope"] = rnd(intercept), rnd(slope)
        if draws:
            ci = bootstrap_intervals(y, p, rng, draws)
            out["auc_ci"], out["brier_ci"] = ci["auc"], ci["brier"]
            out["sensitivity_ci"], out["specificity_ci"] = ci["sensitivity"], ci["specificity"]
    return out


def roc_points(y, p, limit=60):
    if len(set(np.asarray(y).tolist())) < 2:
        return None
    fpr, tpr, _ = roc_curve(y, p)
    if len(fpr) > limit:
        keep = np.unique(np.linspace(0, len(fpr) - 1, limit).astype(int))
        fpr, tpr = fpr[keep], tpr[keep]
    return {"fpr": [rnd(v) for v in fpr], "tpr": [rnd(v) for v in tpr]}


def calibration_bins(y, p, bins=5):
    frame = pd.DataFrame({"y": np.asarray(y), "p": np.asarray(p)})
    try:
        frame["bin"] = pd.qcut(frame["p"], bins, labels=False, duplicates="drop")
    except ValueError:
        return None
    grouped = frame.groupby("bin").agg(p=("p", "mean"), y=("y", "mean"), n=("y", "size"))
    return {"predicted": [rnd(v) for v in grouped["p"]], "observed": [rnd(v) for v in grouped["y"]],
            "n": [int(v) for v in grouped["n"]]}


def net_benefit(y, q, t):
    return float(((q >= t) & (y == 1)).mean() - ((q >= t) & (y == 0)).mean() * t / (1 - t))


def decision_curve(y, p, adjusted):
    prevalence = y.mean()
    return {"thresholds": [float(t) for t in THRESHOLDS],
            "model": [rnd(net_benefit(y, p, t), 4) for t in THRESHOLDS],
            "prevalence_adjusted": [rnd(net_benefit(y, adjusted, t), 4) for t in THRESHOLDS],
            "treat_all": [rnd(prevalence - (1 - prevalence) * t / (1 - t), 4) for t in THRESHOLDS],
            "treat_none": [0.0 for _ in THRESHOLDS]}


def update_study(y, p, rng, sizes=(10, 20, 40, 80), draws=100):
    z, out = logit(p), {}
    for n in sizes:
        if n > len(y) * 0.6:
            continue
        rows = [[], [], []]
        for _ in range(draws):
            i = rng.choice(len(y), n, replace=False)
            rest = np.setdiff1d(np.arange(len(y)), i)
            if y[i].min() == y[i].max():
                continue
            try:
                a = sm.GLM(y[i], np.ones(n), family=sm.families.Binomial(), offset=z[i]).fit().params[0]
                c = sm.Logit(y[i], sm.add_constant(z[i])).fit(disp=0).params
            except Exception:
                continue
            rows[0].append(brier(y[rest], p[rest]))
            rows[1].append(brier(y[rest], sig(z[rest] + a)))
            rows[2].append(brier(y[rest], sig(c[0] + c[1] * z[rest])))
        if rows[0]:
            out[str(n)] = {"none": rnd(np.mean(rows[0]), 4), "intercept": rnd(np.mean(rows[1]), 4),
                           "intercept_slope": rnd(np.mean(rows[2]), 4)}
    return out


def full_update(y, p):
    if len(set(y.tolist())) < 2:
        return None
    z = logit(p)
    try:
        a = float(sm.GLM(y, np.ones((len(z), 1)), family=sm.families.Binomial(), offset=z).fit().params[0])
        c = sm.Logit(y, sm.add_constant(z)).fit(disp=0).params
    except Exception:
        return None
    after_i, after_s = sig(z + a), sig(c[0] + c[1] * z)
    return {"intercept": {"shift": rnd(a), "brier": rnd(brier(y, after_i), 4)},
            "intercept_slope": {"intercept": rnd(c[0]), "slope": rnd(c[1]), "brier": rnd(brier(y, after_s), 4)},
            "brier_before": rnd(brier(y, p), 4), "note": "Apparent performance on the same records, so optimistic."}


def verdicts(internal_auc, external):
    rows = []
    for site, m in external.items():
        found = []
        if m["auc"] is not None and internal_auc is not None and internal_auc - m["auc"] > 0.08:
            found.append("ranking degraded by more than 0.08 AUC")
        if m["cal_intercept"] is not None and abs(m["cal_intercept"]) > 0.5:
            found.append("baseline risk shifted (calibration intercept beyond ±0.5)")
        if m["cal_slope"] is not None and not 0.8 <= m["cal_slope"] <= 1.2:
            found.append("predictions over- or under-confident (calibration slope outside 0.8 to 1.2)")
        rows.append({"site": site, "level": "warn" if found else "ok",
                     "status": "; ".join(found) if found else "transports acceptably by these rules of thumb"})
    return rows
