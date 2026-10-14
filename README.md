# CareFlow — Clinical Pathway Process Mining

**Internship project — Infotact Solutions** | Ref. No. `ITS/DA/-----`
Intern: **Yash Rahangdale** · Role: **Data Associate L1 Intern** · Domain: **Data Analytics**
Project duration: **10 Oct 2026 → 10 Nov 2026 (1 month)**

---

## 1. What this project does

Hospitals run on **care pathways** — the sequence of steps a patient goes through
(Registration → Triage → Lab Test → Diagnosis → Treatment → Discharge). In reality this
sequence keeps changing: tests repeat, patients wait, some journeys take far longer.

CareFlow reads a **hospital event log** (one row = one activity for one patient) and applies
**process mining** to:

1. **Discover** the real pathway as a Directly-Follows Graph / process model
2. **Analyse** bottlenecks, waiting time, cost and resource load
3. **Check conformance** — how far real cases deviate from the expected pathway
4. **Predict** which journey becomes a long stay (LOS > 24 h)
5. **Visualise** everything in an interactive Streamlit dashboard
6. **Store & query** the whole log in SQL (MySQL / PostgreSQL / SQLite star schema)

## 2. Repository layout

```
CareFlow/
├── config/config.yaml           # every setting in one place
├── data/
│   ├── raw/                     # event_log.csv, case_attributes.csv
│   └── processed/               # event_log_clean.csv
├── sql/                         # schema.sql, load_data.sql, kpi_queries.sql, views.sql
├── src/
│   ├── utils.py                 # config, logger, helpers
│   ├── generate_data.py         # STEP 1  build the event log
│   ├── clean_data.py            # STEP 2a clean + audit trail
│   ├── preprocess.py            # STEP 2b features (gap, shift, variant, rework)
│   ├── discover_models.py       # STEP 3  DFG + variants + process model
│   ├── analyze_insights.py      # STEP 4  KPI, bottlenecks, charts
│   ├── conformance.py           # STEP 5  fitness / deviations
│   ├── ml_model.py              # STEP 6  long-stay prediction
│   ├── connect_db.py            # STEP 7  SQLAlchemy -> SQL demo + KPI export
│   └── pm4py_discovery.py       # OPTIONAL real Inductive/Heuristics miner
├── notebooks/                   # 00 database … 05 ML (6 notebooks)
├── dashboard/app.py             # STEP 8  Streamlit dashboard
├── outputs/                     # figures (PNG), reports (JSON/CSV), models
├── docs/                        # setup guide PDF, documentation
├── reports/                     # project report PDF
├── presentation/                # PPTX
├── run_all.py                   # one-click pipeline
├── requirements.txt
└── requirements-optional.txt    # pm4py + graphviz
```

## 3. Quick start

```bash
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python run_all.py                  # full pipeline (~25 s on a laptop)
streamlit run dashboard/app.py     # http://localhost:8501
```

## 4. Import your own data

Put a CSV at `data/raw/event_log.csv` — mandatory columns `case_id`, `activity`,
`timestamp`; optional `resource, department, wait_minutes, service_minutes, cost_inr`.
For the public real log (Sepsis Cases, 4TU.ResearchData) rename the XES columns
`case:concept:name → case_id`, `concept:name → activity`, `time:timestamp → timestamp`,
`org:resource → resource`, then:

```bash
python src/clean_data.py
python run_all.py --skip-data
```

## 5. Database

```bash
mysql -u root -p < sql/schema.sql
mysql -u root -p --local-infile=1 careflow < sql/load_data.sql
mysql -u root -p careflow < sql/kpi_queries.sql
python src/connect_db.py --engine sqlite     # offline demo (no server needed)
python src/connect_db.py --engine mysql      # MySQL / postgres
```

## 6. Reference run results (synthetic log, seed 42)

| metric | value |
|---|---|
| patient cases | 1,500 |
| events raw → clean | 13,664 → 13,583 (81 duplicates removed) |
| activities / DFG edges | 15 / 28 |
| pathway variants | 14 (top variant 29.9 %) |
| average length of stay | 9.65 h (median 6.14 h, P90 18.69 h) |
| long-stay cases (> 24 h) | 17 (1.13 %) |
| biggest bottleneck | Observation — 226.6 min average wait |
| costliest department | Operation Theatre |
| average cost per case | INR 17,258 |
| total cost | INR 25,886,761 |
| peak hospital load | Friday, 14:00 |
| conformance fitness (synthetic) | 1.0000 |

> **Data note.** `src/generate_data.py` builds a *realistic but synthetic* event log so the
> pipeline can be demonstrated without patient-confidential data. On a real hospital log
> expect fitness 0.7–0.95 and long-stay AUC ≈ 0.75–0.90.

## 7. Deliverables (per assignment letter)

| Deliverable | Location |
|---|---|
| Source Code | `src/`, `dashboard/`, `sql/`, `notebooks/`, `run_all.py` |
| Project Documentation | `docs/CareFlow_Setup_Guide_Hinglish.pdf`, `docs/documentation.html` |
| Project Report | `reports/CareFlow_Project_Report.pdf` |
| Presentation (PPT) | `presentation/CareFlow_Presentation.pptx` |
| Model Evaluation Results | `outputs/reports/model_metrics.json` |
| Final Demonstration | `streamlit run dashboard/app.py` |

Built by **Yash Rahangdale** — Data Associate L1 Intern, Infotact Solutions.
