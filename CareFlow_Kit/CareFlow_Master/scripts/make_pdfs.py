# -*- coding: utf-8 -*-
"""Render the setup guide, project report and documentation to PDF (reportlab)."""
from pathlib import Path
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_LEFT
from reportlab.platypus import (SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
                                Preformatted, KeepTogether)
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
import sys, os
sys.path.insert(0, str(Path(__file__).resolve().parent))
from guide_content import GUIDE

ROOT = Path(__file__).resolve().parents[1]
NAVY = colors.HexColor("#0B5D7A"); TEAL = colors.HexColor("#17A2B8")
GREY = colors.HexColor("#5A6B78"); LINE = colors.HexColor("#CFE0E6")

F = "Helvetica"; FB = "Helvetica-Bold"; FM = "Courier"
base = "/usr/share/fonts/truetype/dejavu/"
if Path(base + "DejaVuSans.ttf").exists():
    pdfmetrics.registerFont(TTFont("DJV", base + "DejaVuSans.ttf"))
    pdfmetrics.registerFont(TTFont("DJV-B", base + "DejaVuSans-Bold.ttf"))
    pdfmetrics.registerFont(TTFont("DJV-M", base + "DejaVuSansMono.ttf"))
    F, FB, FM = "DJV", "DJV-B", "DJV-M"

ss = getSampleStyleSheet()
S = {
 "h1": ParagraphStyle("h1", fontName=FB, fontSize=19, leading=23, textColor=NAVY, spaceAfter=2, alignment=TA_LEFT),
 "h2": ParagraphStyle("h2", fontName=FB, fontSize=12.5, leading=16, textColor=NAVY, spaceBefore=12, spaceAfter=4, leftIndent=6, borderPadding=0),
 "h3": ParagraphStyle("h3", fontName=FB, fontSize=11, leading=14, textColor=colors.HexColor("#12607D"), spaceBefore=8, spaceAfter=3),
 "p":  ParagraphStyle("p", fontName=F, fontSize=9.6, leading=13.4, textColor=colors.HexColor("#12212E"), spaceAfter=4),
 "small": ParagraphStyle("small", fontName=F, fontSize=8.4, leading=11, textColor=GREY, spaceAfter=6),
 "code": ParagraphStyle("code", fontName=FM, fontSize=7.9, leading=10.4, textColor=colors.HexColor("#12212E")),
 "li": ParagraphStyle("li", fontName=F, fontSize=9.5, leading=13, textColor=colors.HexColor("#12212E"),
                      leftIndent=12, bulletIndent=2, spaceAfter=3.5),
 "cell": ParagraphStyle("cell", fontName=F, fontSize=8.1, leading=10.6),
 "cellh": ParagraphStyle("cellh", fontName=FB, fontSize=8.1, leading=10.6, textColor=colors.white),
}

def esc(t):
    return (str(t).replace("&","&amp;").replace("<","&lt;").replace(">","&gt;"))

def build(blocks, out, title, subtitle):
    story = []
    for kind, val in blocks:
        if kind == "h1":
            story += [Paragraph(esc(val), S["h1"]), Spacer(1, 2),
                      Table([[""]], colWidths=[170*mm], rowHeights=[1.6],
                            style=TableStyle([("BACKGROUND",(0,0),(-1,-1),NAVY)])), Spacer(1,6)]
        elif kind == "h2":
            story.append(Paragraph(esc(val), S["h2"]))
            story.append(Table([[""]], colWidths=[165*mm], rowHeights=[0.7],
                        style=TableStyle([("BACKGROUND",(0,0),(-1,-1),TEAL)])))
        elif kind == "h3": story.append(Paragraph(esc(val), S["h3"]))
        elif kind == "p":  story.append(Paragraph(esc(val), S["p"]))
        elif kind == "small": story.append(Paragraph(esc(val), S["small"]))
        elif kind == "bullets":
            for it in val:
                story.append(Paragraph(esc(it), S["li"], bulletText="\u2022"))
            story.append(Spacer(1,3))
        elif kind == "code":
            story.append(KeepTogether([Preformatted(val, S["code"]), Spacer(1,7)]))
        elif kind == "table":
            head, rows = val[0], val[1:]
            data = [[Paragraph(esc(c), S["cellh"]) for c in head]] + \
                   [[Paragraph(esc(c), S["cell"]) for c in r] for r in rows]
            n = len(head); w = 168*mm/n
            t = Table(data, colWidths=[w]*n, repeatRows=1)
            t.setStyle(TableStyle([
                ("BACKGROUND",(0,0),(-1,0),NAVY),
                ("GRID",(0,0),(-1,-1),0.4,LINE),
                ("VALIGN",(0,0),(-1,-1),"TOP"),
                ("LEFTPADDING",(0,0),(-1,-1),4),("RIGHTPADDING",(0,0),(-1,-1),4),
                ("TOPPADDING",(0,0),(-1,-1),3),("BOTTOMPADDING",(0,0),(-1,-1),3),
                ("ROWBACKGROUNDS",(0,1),(-1,-1),[colors.white, colors.HexColor("#F7FBFC")]),
            ]))
            story += [t, Spacer(1,7)]

    def deco(canv, doc):
        canv.saveState(); canv.setFillColor(NAVY)
        canv.rect(0, A4[1]-10*mm, A4[0], 4*mm, stroke=0, fill=1)
        canv.setFillColor(colors.white); canv.setFont(FB, 8)
        canv.drawString(15*mm, A4[1]-8.6*mm, title)
        canv.setFillColor(GREY); canv.setFont(F, 7.5)
        canv.drawString(15*mm, 8*mm, subtitle)
        canv.drawRightString(A4[0]-15*mm, 8*mm, "Page %d" % doc.page)
        canv.restoreState()

    doc = SimpleDocTemplate(str(out), pagesize=A4, topMargin=16*mm, bottomMargin=14*mm,
                            leftMargin=15*mm, rightMargin=15*mm,
                            title=title, author="Yash Rahangdale")
    doc.build(story, onFirstPage=deco, onLaterPages=deco)
    print("PDF:", out, round(out.stat().st_size/1024,1), "KB")

def count_pages(p):
    import re
    raw = Path(p).read_bytes()
    return len(re.findall(rb"/Type\s*/Page[^s]", raw))

# ---------------- 1. setup guide ----------------
build(GUIDE, ROOT/"docs/CareFlow_Setup_Guide_Hinglish.pdf",
      "CareFlow - Setup Guide",
      "Infotact Solutions confidential | Yash Rahangdale | ITS/DA/1393")

# ---------------- 2. project report ----------------
REPORT = [
 ("h1","CareFlow: Clinical Pathway Process Mining"),
 ("small","Internship Project Report | Infotact Solutions | Ref. No. ITS/DA/1393 | Intern: Yash Rahangdale | Data Associate L1 Intern (Data Analytics) | 10 Oct 2026 - 10 Nov 2026"),
 ("table",[["KPI","Value","KPI","Value"],
   ["Patient cases","1,500","Clean events","13,583"],
   ["Activities","15","DFG edges","28"],
   ["Average length of stay","9.65 h","Long stay > 24 h","17 (1.13 %)"],
   ["Worst bottleneck","Observation 226.6 min","Costliest dept","Operation Theatre"],
   ["Total cost","INR 25,886,761","Avg cost / case","INR 17,258"],
   ["Conformance fitness","1.0000","Long-stay AUC","0.998"]]),
 ("h2","1. Executive summary"),
 ("p","CareFlow analyses a hospital event log with process-mining techniques and answers three operational questions: what is the REAL care pathway, where do time and money leak, and which patient will become a long stay. From 1,500 journeys and 13,583 clean events the project reconstructs 14 pathway variants on a 28-edge Directly-Follows Graph, locates the worst bottleneck (Observation, 226.6 min average wait), shows Operation Theatre consumes 36 % of cost (INR 9,381,243 of INR 25,886,761), and trains a long-stay classifier on leakage-free features (AUC 0.998, F1 0.800). Everything reproduces with one command."),
 ("h2","2. Objectives"),
 ("bullets",["O1 Discover the real pathway as a process model (DFG + variants).",
   "O2 Quantify bottlenecks, waiting time, service time, cost and resource load.",
   "O3 Measure conformance of actual cases against the expected pathway.",
   "O4 Predict long stay (LOS > 24 h) from leakage-free features.",
   "O5 Deliver an interactive dashboard and documentation to industry standards."]),
 ("h2","3. Data"),
 ("p","Event log: one row = one event. Mandatory case_id (patient journey), activity, timestamp; optional resource, department, wait_minutes, service_minutes, cost_inr. Case attributes: age, gender, triage_level, admission_type, pathway, los_hours, total_cost_inr, n_events."),
 ("table",[["Property","Value"],
   ["Raw rows / clean rows","13,664 / 13,583 (81 duplicates removed)"],
   ["Cases / activities","1,500 / 15"],
   ["Period","Mar 2026 - Aug 2026"],
   ["Engineered columns","26 (event_log_clean.csv)"]]),
 ("p","Provenance: the reference log is realistic but synthetic (src/generate_data.py, seed 42) because patient-confidential data cannot be used. For real data the project documents the public 4TU.ResearchData 'Sepsis Cases - Event Log' (Mannhardt; ~1,050 cases / 15,214 events / 16 activities) with the exact XES-to-CSV column mapping, so the same pipeline runs unchanged."),
 ("h2","4. Pipeline architecture"),
 ("code","data/raw/event_log.csv\n  |  clean_data.py      8 cleaning rules + audit trail\n  v\ndata/processed/event_log_clean.csv   (26 features)\n  |- discover_models.py  DFG (28 edges), 14 variants\n  |- analyze_insights.py KPIs, bottlenecks, 14 PNG charts\n  |- conformance.py      token-based replay fitness\n  |- ml_model.py         long-stay classifier + evaluation\n  |- connect_db.py       MySQL / PostgreSQL / SQLite star schema\n  `- dashboard/app.py    Streamlit dashboard\nrun_all.py  ->  all six stages, ~25 seconds"),
 ("h2","5. Data cleaning rules"),
 ("table",[["#","Rule","Justification","Effect"],
   ["1","Trim/lower names, cast types","consistent schema","8 columns"],
   ["2","Drop rows with no case_id/activity/timestamp","unmineable","0 rows"],
   ["3","Remove exact duplicate events","double-scanned events inflate counts","81 rows"],
   ["4","Blank resource -> UNKNOWN, dept -> Unassigned","never delete an event for a label","203 filled"],
   ["5","Negative wait/cost -> 0; service <= 0 -> median","impossible / robust","outliers tamed"],
   ["6","Derive event_index, gap_minutes, is_rework","core mining features","3 columns"],
   ["7","Drop cases < 3 or > 200 events","too short / corrupt","0 cases"]]),
 ("h2","6. Results"),
 ("h3","6.1 Top directly-follows edges"),
 ("table",[["From - To","Count","From - To","Count"],
   ["Registration -> Triage","1,100","Emergency Assessment -> Lab Test","579"],
   ["Discharge Planning -> Discharge","979","Radiology -> Diagnosis Confirmed","579"],
   ["Specialist Consultation -> Lab Test","921","Triage -> Emergency Assessment","579"],
   ["Physiotherapy -> Discharge Planning","775","Lab Test -> Diagnosis Confirmed","521"],
   ["Diagnosis Confirmed -> Medication","725","Medication Prescribed -> Discharge","521"]]),
 ("h3","6.2 Department cost concentration"),
 ("table",[["Department","Events","Cost (INR)","Department","Events","Cost (INR)"],
   ["Operation Theatre","386","9,381,243","ICU","228","1,528,075"],
   ["Ward","1,951","4,903,160","Rehabilitation","862","1,254,142"],
   ["Laboratory","1,690","2,526,299","Front Desk","3,018","721,690"],
   ["Outpatient","2,034","1,783,783","Pharmacy","1,128","565,041"],
   ["Radiology","680","1,675,840","Emergency","1,687","1,649,701"]]),
 ("h3","6.3 Model evaluation (long stay > 24 h)"),
 ("p","Two feature sets were compared deliberately. The 'full' set contains post-outcome aggregates (they exist only after the stay ends) and therefore scores a perfect 1.000 - a textbook leakage artefact. The leakage-free set (age, gender, triage level, admission type, pathway, event count) is the shipped production model."),
 ("table",[["Feature set","Model","Accuracy","F1","ROC-AUC","CV F1"],
   ["full (leaky)","logistic regression","1.000","1.000","1.000","0.727 +/- 0.167"],
   ["full (leaky)","random forest","1.000","1.000","1.000","1.000 +/- 0.000"],
   ["full (leaky)","gradient boosting","1.000","1.000","1.000","1.000 +/- 0.000"],
   ["leakage-free","logistic regression","0.993","0.500","0.987","0.080 +/- 0.160"],
   ["leakage-free","random forest","0.990","0.000","0.996","0.000 +/- 0.000"],
   ["leakage-free (shipped)","gradient boosting","0.997","0.800","0.998","0.180 +/- 0.223"]]),
 ("p","Honest reading: long stays are only 1.13 % of cases (17 of 1,500), so accuracy misleads and cross-validated F1 swings widely. The model ranks risk well (AUC 0.998) but is not yet a clinically reliable decision rule. Next step: more long-stay cases or cost-sensitive learning / SMOTE, and validation on a real log where AUC 0.75-0.90 is expected."),
 ("h2","7. Business recommendations"),
 ("bullets",["Fix Observation first - 226.6 min average wait is the largest recoverable delay.",
   "Shift elective activity away from Friday 14:00 (peak load).",
   "Audit Operation Theatre utilisation - 36 % of total cost sits in one department.",
   "Standardise the most repeated step to remove rework at source.",
   "Fast-track Emergency Assessment -> Lab Test (579 cases) with a pre-approved lab panel.",
   "Use the risk score at triage to prioritise probable long stays for case management."]),
 ("h2","8. Limitations and next steps"),
 ("bullets",["Reference log is synthetic; real-log fitness is expected at 0.7-0.95, not 1.0.",
   "Cost is activity-level, not invoice-level; no payer dimension.",
   "Extreme class imbalance (1.13 %) limits classifier reliability.",
   "Next: real HIS log, pm4py Inductive Miner + Petri net, dashboard deployment, process drift monitoring."]),
 ("h2","9. Reproducibility"),
 ("code","pip install -r requirements.txt\npython run_all.py                 # 6 stages, ~25 s\npython src/connect_db.py --engine sqlite\nstreamlit run dashboard/app.py"),
 ("small","Infotact Solutions confidential - prepared by Yash Rahangdale - ITS/DA/1393"),
]
build(REPORT, ROOT/"reports/CareFlow_Project_Report.pdf",
      "CareFlow - Project Report",
      "Infotact Solutions confidential | Yash Rahangdale | ITS/DA/1393")

# ---------------- 3. documentation ----------------
DOC = [
 ("h1","CareFlow - Project Documentation"),
 ("small","Project: CareFlow: Clinical Pathway Process Mining | Intern: Yash Rahangdale | Role: Data Associate L1 Intern (Data Analytics) | Organisation: Infotact Solutions | Ref. No. ITS/DA/1393"),
 ("h2","1. Objective"),
 ("p","Read a hospital event log, reconstruct the real clinical pathway, find bottlenecks, rework and deviations, predict long stays, and publish results as charts, reports and a dashboard using the industry-standard workflow: collect, clean, validate, analyse, visualise, document."),
 ("h2","2. Data model"),
 ("p","One row = one event. Minimum columns: case_id (patient journey), activity (step), timestamp. Optional: resource, department, wait_minutes, service_minutes, cost_inr. Case-level: age, gender, triage_level, admission_type, pathway, los_hours, total_cost_inr."),
 ("h2","3. Database design (star schema)"),
 ("table",[["Table","Type","Key columns"],
   ["dim_patient","dimension","patient_id, age, gender"],
   ["dim_activity","dimension","activity, activity_group"],
   ["dim_department","dimension","department"],
   ["dim_resource","dimension","resource, department"],
   ["dim_date","dimension","date_key, day_name, month_name, is_weekend"],
   ["fact_case","fact","case_id, los_hours, total_cost_inr, is_long_stay"],
   ["fact_event","fact","event_id, case_id, event_index, activity, event_timestamp, wait_minutes"]]),
 ("p","MySQL note: TIMESTAMP is a reserved word, so the column is named event_timestamp. event_index must be rebuilt with ROW_NUMBER() OVER (PARTITION BY case_id ORDER BY event_timestamp) - that ordering is what makes process mining possible."),
 ("h2","4. Cleaning rules applied (audit logged in outputs/reports/cleaning_audit.json)"),
 ("table",[["Rule","Reason"],
   ["Drop rows without case_id / activity / timestamp","cannot be mined"],
   ["Remove exact duplicates (case + activity + timestamp)","double-scanned events - 81 removed"],
   ["Blank resource -> UNKNOWN","keep the event, do not lose the path"],
   ["Negative wait / cost -> 0","physically impossible"],
   ["service_minutes <= 0 -> median","robust to outliers"],
   ["Cases < 3 or > 200 events dropped","too short / corrupt journeys"]]),
 ("h2","5. Methods"),
 ("p","Process discovery: Directly-Follows Graph and trace-variant analysis; optional Inductive / Heuristics / Alpha miner plus token-based replay via pm4py. Conformance: token-based replay fitness per case and per variant with deviation typing. Analytics: KPI cards, bottleneck ranking by average wait, department cost, resource workload, weekday x hour heat map, LOS distribution. Predictive: binary classification of long stay (> 24 h) with leakage-free features, 5-fold cross-validation, ROC-AUC / F1 comparison and confusion matrix."),
 ("h2","6. Reproducibility"),
 ("code","pip install -r requirements.txt\npython run_all.py\npython src/connect_db.py --engine sqlite\njupyter notebook notebooks/"),
 ("h2","7. Limitations"),
 ("p","The reference log is synthetic, so conformance fitness is 1.0 and the classifier scores high. On real data expect fitness 0.7-0.95 and long-stay AUC 0.75-0.90. The resource dimension is coarse, cost is activity-level, and the long-stay class is highly imbalanced (1.13 %)."),
 ("small","Infotact Solutions confidential - prepared by Yash Rahangdale."),
]
build(DOC, ROOT/"docs/CareFlow_Project_Documentation.pdf",
      "CareFlow - Documentation",
      "Infotact Solutions confidential | Yash Rahangdale | ITS/DA/1393")
