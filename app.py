import json
import os
import uuid
import pandas as pd
from flask import Flask, abort, redirect, render_template, request
import core
import demo

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 25 * 1024 * 1024
STORE = os.environ.get("REPORTS", "reports")
os.makedirs(STORE, exist_ok=True)


def save(rep):
    rid = uuid.uuid4().hex[:10]
    with open(f"{STORE}/{rid}.json", "w") as f:
        json.dump(rep, f)
    return rid


def recent():
    files = sorted(os.listdir(STORE), key=lambda f: os.path.getmtime(f"{STORE}/{f}"), reverse=True)[:8]
    return [(f[:-5], json.load(open(f"{STORE}/{f}"))["meta"]["name"]) for f in files if f.endswith(".json")]


@app.route("/")
def index():
    return render_template("index.html", recent=recent(), error=request.args.get("error"))


@app.route("/analyze", methods=["POST"])
def analyze():
    try:
        df = pd.read_csv(request.files["file"])
        f = request.form
        rep = core.analyze(df, f["target"], f["site_col"], f["dev_site"], f.get("group_col") or None,
                           request.files["file"].filename)
    except Exception as e:
        return redirect(f"/?error={str(e)[:160]}")
    return redirect(f"/report/{save(rep)}")


@app.route("/demo/<name>")
def run_demo(name):
    if name not in demo.DEMOS:
        abort(404)
    try:
        df, cfg = demo.DEMOS[name]()
        rep = core.analyze(df, **cfg)
    except Exception as e:
        return redirect(f"/?error={str(e)[:160]}")
    return redirect(f"/report/{save(rep)}")


@app.route("/report/<rid>")
def report(rid):
    if not rid.isalnum():
        abort(404)
    try:
        with open(f"{STORE}/{rid}.json") as f:
            return render_template("report.html", r=json.load(f))
    except FileNotFoundError:
        abort(404)


if __name__ == "__main__":
    app.run(port=int(os.environ.get("PORT", 5000)), debug=True)
