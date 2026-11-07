import json
import os
import threading
import uuid
from urllib.parse import quote

import pandas as pd
from flask import Flask, abort, redirect, render_template, request, send_file, jsonify

import core
import demo

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 25 * 1024 * 1024
STORE = os.environ.get("REPORTS", "reports")
SHOW_RECENT = os.environ.get("SHOW_RECENT", "1") == "1"
JOBS = {}
os.makedirs(STORE, exist_ok=True)


def path(rid):
    return f"{STORE}/{rid}.json"


def submit(fn):
    rid = uuid.uuid4().hex[:10]
    JOBS[rid] = "running"

    def work():
        try:
            result = fn()
            with open(path(rid) + ".tmp", "w") as f:
                json.dump(result, f)
            os.replace(path(rid) + ".tmp", path(rid))
            JOBS[rid] = "done"
        except Exception as e:
            JOBS[rid] = "error: " + str(e)[:200]

    threading.Thread(target=work, daemon=True).start()
    return rid


def recent():
    if not SHOW_RECENT:
        return []
    files = sorted((f for f in os.listdir(STORE) if f.endswith(".json")),
                   key=lambda f: os.path.getmtime(f"{STORE}/{f}"), reverse=True)[:8]
    return [(f[:-5], json.load(open(f"{STORE}/{f}"))["meta"]["name"]) for f in files]


def fail(msg):
    return redirect("/?error=" + quote(msg[:200]))


def read_csv():
    try:
        return pd.read_csv(request.files["file"])
    except Exception:
        return None


@app.route("/")
def index():
    return render_template("index.html", recent=recent(), error=request.args.get("error"))


@app.route("/inspect", methods=["POST"])
def inspect():
    df = read_csv()
    if df is None or df.empty:
        abort(400)
    cols = []
    for c in df.columns:
        vals = df[c].dropna().unique()
        cols.append(dict(name=str(c), values=[str(v) for v in sorted(vals, key=str)][:40] if len(vals) <= 40 else None))
    return jsonify(columns=cols, rows=len(df))


@app.route("/analyze", methods=["POST"])
def analyze():
    df = read_csv()
    if df is None:
        return fail("That file could not be read as a CSV.")
    f = request.form
    name = request.files["file"].filename or "Uploaded data"
    group = f.get("group_col") or None
    for col in (f.get("target"), f.get("site_col")):
        if col not in df.columns:
            return fail(f"Column '{col}' not found.")
    return redirect("/report/" + submit(lambda: core.analyze(df, f["target"], f["site_col"], f["dev_site"], group, name)))


@app.route("/demo/<name>")
def run_demo(name):
    if name not in demo.DEMOS:
        abort(404)

    def job():
        df, cfg = demo.DEMOS[name]()
        return core.analyze(df, **cfg)

    return redirect("/report/" + submit(job))


@app.route("/report/<rid>")
def report(rid):
    if not rid.isalnum():
        abort(404)
    if os.path.exists(path(rid)):
        with open(path(rid)) as f:
            return render_template("report.html", r=json.load(f), rid=rid)
    state = JOBS.get(rid)
    if state == "running":
        return render_template("running.html")
    if state:
        return fail(state.replace("error: ", ""))
    abort(404)


@app.route("/report/<rid>/json")
def report_json(rid):
    if not rid.isalnum() or not os.path.exists(path(rid)):
        abort(404)
    return send_file(path(rid), mimetype="application/json", as_attachment=True, download_name=f"transportlab-{rid}.json")


if __name__ == "__main__":
    app.run(port=int(os.environ.get("PORT", 5000)), debug=os.environ.get("DEBUG") == "1")
