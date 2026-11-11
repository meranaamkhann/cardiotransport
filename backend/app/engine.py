import json
from pathlib import Path

import joblib
import numpy as np
import pandas as pd

from .features import CLINICAL, DEPLOY, LABELS
from .schemas import Assessment

CHEST_PAIN = {"typical": 1.0, "atypical": 2.0, "non_anginal": 3.0, "none": 4.0}
ECG = {"normal": 0.0, "st_t_abnormality": 1.0, "lv_hypertrophy": 2.0}
ORDER = {"lower": 0, "moderate": 1, "higher": 2}
BAND_TEXT = {
    "lower": ("Lower concern",
              "Your answers look more like patients who turned out not to have significant artery blockage.",
              "This is not an all-clear. Mention your symptoms and numbers at your next routine check-up, and seek care sooner if anything changes."),
    "moderate": ("Worth getting checked",
                 "Your answers sit in the middle: some patients with similar answers had significant blockage and many did not.",
                 "Book a doctor visit in the next few weeks and ask whether an ECG or a stress test makes sense."),
    "higher": ("See a doctor soon",
               "Your answers look more like patients who were found to have significant artery blockage.",
               "Arrange a medical review within days, ideally with a cardiologist. If symptoms worsen, treat it as an emergency."),
}
NEXT_STEPS = [
    "Take this summary to your doctor; the list of what you entered is on the page.",
    "Ask about a resting ECG, an exercise stress test, and a lipid and blood sugar profile.",
    "Write down when the symptoms happen, how long they last, and what eases them.",
]
EMERGENCY_TEXT = ("Your answers include warning signs that can mean a heart attack. Call your local emergency number now "
                  "(112 in India, 911 in the US, 999 in the UK) and do not drive yourself. This tool is not a substitute for emergency care.")


def sigmoid(z):
    return float(1 / (1 + np.exp(-np.clip(z, -30, 30))))


def strength(value):
    size = abs(value)
    return "strong" if size >= 0.6 else "moderate" if size >= 0.2 else "slight"


class Engine:
    def __init__(self, artifact_dir: Path):
        bundle = joblib.load(artifact_dir / "models.joblib")
        self.pipelines = bundle["pipelines"]
        self.means = bundle["means"]
        self.forests = bundle.get("forests", {})
        self.bootstrap = bundle.get("bootstrap", {})
        self.card = json.loads((artifact_dir / "model_card.json").read_text())
        self.groups = {}
        for tier, pipe in self.pipelines.items():
            names = pipe.named_steps["pre"].get_feature_names_out()
            self.groups[tier] = [n.split("__", 1)[1].rsplit("_", 1)[0] if n.startswith("cat__") else n.split("__", 1)[1]
                                 for n in names]

    def values(self, a: Assessment):
        nan = float("nan")
        return {
            "age": float(a.age),
            "sex": 1.0 if a.sex == "male" else 0.0,
            "cp": CHEST_PAIN[a.chest_pain],
            "exang": 1.0 if a.exercise_pain else 0.0,
            "trestbps": a.systolic if a.systolic is not None else nan,
            "chol": a.cholesterol if a.cholesterol is not None else nan,
            "fbs": nan if a.fasting_glucose is None else (1.0 if a.fasting_glucose > 120 else 0.0),
            "restecg": ECG[a.ecg] if a.ecg else nan,
            "thalach": a.max_hr if a.max_hr is not None else nan,
            "oldpeak": a.st_depression if a.st_depression is not None else nan,
        }

    def score_range(self, tier, xt):
        boot = self.bootstrap.get(tier)
        if not boot or len(boot["intercept"]) < 20:
            return None
        z = boot["intercept"] + boot["coef"] @ xt
        low, high = np.percentile(1 / (1 + np.exp(-np.clip(z, -30, 30))), [5, 95])
        return [int(round(low * 100)), int(round(high * 100))]

    def second_opinion(self, tier, row, tier_card, model_band):
        forest = self.forests.get(tier)
        cuts = tier_card.get("forest_bands")
        if forest is None or cuts is None:
            return None
        q = float(forest.predict_proba(row)[0, 1])
        band = "lower" if q < cuts["lower_cut"] else "moderate" if q < cuts["higher_cut"] else "higher"
        return {"band": band, "agrees": band == model_band, "score": int(round(q * 100)), "model": "random forest"}

    def readable(self, a: Assessment, features):
        pain = {"typical": "Typical angina pattern", "atypical": "Atypical angina pattern",
                "non_anginal": "Chest pain, not angina-like", "none": "No chest pain"}
        ecg = {"normal": "Normal", "st_t_abnormality": "ST-T wave abnormality", "lv_hypertrophy": "Left ventricular hypertrophy"}
        shown = {
            "age": f"{a.age} years",
            "sex": a.sex.capitalize(),
            "cp": pain[a.chest_pain],
            "exang": "Yes" if a.exercise_pain else "No",
            "trestbps": None if a.systolic is None else f"{a.systolic:g} mmHg",
            "chol": None if a.cholesterol is None else f"{a.cholesterol:g} mg/dL",
            "fbs": None if a.fasting_glucose is None else f"{a.fasting_glucose:g} mg/dL",
            "restecg": ecg.get(a.ecg) if a.ecg else None,
            "thalach": None if a.max_hr is None else f"{a.max_hr:g} bpm",
            "oldpeak": None if a.st_depression is None else f"{a.st_depression:g} mm",
        }
        return [{"label": LABELS[f], "value": shown[f] or "Not provided"} for f in features]

    def choose_tier(self, a: Assessment):
        return "clinical" if a.ecg and a.max_hr is not None and a.st_depression is not None else "core"

    def assess(self, a: Assessment):
        values = self.values(a)
        tier = self.choose_tier(a)
        features = DEPLOY[tier]
        row = pd.DataFrame([{f: values[f] for f in features}])
        pipe = self.pipelines[tier]
        clf = pipe.named_steps["clf"]
        xt = pipe.named_steps["pre"].transform(row)[0]
        z = float(clf.intercept_[0] + clf.coef_[0] @ xt)
        p = sigmoid(z)

        known = {f for f in features if not np.isnan(values[f])}
        contrib = clf.coef_[0] * (xt - self.means[tier])
        by_feature = {}
        for group, c in zip(self.groups[tier], contrib):
            by_feature[group] = by_feature.get(group, 0.0) + float(c)
        drivers = [{"feature": f, "label": LABELS[f], "effect": strength(v), "log_odds": round(v, 3)}
                   for f, v in by_feature.items() if f in known and abs(v) >= 0.05]
        up = sorted([d for d in drivers if d["log_odds"] > 0], key=lambda d: -d["log_odds"])[:4]
        down = sorted([d for d in drivers if d["log_odds"] < 0], key=lambda d: d["log_odds"])[:4]

        tier_card = self.card["deployment"][tier]
        bands = tier_card["bands"]
        model_band = "lower" if p < bands["lower_cut"] else "moderate" if p < bands["higher_cut"] else "higher"
        score_range = self.score_range(tier, xt)
        second = self.second_opinion(tier, row, tier_card, model_band)
        band, reason = model_band, None
        if a.emergency:
            band, reason = "higher", "You reported warning signs."
        elif a.pathway == "symptomatic" and (a.chest_pain == "typical" or a.exercise_pain) and ORDER[band] < 1:
            band, reason = "moderate", "Chest pain that comes on with effort should always be checked by a doctor."
        stats = bands["stats"][band]

        local = None
        for cal in a.local_calibrations:
            if cal.tier == tier:
                local = {"probability": round(sigmoid(cal.intercept + cal.slope * z), 3),
                         "label": cal.label or "your clinic", "n": cal.n}

        warnings = []
        reference = self.card["reference_ranges"]
        for feature, (low, high) in reference.items():
            v = values.get(feature)
            if v is not None and feature in features and not np.isnan(v) and not low <= v <= high:
                warnings.append(f"{LABELS[feature]} is outside the range most patients in the reference data fell in "
                                f"({low:g} to {high:g}), so the estimate is less reliable.")
        if self.card["data_source"] != "uci":
            warnings.append("This build uses demonstration data, not the real hospital records.")

        missing = [LABELS[f] for f in features if f not in known]
        wide = score_range is not None and score_range[1] - score_range[0] > 35
        disagree = second is not None and not second["agrees"]
        penalty = len(missing) + 2 * len([w for w in warnings if "outside" in w]) + int(wide) + int(disagree)
        level = "limited" if penalty >= 3 else "fair" if penalty >= 1 or tier == "core" else "good"
        reasons = []
        if missing:
            reasons.append("Not provided: " + ", ".join(m.lower() for m in missing) + ".")
        if tier == "core":
            reasons.append("No ECG or stress-test values were entered, so a simpler model was used.")
        if any("outside" in w for w in warnings):
            reasons.append("Some values are unusual compared with the reference data.")
        if wide:
            reasons.append("The score is uncertain: a different sample of patients could have moved it a lot.")
        if disagree:
            reasons.append("A second, differently built model placed you in another band.")
        site_min, site_max = stats["site_min"], stats["site_max"]

        title, summary, action = BAND_TEXT[band]
        return {
            "tier": tier,
            "band": band,
            "band_raised": band != model_band,
            "raised_reason": reason,
            "headline": title,
            "summary": summary,
            "action": action,
            "emergency": {"active": bool(a.emergency), "message": EMERGENCY_TEXT if a.emergency else None},
            "model_score": int(round(p * 100)),
            "score_range": score_range,
            "second_opinion": second,
            "local": local,
            "observed": {"n": stats["n"], "rate": stats["rate"], "ci": stats["ci"],
                         "site_min": site_min, "site_max": site_max},
            "drivers": {"up": up, "down": down},
            "confidence": {"level": level, "reasons": reasons},
            "warnings": warnings,
            "next_steps": NEXT_STEPS,
            "inputs": self.readable(a, features),
            "data_source": self.card["data_source"],
            "model_version": self.card["version"],
        }
