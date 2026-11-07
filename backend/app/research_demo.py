import numpy as np
import pandas as pd
from .research_engine import sig

UCI = "https://archive.ics.uci.edu/ml/machine-learning-databases/heart-disease/processed."
HEART = {"Cleveland": "cleveland", "Hungary": "hungarian", "Switzerland": "switzerland", "Long Beach VA": "va"}
COLS = "age sex cp trestbps chol fbs restecg thalach exang oldpeak slope ca thal num".split()


def synthetic(seed=3):
    rng = np.random.default_rng(seed)
    frames = []
    for site, n, shift, miss, scale in [("Hospital A", 700, 0.0, 0.0, 1.0), ("Hospital B", 400, -0.9, 0.05, 0.9),
                                        ("Hospital C", 250, 1.7, 0.4, 0.6), ("Hospital D", 300, 0.4, 0.1, 1.0)]:
        age, sbp = rng.normal(58, 11, n), rng.normal(132, 18, n)
        chol, hr = rng.normal(210, 40, n), rng.normal(140, 22, n)
        smoker, sex = rng.integers(0, 2, n), rng.integers(0, 2, n)
        st, marker = rng.gamma(1.5, 0.6, n), rng.normal(0, 1, n)
        lp = -6.6 + 0.045 * age + 0.012 * sbp + 0.004 * chol - 0.01 * hr + 0.5 * smoker + 0.7 * st + 0.9 * marker
        y = (rng.random(n) < sig(scale * lp + shift)).astype(int)
        d = pd.DataFrame(dict(site=site, outcome=y, age=age, sex=sex, sbp=sbp, cholesterol=chol, max_hr=hr,
                              smoker=smoker, st_depression=st, biomarker=marker))
        d.loc[rng.random(n) < miss, "biomarker"] = np.nan
        frames.append(d)
    return pd.concat(frames, ignore_index=True), dict(
        name="Synthetic multi-hospital demo", target="outcome", site_col="site", dev_site="Hospital A", group_col="sex")

