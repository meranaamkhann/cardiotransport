from functools import lru_cache

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


def test_web_flow(tmp_path, monkeypatch):
    monkeypatch.setenv("REPORTS", str(tmp_path))
    import app as web
    web.STORE = str(tmp_path)
    c = web.app.test_client()
    rid = web.save(run())
    page = c.get(f"/report/{rid}")
    assert page.status_code == 200 and b"Hospital C" in page.data
    assert c.get("/").status_code == 200
    assert c.get("/report/nope").status_code == 404
