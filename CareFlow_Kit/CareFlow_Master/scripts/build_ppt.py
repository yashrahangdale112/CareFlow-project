from pptx import Presentation
from pptx.util import Inches, Pt
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]

NAVY = RGBColor(0x0B,0x5D,0x7A); TEAL = RGBColor(0x17,0xA2,0xB8)
DARK = RGBColor(0x12,0x21,0x2E); GREY = RGBColor(0x5A,0x6B,0x78)
prs = Presentation(); prs.slide_width = Inches(13.333); prs.slide_height = Inches(7.5)
BLANK = prs.slide_layouts[6]

def bar(s): 
    r = s.shapes.add_shape(1, Inches(0), Inches(0), prs.slide_width, Inches(0.14))
    r.fill.solid(); r.fill.fore_color.rgb = TEAL; r.line.fill.background()
def txt(s,l,t,w,h,text,size=18,bold=False,color=DARK,align=PP_ALIGN.LEFT):
    tb = s.shapes.add_textbox(Inches(l),Inches(t),Inches(w),Inches(h)); tf = tb.text_frame
    tf.word_wrap = True
    for i,line in enumerate(text.split("\n")):
        p = tf.paragraphs[0] if i==0 else tf.add_paragraph()
        p.text = line; p.alignment = align
        for r in p.runs: r.font.size = Pt(size); r.font.bold = bold; r.font.color.rgb = color; r.font.name="Calibri"
    return tb
def head(s,title,kicker="CareFlow · Clinical Pathway Process Mining"):
    bar(s); txt(s,0.6,0.32,12,0.4,kicker.upper(),11,False,TEAL)
    txt(s,0.6,0.62,12,0.75,title,30,True,NAVY)
def bullets(s,items,t=1.7,l=0.7,w=12,h=5.2,size=15):
    tb = s.shapes.add_textbox(Inches(l),Inches(t),Inches(w),Inches(h)); tf = tb.text_frame; tf.word_wrap=True
    for i,it in enumerate(items):
        p = tf.paragraphs[0] if i==0 else tf.add_paragraph()
        p.text = "•  " + it; p.space_after = Pt(9)
        for r in p.runs: r.font.size = Pt(size); r.font.color.rgb = DARK
    return tb
def cards(s,data,t=1.75,h=1.5,size=22):
    n=len(data); gap=0.25; left=0.7; W=(12.0-gap*(n-1))/n
    for i,(big,small) in enumerate(data):
        x=left+i*(W+gap)
        sh=s.shapes.add_shape(1,Inches(x),Inches(t),Inches(W),Inches(h)); sh.fill.solid(); sh.fill.fore_color.rgb=RGBColor(0xEE,0xF7,0xFA)
        sh.line.color.rgb=RGBColor(0xCF,0xE0,0xE6)
        tf=sh.text_frame; tf.word_wrap=True
        p=tf.paragraphs[0]; p.text=big; p.alignment=PP_ALIGN.CENTER
        for r in p.runs: r.font.size=Pt(size); r.font.bold=True; r.font.color.rgb=NAVY
        p2=tf.add_paragraph(); p2.text=small; p2.alignment=PP_ALIGN.CENTER
        for r in p2.runs: r.font.size=Pt(10); r.font.color.rgb=GREY
def table(s,rows,t=1.9,l=0.7,w=12):
    cols=len(rows[0]); nr=len(rows); H=min(0.42*nr,4.8)
    shp=s.shapes.add_table(nr,cols,Inches(l),Inches(t),Inches(w),Inches(H))
    tbl=shp.table
    for i,row in enumerate(rows):
        for j,val in enumerate(row):
            c=tbl.cell(i,j); c.text=str(val)
            for p in c.text_frame.paragraphs:
                for r in p.runs:
                    r.font.size=Pt(11); r.font.name="Calibri"
                    r.font.bold = (i==0); r.font.color.rgb = RGBColor(0xFF,0xFF,0xFF) if i==0 else DARK
            if i==0: c.fill.solid(); c.fill.fore_color.rgb=NAVY
def foot(s,n):
    txt(s,0.7,7.0,10,0.3,"Infotact Solutions confidential · Yash Rahangdale · ITS/DA/1393",9,False,GREY)
    txt(s,12.0,7.0,0.8,0.3,str(n),9,False,GREY,PP_ALIGN.RIGHT)

# 1 title
s=prs.slides.add_slide(BLANK); bar(s)
txt(s,0.8,2.0,11.6,1.3,"CareFlow: Clinical Pathway\nProcess Mining",40,True,NAVY)
txt(s,0.8,3.5,11.6,0.5,"Process intelligence on a hospital event log — discover, diagnose, predict",17,False,DARK)
txt(s,0.8,4.3,11.6,0.4,"Yash Rahangdale  ·  Data Associate L1 Intern  ·  Data Analytics",14,True,DARK)
txt(s,0.8,4.75,11.6,0.4,"Infotact Solutions  ·  Ref. No. ITS/DA/1393  ·  10 Oct 2026 – 10 Nov 2026",12,False,GREY)
foot(s,1)

# 2 agenda
s=prs.slides.add_slide(BLANK); head(s,"Agenda")
bullets(s,["Business problem — why clinical pathways drift",
 "Data & method — event log, cleaning, process mining, SQL star schema",
 "What the process looks like — DFG, 14 variants, bottleneck at Observation",
 "Where the money goes — Operation Theatre = 36 % of cost",
 "Conformance — fitness 1.0000 on the synthetic log, 0.7–0.95 expected on real data",
 "Prediction — long stay > 24 h, leakage-free model, AUC 0.998",
 "Deliverables, dashboard demo and roadmap"],1.75)
foot(s,2)

# 3 problem
s=prs.slides.add_slide(BLANK); head(s,"The problem: pathways are designed on paper, executed differently")
bullets(s,["A hospital knows totals, not sequences — the ORDER of steps is invisible in reports.",
 "Tests repeat, patients queue, some journeys escalate to ICU — nobody can see where.",
 "Result: longer stays, avoidable cost, unpredictable capacity.",
 "Question this project answers: what is the REAL pathway, where does time leak, and who will become a long stay?"],1.8,0.7,12,4.6,16)
foot(s,3)

# 4 data
s=prs.slides.add_slide(BLANK); head(s,"Data: a process-mining event log")
txt(s,0.7,1.7,12,0.5,"One row = one event.  case_id + activity + timestamp are mandatory.",14,True,TEAL)
table(s,[["Field","Meaning","Field","Meaning"],
 ["case_id","patient journey","department","department"],
 ["activity","the step performed","wait_minutes","waiting before the step"],
 ["timestamp","when it happened","service_minutes","duration of the step"],
 ["resource","staff / machine","cost_inr","cost of the step"]],2.3)
cards(s,[("1,500","patient cases"),("13,583","clean events"),("15","activities"),("26","engineered columns")],4.5,1.4)
txt(s,0.7,6.2,12,0.5,"Synthetic but realistic log (seed 42) for the reference run; the pipeline also documents how to plug in a real public log (4TU Sepsis Cases, ~1,050 cases / 15,214 events).",11.5,False,GREY)
foot(s,4)

# 5 cleaning
s=prs.slides.add_slide(BLANK); head(s,"Step 1 — Data cleaning with an audit trail")
table(s,[["#","Rule","Effect"],
 ["1","Trim/lower names, cast timestamp & numbers","type errors removed"],
 ["2","Drop rows with no case_id / activity / timestamp","0 rows"],
 ["3","Remove exact duplicate events","81 duplicates removed"],
 ["4","Blank resource → UNKNOWN, department → Unassigned","events kept, not deleted"],
 ["5","Negative wait/cost → 0, service_minutes ≤ 0 → median","outliers tamed"],
 ["6","Derive event_index, gap_minutes, is_rework","process mining ready"],
 ["7","Drop cases < 3 or > 200 events","0 cases"]])
txt(s,0.7,6.15,12,0.4,"Every step is written to outputs/reports/cleaning_audit.json — grading-friendly evidence.",12,True,NAVY)
foot(s,5)

# 6 architecture
s=prs.slides.add_slide(BLANK); head(s,"Architecture — one command runs everything")
txt(s,0.7,1.6,12,4.6,"""data/raw/event_log.csv\n   │  clean_data.py   → 8 cleaning rules + audit JSON\n   ▼\ndata/processed/event_log_clean.csv   (26 features)\n   ├─ discover_models.py   → DFG (28 edges), 14 variants\n   ├─ analyze_insights.py  → KPIs, bottlenecks, 14 charts\n   ├─ conformance.py       → token-based replay fitness\n   ├─ ml_model.py          → long-stay classifier + eval\n   ├─ connect_db.py        → MySQL / PostgreSQL / SQLite star schema\n   └─ dashboard/app.py     → Streamlit dashboard\nrun_all.py  →  all six stages, ~25 seconds""",14,False,DARK)
foot(s,6)

# 7 process discovery
s=prs.slides.add_slide(BLANK); head(s,"Step 2 — What the pathway really looks like")
bullets(s,["28 directly-follows edges, 14 distinct variants; the top variant covers 29.9 % of cases.",
 "Registration → Triage is the busiest edge (1,100 cases): the front door is the volume gate.",
 "Diagnosis Confirmed → Medication Prescribed (725) is the clinical core.",
 "Emergency Assessment → Lab Test (579) is the biggest escalation edge."],1.7,0.7,12,4.8,15)
foot(s,7)

# 8 bottleneck
s=prs.slides.add_slide(BLANK); head(s,"Step 3 — Bottlenecks: the biggest single win")
cards(s,[("226.6 min","Observation — worst wait"),("Friday 14:00","peak hospital load"),("28","DFG edges"),("14","pathway variants")],1.75,1.5)
bullets(s,["Observation is the number-one delay in the pathway — one extra bay or a queue rule beats every other change per rupee.",
 "High-volume activities (Front Desk 3,018 events, Outpatient 2,034) matter for throughput, not wait.",
 "Rework events (a step repeated back-to-back) inflate both length of stay and cost."],3.6,0.7,12,3.0,15)
foot(s,8)

# 9 cost
s=prs.slides.add_slide(BLANK); head(s,"Step 4 — Where the money actually goes")
table(s,[["Department","Events","Total cost (INR)"],
 ["Operation Theatre","386","9,381,243  (36 %)"],
 ["Ward","1,951","4,903,160"],
 ["Laboratory","1,690","2,526,299"],
 ["Outpatient","2,034","1,783,783"],
 ["Radiology","680","1,675,840"],
 ["Emergency","1,687","1,649,701"],
 ["ICU","228","1,528,075"]])
txt(s,0.7,6.05,12,0.5,"Total INR 25,886,761 across 13,583 events · average INR 17,258 per patient case.",13,True,NAVY)
foot(s,9)

# 10 conformance
s=prs.slides.add_slide(BLANK); head(s,"Step 5 — Conformance: how far reality drifts")
cards(s,[("1.0000","fitness (synthetic log)"),("100 %","cases on model"),("14","variants observed"),("0.7–0.95","expected on real data")],1.75,1.5)
bullets(s,["Token-based replay scores every case: how many tokens were missing / left behind.",
 "Fitness 1.0000 is expected here — the synthetic generator follows fixed pathway templates.",
 "On a real hospital log the honest expectation is 0.7–0.95, with deviations clustering on rework loops and escalations."],3.6,0.7,12,3.0,15)
foot(s,10)

# 11 ML
s=prs.slides.add_slide(BLANK); head(s,"Step 6 — Predicting a long stay (> 24 h)")
table(s,[["Feature set","Model","Accuracy","F1","ROC-AUC"],
 ["full (leaky)","gradient boosting","1.000","1.000","1.000"],
 ["full (leaky)","logistic regression","1.000","1.000","1.000"],
 ["leakage-free","logistic regression","0.993","0.500","0.987"],
 ["leakage-free","random forest","0.990","0.000","0.996"],
 ["leakage-free (shipped)","gradient boosting","0.997","0.800","0.998"]],1.8)
txt(s,0.7,5.3,12,1.3,"Why two feature sets? The 'full' set contains post-outcome aggregates and scores a perfect 1.000 — a textbook data-leakage artefact. The leakage-free model is what ships.\nHonest caveat: long stays are only 1.13 % of cases (17 of 1,500), so recall is unstable — ranking is good, clinical reliability is not yet proven.",12,False,DARK)
foot(s,11)

# 12 recommendations
s=prs.slides.add_slide(BLANK); head(s,"Recommendations for the hospital")
bullets(s,["Fix Observation first — 226.6 min average wait is the largest recoverable delay.",
 "Move elective activity away from Friday 14:00 (peak load).",
 "Audit Operation Theatre utilisation — 36 % of cost sits in one department.",
 "Standardise the most repeated step to remove rework at source.",
 "Fast-track Emergency Assessment → Lab Test with a pre-approved lab panel.",
 "Use the risk score at triage to prioritise likely long stays for case management."],1.75,0.7,12,4.8,15)
foot(s,12)

# 13 deliverables
s=prs.slides.add_slide(BLANK); head(s,"Deliverables & how to reproduce")
table(s,[["Deliverable","Where"],
 ["Source code","src/, dashboard/, sql/, notebooks/, run_all.py"],
 ["Documentation","docs/ (setup guide + documentation.html)"],
 ["Project report","reports/CareFlow_Project_Report.pdf"],
 ["Presentation","presentation/CareFlow_Presentation.pptx"],
 ["Model evaluation","outputs/reports/model_metrics.json"],
 ["Demonstration","streamlit run dashboard/app.py"]],1.7)
txt(s,0.7,6.0,12,0.5,"pip install -r requirements.txt  →  python run_all.py  →  streamlit run dashboard/app.py",12,True,NAVY)
foot(s,13)

# 14 limitations / roadmap
s=prs.slides.add_slide(BLANK); head(s,"Limitations and next steps")
bullets(s,["Reference log is synthetic — real-log fitness will be lower (0.7–0.95).",
 "Cost is activity-level, not invoice-level; no payer dimension.",
 "Long-stay class is highly imbalanced (1.13 %) → use cost-sensitive learning or SMOTE.",
 "Next: connect a real HIS / Sepsis log, add pm4py Inductive Miner + Petri net, deploy the dashboard, monitor process drift."],1.8,0.7,12,4.4,16)
foot(s,14)

# 15 thank you
s=prs.slides.add_slide(BLANK); bar(s)
txt(s,0.8,2.6,11.6,1.0,"Thank you",40,True,NAVY)
txt(s,0.8,3.8,11.6,0.5,"Questions welcome — CareFlow: Clinical Pathway Process Mining",15,False,DARK)
txt(s,0.8,4.4,11.6,0.4,"Yash Rahangdale · Data Associate L1 Intern · Infotact Solutions · ITS/DA/1393",12,False,GREY)
foot(s,15)

out = ROOT/"presentation/CareFlow_Presentation.pptx"
prs.save(str(out)); print("PPT saved:", out, "slides:", len(prs.slides.__iter__.__self__._sldIdLst))
