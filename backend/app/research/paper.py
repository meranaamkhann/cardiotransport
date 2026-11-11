PAPER_INTERNAL = {
    "full_logistic": {"auc": 0.913, "brier": 0.114, "cal_slope": 0.935, "sensitivity": 0.806, "specificity": 0.902},
    "portable_logistic": {"auc": 0.875, "brier": 0.143, "cal_slope": 0.972, "sensitivity": 0.755, "specificity": 0.841},
    "full_forest": {"auc": 0.908, "brier": 0.125, "cal_slope": 1.579, "sensitivity": 0.791, "specificity": 0.872},
    "portable_forest": {"auc": 0.867, "brier": 0.151, "cal_slope": 1.507, "sensitivity": 0.719, "specificity": 0.841},
}

PAPER_EXTERNAL = {
    "portable_logistic": {
        "Hungary": {"auc": 0.877, "brier": 0.135, "sensitivity": 0.783, "specificity": 0.814},
        "Switzerland": {"auc": 0.766, "brier": 0.267, "sensitivity": 0.609, "specificity": 0.625, "cal_intercept": 2.968},
        "Long Beach VA": {"auc": 0.722, "brier": 0.188, "sensitivity": 0.785, "specificity": 0.529, "cal_slope": 0.488},
    },
    "portable_forest": {
        "Hungary": {"auc": 0.890, "brier": 0.131, "sensitivity": 0.717, "specificity": 0.894},
        "Switzerland": {"auc": 0.767, "brier": 0.198, "sensitivity": 0.626, "specificity": 0.625},
        "Long Beach VA": {"auc": 0.749, "brier": 0.186, "sensitivity": 0.779, "specificity": 0.549},
    },
}

PAPER_POOLED = {"portable_logistic": {"auc": 0.815, "sensitivity": 0.730, "specificity": 0.749, "brier": 0.179}}

NAMES = {"auc": "AUC", "brier": "Brier", "cal_slope": "calibration slope", "cal_intercept": "calibration intercept",
         "sensitivity": "sensitivity", "specificity": "specificity"}


def compare(models: dict) -> list:
    rows = []

    def add(label, paper, found):
        if paper is None or found is None:
            return
        rows.append({"label": label, "paper": paper, "reproduced": found, "difference": round(found - paper, 3)})

    for name, values in PAPER_INTERNAL.items():
        if name in models:
            for key, paper in values.items():
                add(f"{name.replace('_', ' ')} · Cleveland (cross-validated) · {NAMES[key]}", paper, models[name]["internal"].get(key))
    for name, sites in PAPER_EXTERNAL.items():
        if name in models:
            for site, values in sites.items():
                for key, paper in values.items():
                    add(f"{name.replace('_', ' ')} · {site} · {NAMES[key]}", paper, models[name]["external"].get(site, {}).get(key))
    for name, values in PAPER_POOLED.items():
        if name in models:
            for key, paper in values.items():
                add(f"{name.replace('_', ' ')} · pooled external · {NAMES[key]}", paper, models[name]["pooled_external"].get(key))
    return rows
