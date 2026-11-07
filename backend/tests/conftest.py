import pytest
from fastapi.testclient import TestClient

from app import data
from app.main import create_app
from app.training import train


@pytest.fixture(scope="session")
def client(tmp_path_factory):
    out = tmp_path_factory.mktemp("artifacts")
    frame, source, quality = data.load_cohorts(force_synthetic=True)
    train(frame, source, quality, out_dir=out, run_paper=False)
    return TestClient(create_app(out, out / "no-static"))
