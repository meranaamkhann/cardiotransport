import csv
import hashlib
import io
from datetime import datetime
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

TEAL = colors.HexColor("#0f766e")
DISCLAIMER = ("CardioLens is an educational research platform. It does not diagnose heart disease and does not replace "
              "a clinician. In an emergency call your local emergency number.")


def csv_safe(value):
    text = "" if value is None else str(value)
    return "'" + text if text[:1] in ("=", "+", "-", "@", "\t", "\r") else text


def to_csv(header, rows) -> str:
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(header)
    for row in rows:
        writer.writerow([csv_safe(v) for v in row])
    return buffer.getvalue()


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def styles():
    base = getSampleStyleSheet()
    return {
        "title": ParagraphStyle("t", parent=base["Title"], textColor=TEAL, fontSize=20, alignment=0, spaceAfter=4),
        "h": ParagraphStyle("h", parent=base["Heading2"], textColor=TEAL, fontSize=13, spaceBefore=12, spaceAfter=4),
        "p": ParagraphStyle("p", parent=base["BodyText"], fontSize=10, leading=14),
        "small": ParagraphStyle("s", parent=base["BodyText"], fontSize=8.5, leading=11, textColor=colors.HexColor("#55707a")),
        "tag": ParagraphStyle("g", parent=base["BodyText"], fontSize=8.5, textColor=colors.HexColor("#92400e")),
    }


def table(rows, widths=None):
    t = Table([[Paragraph(escape(str(c)), styles()["p"]) for c in r] for r in rows], colWidths=widths)
    t.setStyle(TableStyle([("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#d9e3e5")),
                           ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#f4f7f7")),
                           ("VALIGN", (0, 0), (-1, -1), "TOP")]))
    return t


def build(story) -> bytes:
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, leftMargin=18 * mm, rightMargin=18 * mm, topMargin=16 * mm,
                            bottomMargin=16 * mm, title="CardioLens report")
    doc.build(story)
    return buffer.getvalue()


def label(text, st):
    return Paragraph(escape(text), st["tag"])


def assessment_pdf(a, patient, reviewer, summary) -> bytes:
    st = styles()
    story = [Paragraph("CardioLens assessment report", st["title"]),
             Paragraph(escape(f"Patient: {patient.full_name} · Assessment #{a.id} · {a.kind} · "
                              f"{a.created_at:%d %b %Y %H:%M} UTC"), st["small"]), Spacer(1, 6)]
    story.append(Paragraph("1. Patient-reported information", st["h"]))
    story.append(label("Source: entered by the patient", st))
    rows = [[k.replace("_", " ").capitalize(), v if not isinstance(v, (list, dict)) else ", ".join(map(str, v)) or "none"]
            for k, v in a.inputs.items()]
    story.append(table(rows, [55 * mm, 110 * mm]))
    story.append(Paragraph("2. Model-generated information", st["h"]))
    result = a.result
    if a.kind == "symptom":
        tri = result["triage"]
        story.append(label("Source: rule-based symptom triage (not a diagnosis)", st))
        story.append(Paragraph(escape(f"{tri['title']}. {tri['message']}"), st["p"]))
        for r in tri["reasons"]:
            story.append(Paragraph("• " + escape(r), st["p"]))
        model = result.get("model")
        story.append(Spacer(1, 6))
        if model:
            story.append(label("Source: research model trained on historical angiography records (not clinically validated)", st))
            o = model["observed"]
            rate = "n/a" if o["rate"] is None else f"{round(o['rate'] * 100)}%"
            story.append(Paragraph(escape(f"Band: {model['headline']}. In the reference records {o['n']} people landed in this band and about {rate} had significant artery blockage on angiography. Model confidence: {model['confidence']['level']}."), st["p"]))
            if model["drivers"]["up"]:
                story.append(Paragraph("Pushed the estimate up: " + escape(", ".join(d["label"] for d in model["drivers"]["up"])), st["p"]))
            if model["drivers"]["down"]:
                story.append(Paragraph("Pulled it down: " + escape(", ".join(d["label"] for d in model["drivers"]["down"])), st["p"]))
        else:
            story.append(Paragraph(escape(result["model_note"] or ""), st["p"]))
        story.append(Spacer(1, 6))
        story.append(Paragraph(escape(f"Final guidance: {result['final']['title']}. {result['final']['message']}"), st["p"]))
    else:
        story.append(label("Source: guideline-threshold risk-factor review (not a prediction or diagnosis)", st))
        story.append(Paragraph(escape(result["headline"]), st["p"]))
        rows = [[f["label"], f["value"], f["status"], f["detail"]] for f in result["factors"]]
        story.append(table([["Factor", "Value", "Status", "Note"]] + rows, [38 * mm, 28 * mm, 22 * mm, 77 * mm]))
    story.append(Paragraph("3. Clinician review", st["h"]))
    if a.status == "reviewed" and reviewer is not None:
        story.append(label("Source: written by a clinician", st))
        story.append(Paragraph(escape(f"Reviewed by {reviewer.full_name} on {a.reviewed_at:%d %b %Y}"), st["small"]))
        story.append(Paragraph(escape(summary or ""), st["p"]))
    else:
        story.append(Paragraph("This assessment has not been reviewed by a clinician.", st["p"]))
    story.append(Spacer(1, 14))
    story.append(Paragraph(escape(DISCLAIMER), st["small"]))
    return build(story)


def pct(v):
    return "n/a" if v is None else f"{v:.3f}"


def experiment_pdf(exp, owner_name) -> bytes:
    st = styles()
    result = exp.result or {}
    meta = result.get("meta", {})
    story = [Paragraph("CardioLens research report", st["title"]),
             Paragraph(escape(f"{exp.name} · experiment #{exp.id} · {owner_name} · {exp.created_at:%d %b %Y}"), st["small"]),
             Spacer(1, 6)]
    story.append(Paragraph("Provenance", st["h"]))
    story.append(table([["Type", meta.get("provenance_label", exp.provenance)],
                        ["Data source", meta.get("data_source", "")],
                        ["Development cohort", meta.get("dev_site", "")],
                        ["Zero cholesterol / blood pressure", "recoded as missing" if meta.get("recode_zeros") else "kept as recorded (as in the paper)"],
                        ["Bootstrap resamples", meta.get("bootstrap", "")],
                        ["Cross-validation", f"{meta.get('folds', '')}-fold x {meta.get('repeats', '')} repeats"]],
                       [55 * mm, 110 * mm]))
    story.append(Paragraph("Internal and external discrimination (AUC, 95% CI)", st["h"]))
    rows = [["Model", "Internal", *result.get("sites_external", [])]]
    for name, m in result.get("models", {}).items():
        row = [name.replace("_", " "), f"{pct(m['internal']['auc'])}"]
        for s in result.get("sites_external", []):
            e = m["external"][s]
            ci = e["auc_ci"]
            row.append(f"{pct(e['auc'])}" + (f" ({ci[0]:.3f}-{ci[1]:.3f})" if ci else ""))
        rows.append(row)
    story.append(table(rows))
    story.append(Paragraph("Calibration and Brier score on external cohorts", st["h"]))
    rows = [["Model", "Cohort", "Brier", "Cal. intercept", "Cal. slope"]]
    for name, m in result.get("models", {}).items():
        for s, e in m["external"].items():
            rows.append([name.replace("_", " "), s, pct(e["brier"]), e["cal_intercept"], e["cal_slope"]])
    story.append(table(rows))
    cmp = result.get("comparison_with_paper")
    if cmp:
        story.append(Paragraph("Comparison with values reported in the paper", st["h"]))
        rows = [["Quantity", "Paper", "This run", "Difference"]]
        for c in cmp:
            rows.append([c["label"], c["paper"], c["reproduced"], c["difference"]])
        story.append(table(rows))
    story.append(Paragraph("Notes", st["h"]))
    for note in result.get("notes", []):
        story.append(Paragraph("• " + escape(note), st["p"]))
    story.append(Spacer(1, 12))
    story.append(Paragraph(escape(DISCLAIMER), st["small"]))
    return build(story)


def experiment_csv(exp) -> str:
    result = exp.result or {}
    rows = []
    for name, m in result.get("models", {}).items():
        rows.append([name, "internal", "Development cohort", *[m["internal"].get(k) for k in CSV_KEYS]])
        for s, e in m["external"].items():
            rows.append([name, "external", s, *[e.get(k) for k in CSV_KEYS]])
        pooled = m.get("pooled_external")
        if pooled:
            rows.append([name, "external", "Pooled external", *[pooled.get(k) for k in CSV_KEYS]])
    return to_csv(["model", "evaluation", "cohort", *CSV_KEYS], rows)


CSV_KEYS = ["n", "events", "prevalence", "auc", "average_precision", "brier", "sensitivity", "specificity",
            "precision", "f1", "balanced_accuracy", "cal_intercept", "cal_slope"]
