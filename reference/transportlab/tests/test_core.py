import io
import time
from functools import lru_cache

import pandas as pd
import pytest

import core
import demo


@lru_cache(maxsize=1)
def run():
    df, cfg = demo.synthetic()
    return core.analyze(df, **cfg)


def test_portable_excludes_sparse_feature():
    r = run()
    assert "biomarker" in r["meta"]["dropped"]
    assert "biomarker" not in r["meta"]["portable"]


def test_all_external_sites_evaluated():
    r = run()
    assert set(r["external"]["logistic_portable"]) == {"Hospital B", "Hospital C", "Hospital D"}


def test_shifted_site_is_flagged():
    r = run()
    status = {v["site"]: v for v in r["verdicts"]}
    assert status["Hospital C"]["level"] == "warn"


def test_prevalence_adjustment_helps_shifted_site():
    r = run()
    assert r["adjusted"]["Hospital C"]["adj"] <= r["adjusted"]["Hospital C"]["raw"]


def test_subgroups_present():
    assert run()["subgroup"]


def small():
    df, cfg = demo.synthetic()
    return df.groupby("site").head(150).reset_index(drop=True), cfg


def test_continuous_outcome_rejected():
    df, cfg = small()
    df["bad"] = df["age"]
    with pytest.raises(ValueError):
        core.analyze(df, **{**cfg, "target": "bad"})


def test_id_column_not_used_as_feature():
    df, cfg = small()
    df["patient_id"] = range(len(df))
    assert "patient_id" not in core.analyze(df, **cfg)["meta"]["features"]


def test_leakage_warning():
    df, cfg = small()
    df["leak"] = df["outcome"] * 5.0 + 0.01 * df["age"]
    assert any("leak" in w for w in core.analyze(df, **cfg)["warnings"])


def test_thin_site_flagged():
    df, cfg = small()
    keep = df[df.site != "Hospital D"]
    tiny = df[df.site == "Hospital D"].head(20)
    r = core.analyze(pd.concat([keep, tiny]), **cfg)
    assert {v["site"]: v for v in r["verdicts"]}["Hospital D"]["status"].startswith("too little")


def test_web_flow(tmp_path):
    import app as web
    web.STORE = str(tmp_path)
    c = web.app.test_client()
    df, cfg = small()
    raw = df.to_csv(index=False).encode()
    buf = io.BytesIO(raw)
    info = c.post("/inspect", data={"file": (buf, "d.csv")}).get_json()
    assert any(col["name"] == "site" for col in info["columns"])
    resp = c.post("/analyze", data={"file": (io.BytesIO(raw), "d.csv"), "target": "outcome", "site_col": "site",
                                    "dev_site": "Hospital A", "group_col": "sex"})
    rid = resp.headers["Location"].rsplit("/", 1)[1]
    for _ in range(120):
        page = c.get(f"/report/{rid}")
        if b"Running your analysis" not in page.data:
            break
        time.sleep(1)
    assert page.status_code == 200 and b"Hospital C" in page.data
    assert c.get(f"/report/{rid}/json").status_code == 200
    assert c.get("/report/missing").status_code == 404
    assert c.post("/analyze", data={"file": (io.BytesIO(b"a,b\n1,2\n"), "x.csv"), "target": "zz", "site_col": "b", "dev_site": "1"}).status_code == 302
