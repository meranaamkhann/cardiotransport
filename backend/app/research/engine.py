import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import RandomForestClassifier
from sklearn.impute import SimpleImputer
from sklearn.inspection import permutation_importance
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import RepeatedStratifiedKFold
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

from . import metrics as M


def make_pipeline(numeric, categorical, kind, seed):
    pre = ColumnTransformer(
        [("num", Pipeline([("imp", SimpleImputer(strategy="median")), ("sc", StandardScaler())]), numeric),
         ("cat", Pipeline([("imp", SimpleImputer(strategy="most_frequent")),
                           ("oh", OneHotEncoder(handle_unknown="ignore", sparse_output=False))]), categorical)],
        sparse_threshold=0)
    if kind == "logistic":
        clf = LogisticRegression(penalty="l2", C=1.0, max_iter=5000)
    else:
        clf = RandomForestClassifier(n_estimators=500, max_depth=5, min_samples_leaf=5, max_features="sqrt",
                                     random_state=seed, n_jobs=-1)
    return Pipeline([("pre", pre), ("clf", clf)])


def split_types(features, types):
    return [f for f in features if types[f] == "numeric"], [f for f in features if types[f] == "categorical"]


def group_of(column):
    body = column.split("__", 1)[1]
    return body.rsplit("_", 1)[0] if column.startswith("cat__") else body


def interpret(model, kind, features, external_pooled, seed):
    pre, clf = model.named_steps["pre"], model.named_steps["clf"]
    names = list(pre.get_feature_names_out())
    if kind == "logistic":
        return {"method": "standardised log-odds coefficients; they describe associations, not causes",
                "coefficients": [{"term": n.split("__", 1)[1], "feature": group_of(n), "value": M.rnd(c)}
                                 for n, c in zip(names, clf.coef_[0])]}
    grouped = {}
    for n, v in zip(names, clf.feature_importances_):
        grouped[group_of(n)] = grouped.get(group_of(n), 0.0) + float(v)
    out = {"method": "impurity importance on the development cohort and permutation importance on pooled external records; neither implies causation",
           "impurity": [{"feature": f, "value": M.rnd(v)} for f, v in sorted(grouped.items(), key=lambda kv: -kv[1])]}
    X, y = external_pooled
    if len(set(y.tolist())) == 2:
        perm = permutation_importance(model, X[features], y, scoring="roc_auc", n_repeats=5, random_state=seed)
        out["permutation"] = [{"feature": f, "value": M.rnd(m), "sd": M.rnd(s)}
                              for f, m, s in sorted(zip(features, perm.importances_mean, perm.importances_std),
                                                    key=lambda t: -t[1])]
    return out


def run_validation(frame, specs, types, dev_site, *, folds=5, repeats=10, bootstrap=2000, seed=20260904,
                   group_column=None, progress=None, recalibrate=("portable_logistic", "portable_forest"),
                   subgroup_model="portable_logistic", max_missing=0.30):
    rng = np.random.default_rng(seed)
    report = progress or (lambda fraction, message: None)
    dev = frame[frame["site"] == dev_site].reset_index(drop=True)
    external = {s: frame[frame["site"] == s].reset_index(drop=True) for s in pd.unique(frame["site"]) if s != dev_site}
    sites = {dev_site: dev, **external}
    all_features = sorted({f for cols, _ in specs.values() for f in cols}, key=lambda f: list(types).index(f))
    out = {"sites_external": list(external), "dev_site": dev_site, "models": {}, "recalibration": {}}
    out["cohorts"] = {s: {"n": int(len(d)), "events": int(d["target"].sum()), "prevalence": M.rnd(d["target"].mean())}
                      for s, d in sites.items()}
    out["missingness"] = {s: {f: M.rnd(d[f].isna().mean() * 100, 1) for f in all_features} for s, d in sites.items()}
    out["availability"] = {f: {"worst_missing_pct": max(out["missingness"][s][f] for s in sites),
                               "portable": all(d[f].isna().mean() <= max_missing for d in sites.values())}
                           for f in all_features}
    out["features"] = all_features

    ext_all = pd.concat(list(external.values()), ignore_index=True)
    fitted, oof_store, ext_pred = {}, {}, {}
    steps = len(specs)
    for index, (name, (cols, kind)) in enumerate(specs.items()):
        numeric, categorical = split_types(cols, types)
        base = 0.05 + 0.75 * index / steps
        span = 0.75 / steps
        oof, count = np.zeros(len(dev)), np.zeros(len(dev))
        cv = RepeatedStratifiedKFold(n_splits=folds, n_repeats=repeats, random_state=seed)
        total = folds * repeats
        for step, (train, test) in enumerate(cv.split(dev[cols], dev["target"])):
            model = make_pipeline(numeric, categorical, kind, seed).fit(dev.iloc[train][cols], dev["target"].iloc[train])
            oof[test] += model.predict_proba(dev.iloc[test][cols])[:, 1]
            count[test] += 1
            if step % 5 == 0:
                report(base + span * 0.6 * step / total, f"Cross-validating {name.replace('_', ' ')}")
        oof /= count
        final = make_pipeline(numeric, categorical, kind, seed).fit(dev[cols], dev["target"])
        fitted[name], oof_store[name] = final, oof
        report(base + span * 0.65, f"Validating {name.replace('_', ' ')} on external cohorts")
        y_dev = dev["target"].values
        entry = {"features": cols, "kind": kind, "internal": M.metric_set(y_dev, oof, rng, bootstrap),
                 "external": {}, "roc": {}, "calibration": {}, "dca": {}}
        entry["roc"][f"{dev_site} (cross-validated)"] = M.roc_points(y_dev, oof)
        entry["calibration"][f"{dev_site} (cross-validated)"] = M.calibration_bins(y_dev, oof)
        pooled_p = []
        dev_prev = float(y_dev.mean())
        for site, part in external.items():
            y = part["target"].values
            p = final.predict_proba(part[cols])[:, 1]
            pooled_p.append(p)
            entry["external"][site] = M.metric_set(y, p, rng, bootstrap)
            entry["roc"][site] = M.roc_points(y, p)
            entry["calibration"][site] = M.calibration_bins(y, p)
            adjusted = M.sig(M.logit(p) + M.logit(np.array(y.mean())) - M.logit(np.array(dev_prev)))
            entry["dca"][site] = M.decision_curve(y, p, adjusted)
        ext_p = np.concatenate(pooled_p)
        ext_pred[name] = ext_p
        y_ext = ext_all["target"].values
        entry["pooled_external"] = M.metric_set(y_ext, ext_p, rng, bootstrap)
        entry["roc"]["Pooled external"] = M.roc_points(y_ext, ext_p)
        entry["interpretability"] = interpret(final, kind, cols, (ext_all, y_ext), seed)
        out["models"][name] = entry

    report(0.84, "Recalibration experiments")
    for name in recalibrate:
        if name not in out["models"]:
            continue
        cols = specs[name][0]
        rows = {}
        dev_prev = float(dev["target"].mean())
        for site, part in external.items():
            y = part["target"].values
            p = fitted[name].predict_proba(part[cols])[:, 1]
            adjusted = M.sig(M.logit(p) + M.logit(np.array(y.mean())) - M.logit(np.array(dev_prev)))
            rows[site] = {"prevalence_adjusted": {"brier_before": M.rnd(M.brier(y, p), 4),
                                                  "brier_after": M.rnd(M.brier(y, adjusted), 4),
                                                  "note": "uses the site's observed prevalence, so it is an upper bound on what a real deployment can know"},
                          "update_study": M.update_study(y, p, rng), "full_update": M.full_update(y, p)}
        out["recalibration"][name] = rows

    report(0.93, "Subgroup analysis")
    out["subgroup"] = {"model": subgroup_model, "column": group_column, "rows": []}
    if group_column and subgroup_model in specs:
        cols = specs[subgroup_model][0]
        groups = {"Development": (dev, oof_store[subgroup_model]), "External pooled": (ext_all, ext_pred[subgroup_model])}
        for label, (data, preds) in groups.items():
            for g in data[group_column].dropna().astype(str).value_counts().index[:6]:
                mask = (data[group_column].astype(str) == g).values
                if mask.sum() < 10:
                    continue
                y = data["target"].values[mask]
                m = M.metric_set(y, preds[mask], rng, min(bootstrap, 1000))
                out["subgroup"]["rows"].append({"evaluation": label, "group": g, "n": m["n"], "events": m["events"],
                                                "auc": m["auc"], "auc_ci": m["auc_ci"],
                                                "sensitivity": m["sensitivity"], "specificity": m["specificity"]})
    reference = "portable_logistic" if "portable_logistic" in out["models"] else next(iter(out["models"]))
    out["verdicts"] = M.verdicts(out["models"][reference]["internal"]["auc"], out["models"][reference]["external"])
    out["verdict_model"] = reference
    report(0.98, "Finalising")
    return out
