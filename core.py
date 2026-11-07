import warnings

import numpy as np
import pandas as pd
import statsmodels.api as sm
from sklearn.calibration import calibration_curve
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import RandomForestClassifier
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import brier_score_loss, confusion_matrix, roc_auc_score
from sklearn.model_selection import RepeatedStratifiedKFold
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

warnings.filterwarnings("ignore", category=RuntimeWarning)
warnings.filterwarnings("ignore", module="statsmodels")

SEED = 7
MAX_MISSING = 0.30
THRESHOLDS = np.arange(0.05, 0.81, 0.05)


def sig(z):
    return 1 / (1 + np.exp(-np.clip(z, -30, 30)))


def logit(p):
    p = np.clip(p, 1e-6, 1 - 1e-6)
    return np.log(p / (1 - p))


def build(num, cat, kind):
    pre = ColumnTransformer([
        ("n", Pipeline([("i", SimpleImputer(strategy="median")), ("s", StandardScaler())]), num),
        ("c", Pipeline([("i", SimpleImputer(strategy="most_frequent")),
                        ("o", OneHotEncoder(handle_unknown="ignore"))]), cat)])
    if kind == "logistic":
        clf = LogisticRegression(max_iter=2000)
    else:
        clf = RandomForestClassifier(200, max_depth=5, min_samples_leaf=5, random_state=SEED, n_jobs=-1)
    return Pipeline([("pre", pre), ("m", clf)])


def calib(y, p):
    z = logit(p)
    try:
        slope = sm.Logit(y, sm.add_constant(z)).fit(disp=0).params[1]
        inter = sm.GLM(y, np.ones_like(z), family=sm.families.Binomial(), offset=z).fit().params[0]
        return round(float(inter), 3), round(float(slope), 3)
    except Exception:
        return None, None


def metrics(y, p, boot=0, rng=None):
    y, p = np.asarray(y), np.asarray(p)
    yh = (p >= 0.5).astype(int)
    tn, fp, fn, tp = confusion_matrix(y, yh, labels=[0, 1]).ravel()
    two = len(set(y)) == 2
    m = dict(n=int(len(y)), prev=round(float(y.mean()), 3),
             auc=round(float(roc_auc_score(y, p)), 3) if two else None,
             brier=round(float(brier_score_loss(y, p)), 3),
             sens=round(float(tp / max(tp + fn, 1)), 3), spec=round(float(tn / max(tn + fp, 1)), 3))
    m["cal_intercept"], m["cal_slope"] = calib(y, p) if two else (None, None)
    if boot and two:
        a = []
        for _ in range(boot):
            i = rng.integers(0, len(y), len(y))
            if y[i].min() != y[i].max():
                a.append(roc_auc_score(y[i], p[i]))
        m["auc_ci"] = [round(float(v), 3) for v in np.percentile(a, [2.5, 97.5])]
    return m


def net_benefit(y, q, t):
    return float(((q >= t) & (y == 1)).mean() - ((q >= t) & (y == 0)).mean() * t / (1 - t))


def decision_curve(y, p, padj):
    prev = y.mean()
    return dict(t=[round(float(t), 2) for t in THRESHOLDS],
                raw=[net_benefit(y, p, t) for t in THRESHOLDS],
                adjusted=[net_benefit(y, padj, t) for t in THRESHOLDS],
                all=[float(prev - (1 - prev) * t / (1 - t)) for t in THRESHOLDS])


def update_study(y, p, rng):
    z, out = logit(p), {}
    for n in (10, 20, 40, 80):
        if n > len(y) * 0.6:
            continue
        b = [[], [], []]
        for _ in range(100):
            i = rng.choice(len(y), n, replace=False)
            r = np.setdiff1d(np.arange(len(y)), i)
            if y[i].min() == y[i].max():
                continue
            try:
                a = sm.GLM(y[i], np.ones(n), family=sm.families.Binomial(), offset=z[i]).fit().params[0]
                c = sm.Logit(y[i], sm.add_constant(z[i])).fit(disp=0).params
            except Exception:
                continue
            b[0].append(brier_score_loss(y[r], p[r]))
            b[1].append(brier_score_loss(y[r], sig(z[r] + a)))
            b[2].append(brier_score_loss(y[r], sig(c[0] + c[1] * z[r])))
        if b[0]:
            out[str(n)] = [round(float(np.mean(v)), 4) for v in b]
    return out


def verdicts(internal_auc, external):
    res = []
    for site, m in external.items():
        v = []
        if m["auc"] is not None and internal_auc - m["auc"] > 0.08:
            v.append("ranking degraded: consider redeveloping the model")
        if m["cal_intercept"] is not None and abs(m["cal_intercept"]) > 0.5:
            v.append("baseline risk shifted: update the intercept")
        if m["cal_slope"] is not None and not 0.8 <= m["cal_slope"] <= 1.2:
            v.append("predictions over- or under-confident: update the slope")
        res.append(dict(site=site, level="warn" if v else "ok", status="; ".join(v) if v else "transports acceptably"))
    return res


def analyze(df, target, site_col, dev_site, group_col=None, name="Analysis"):
    rng = np.random.default_rng(SEED)
    yv = pd.to_numeric(df[target], errors="coerce")
    df = df[yv.notna()].copy()
    df["_y"] = (yv[df.index] > 0).astype(int)
    df[site_col] = df[site_col].astype(str)
    dev_site = str(dev_site)
    if dev_site not in set(df[site_col]):
        raise ValueError("Development site not found in the site column.")
    dev = df[df[site_col] == dev_site]
    ext = {s: d for s, d in df.groupby(site_col) if s != dev_site}
    if not ext or dev["_y"].nunique() < 2:
        raise ValueError("Need a development site with both outcomes and at least one other site.")
    feats = [c for c in df.columns if c not in (target, site_col, "_y")]
    feats = [c for c in feats if dev[c].notna().any() and not (df[c].dtype == object and df[c].nunique() > 20)]
    sites = {dev_site: dev, **ext}
    portable = [c for c in feats if all(d[c].isna().mean() <= MAX_MISSING for d in sites.values())]
    if not portable:
        raise ValueError("No feature is available at every site; nothing portable to evaluate.")

    def types(cols):
        cat = [c for c in cols if df[c].dtype == object or df[c].nunique() <= 5]
        return [c for c in cols if c not in cat], cat

    specs = {"logistic_full": (feats, "logistic"), "logistic_portable": (portable, "logistic"),
             "forest_portable": (portable, "forest")}
    rep = dict(meta=dict(name=name, target=target, site_col=site_col, dev_site=dev_site, group_col=group_col,
                         features=feats, portable=portable, dropped=[c for c in feats if c not in portable]),
               sites={}, internal={}, external={}, calib={}, dca={}, update={}, adjusted={}, subgroup={})
    for s, d in sites.items():
        rep["sites"][s] = dict(n=len(d), prev=round(float(d["_y"].mean()) * 100, 1),
                               missing={c: round(float(d[c].isna().mean() * 100), 1) for c in feats})
    final = {}
    for k, (cols, kind) in specs.items():
        num, cat = types(cols)
        oof, cnt = np.zeros(len(dev)), np.zeros(len(dev))
        cv = RepeatedStratifiedKFold(n_splits=5, n_repeats=3, random_state=SEED)
        for tr, te in cv.split(dev[cols], dev["_y"]):
            m = build(num, cat, kind).fit(dev.iloc[tr][cols], dev["_y"].iloc[tr])
            oof[te] += m.predict_proba(dev.iloc[te][cols])[:, 1]
            cnt[te] += 1
        rep["internal"][k] = metrics(dev["_y"].values, oof / cnt, boot=300, rng=rng)
        final[k] = build(num, cat, kind).fit(dev[cols], dev["_y"])
        rep["external"][k] = {s: metrics(d["_y"].values, final[k].predict_proba(d[cols])[:, 1], boot=300, rng=rng)
                              for s, d in ext.items()}
    dev_prev = float(dev["_y"].mean())
    pool_p, pool_d = [], []
    for s, d in ext.items():
        y = d["_y"].values
        p = final["logistic_portable"].predict_proba(d[portable])[:, 1]
        padj = sig(logit(p) + logit(y.mean()) - logit(dev_prev))
        pool_p.append(p)
        pool_d.append(d)
        if len(set(y)) == 2:
            fy, fx = calibration_curve(y, p, n_bins=5, strategy="quantile")
            rep["calib"][s] = dict(x=[round(float(v), 3) for v in fx], y=[round(float(v), 3) for v in fy])
        rep["dca"][s] = decision_curve(y, p, padj)
        rep["adjusted"][s] = dict(raw=round(float(brier_score_loss(y, p)), 3), adj=round(float(brier_score_loss(y, padj)), 3))
        rep["update"][s] = update_study(y, p, rng)
    if group_col and group_col in df.columns:
        pool = pd.concat(pool_d)
        pp = np.concatenate(pool_p)
        for g in pool[group_col].astype(str).value_counts().index[:6]:
            mask = (pool[group_col].astype(str) == g).values
            if mask.sum() >= 10:
                rep["subgroup"][g] = metrics(pool["_y"].values[mask], pp[mask])
    rep["verdicts"] = verdicts(rep["internal"]["logistic_portable"]["auc"], rep["external"]["logistic_portable"])
    return rep
