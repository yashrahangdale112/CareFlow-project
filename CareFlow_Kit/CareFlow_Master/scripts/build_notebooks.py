import json, nbformat as nbf
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]; OUT = ROOT/"notebooks"; OUT.mkdir(exist_ok=True)
def nb(cells):
    n = nbf.v4.new_notebook(); n.cells = cells
    for c in n.cells:
        if c.cell_type=="code" and not c.outputs: c.outputs=[]; c.execution_count=None
    return n
def md(t): return nbf.v4.new_markdown_cell(t)
def co(t): return nbf.v4.new_code_cell(t)

# ---- 00 database ----
n0 = nb([md("# 00 - Database & SQL\nCareFlow | Yash Rahangdale | Infotact Solutions\n\nYahan hum event log ko SQL (SQLite demo / MySQL / PostgreSQL) me load karenge aur KPI queries chalayenge."),
 co("import sys, pandas as pd\nsys.path.append('../src')\nfrom connect_db import get_engine, build_sqlite, run_kpis\neng = get_engine('sqlite')\nbuild_sqlite(eng)"),
 md("## Overall KPI"),
 co("pd.read_sql('SELECT COUNT(*) cases, ROUND(AVG(los_hours),2) avg_los_h, ROUND(SUM(total_cost_inr),0) total_cost FROM fact_case', eng)"),
 md("## Bottleneck: activity-wise waiting time (pure SQL)"),
 co("pd.read_sql('''SELECT activity, COUNT(*) occurrences, ROUND(AVG(wait_minutes),1) avg_wait_min,\n ROUND(AVG(service_minutes),1) avg_service_min FROM fact_event GROUP BY activity ORDER BY avg_wait_min DESC''', eng)"),
 md("## Directly-Follows edges (LEAD window function)"),
 co("pd.read_sql('''SELECT activity, next_activity, COUNT(*) edge_count FROM (SELECT case_id, event_index, activity,\n LEAD(activity) OVER (PARTITION BY case_id ORDER BY event_index) next_activity FROM fact_event)\n WHERE next_activity IS NOT NULL GROUP BY activity, next_activity HAVING COUNT(*)>=3 ORDER BY edge_count DESC LIMIT 10''', eng)")])
nbf.write(n0, str(OUT/"00_database_sql.ipynb"))

# ---- 01 data understanding ----
n1 = nb([md("# 01 - Data Understanding\nHar row = ek EVENT (case_id, activity, timestamp). Ek case = ek patient ka pura safar."),
 co("import pandas as pd, sys; sys.path.append('../src')\ndf = pd.read_csv('../data/raw/event_log.csv', parse_dates=['timestamp'])\nprint(df.shape); df.head()"),
 co("print('cases      :', df.case_id.nunique())\nprint('events     :', len(df))\nprint('activities :', df.activity.nunique())\nprint('date range :', df.timestamp.min(), '->', df.timestamp.max())\ndf.describe(include='all').T"),
 co("df.activity.value_counts().to_frame('events')"),
 co("df.groupby('case_id').size().describe()  # case length: min/max/median")])
nbf.write(n1, str(OUT/"01_data_understanding.ipynb"))

# ---- 02 cleaning ----
n2 = nb([md("# 02 - Data Cleaning\nNeeche wahi 8 steps hain jo `src/clean_data.py` me hain - audit ke saath."),
 co("import pandas as pd, numpy as np\ndf = pd.read_csv('../data/raw/event_log.csv')\nbefore = len(df); print('rows before:', before)"),
 co("df.columns = [c.strip().lower() for c in df.columns]\ndf['timestamp'] = pd.to_datetime(df['timestamp'], errors='coerce')\nfor c in ['wait_minutes','service_minutes','cost_inr']: df[c] = pd.to_numeric(df[c], errors='coerce')"),
 co("n=len(df); df = df.dropna(subset=['case_id','activity','timestamp']); print('missing key rows dropped:', n-len(df))\nn=len(df); df = df.drop_duplicates(['case_id','activity','timestamp']); print('duplicates removed:', n-len(df))\ndf['resource'] = df['resource'].fillna('UNKNOWN').str.upper()\ndf['department'] = df['department'].fillna('Unassigned')"),
 co("df.loc[df.wait_minutes<0,'wait_minutes']=0\ndf['service_minutes'] = df['service_minutes'].where(df.service_minutes>0, np.nan).fillna(df.service_minutes.median())\ndf['cost_inr'] = df['cost_inr'].clip(lower=0)"),
 co("df = df.sort_values(['case_id','timestamp'])\ndf['event_index'] = df.groupby('case_id').cumcount()\ndf['is_rework'] = (df.groupby('case_id')['activity'].shift(1)==df['activity']).astype(int)\nprint('rows after:', len(df), '| rework events:', df.is_rework.sum())\ndf.to_csv('../data/processed/event_log_clean.csv', index=False)")])
nbf.write(n2, str(OUT/"02_data_cleaning.ipynb"))

# ---- 03 discovery ----
n3 = nb([md("# 03 - Process Discovery\nDirectly-Follows Graph + variants. pm4py mile to Inductive Miner bhi."),
 co("import pandas as pd, networkx as nx, matplotlib.pyplot as plt\ndf = pd.read_csv('../data/processed/event_log_clean.csv', parse_dates=['timestamp'])"),
 co("df['next_activity'] = df.groupby('case_id')['activity'].shift(-1)\nedges = df.dropna(subset=['next_activity']).groupby(['activity','next_activity']).size().reset_index(name='count')\nedges.sort_values('count', ascending=False).head(15)"),
 co("G = nx.DiGraph()\nfor _,r in edges.iterrows(): G.add_edge(r.activity, r.next_activity, weight=r['count'])\nnx.draw(G, with_labels=True, node_size=1800, font_size=7, arrowsize=12)\nplt.tight_layout(); plt.show()"),
 co("df['variant'] = df.groupby('case_id')['activity'].transform(lambda s: ' -> '.join(s))\nvar = df.groupby('case_id')['variant'].first().value_counts().reset_index()\nvar.columns=['variant','cases']; var['pct'] = (100*var.cases/var.cases.sum()).round(2)\nprint('variants:', len(var)); var.head(10)")])
nbf.write(n3, str(OUT/"03_process_discovery.ipynb"))

# ---- 04 insights ----
n4 = nb([md("# 04 - Insights, Bottlenecks & Visualisation"),
 co("import pandas as pd, matplotlib.pyplot as plt\ndf = pd.read_csv('../data/processed/event_log_clean.csv')\nca = pd.read_csv('../data/raw/case_attributes.csv')"),
 co("bt = df.groupby('activity').agg(events=('activity','size'), avg_wait=('wait_minutes','mean'),\n        avg_service=('service_minutes','mean')).sort_values('avg_wait', ascending=False)\nbt.round(1)"),
 co("bt['avg_wait'].plot(kind='barh', figsize=(8,5), title='Bottlenecks - average wait (min)')\nplt.gca().invert_yaxis(); plt.tight_layout(); plt.show()"),
 co("dep = df.groupby('department').agg(cost=('cost_inr','sum'), events=('activity','size')).sort_values('cost', ascending=False)\ndep['cost'].plot(kind='bar', figsize=(8,4), title='Cost by department (INR)'); plt.tight_layout(); plt.show()"),
 co("ca['bucket'] = pd.cut(ca.los_hours, [0,6,12,18,24,999], labels=['<6h','6-12h','12-18h','18-24h','>24h'])\nca.groupby('bucket', observed=True).agg(cases=('case_id','size'), avg_cost=('total_cost_inr','mean')).round(0)")])
nbf.write(n4, str(OUT/"04_insights_visualization.ipynb"))

# ---- 05 ml ----
n5 = nb([md("# 05 - Long-stay Prediction (LOS > 24 h)\nLeakage-free features use karke."),
 co("import pandas as pd, json\nfrom sklearn.model_selection import train_test_split\nfrom sklearn.ensemble import GradientBoostingClassifier\nfrom sklearn.metrics import roc_auc_score, classification_report\ndf = pd.read_csv('../data/processed/event_log_clean.csv')\nca = pd.read_csv('../data/raw/case_attributes.csv')"),
 co("X = pd.get_dummies(ca[['age','gender','triage_level','admission_type','pathway','n_events']], drop_first=True)\ny = (ca.los_hours > 24).astype(int)\nXtr,Xte,ytr,yte = train_test_split(X,y,test_size=0.2,random_state=42,stratify=y)\nprint('train', Xtr.shape, 'test', Xte.shape, 'long-stay share', round(y.mean()*100,2),'%')"),
 co("m = GradientBoostingClassifier(random_state=42).fit(Xtr,ytr)\np = m.predict_proba(Xte)[:,1]\nprint('AUC:', round(roc_auc_score(yte,p),4))\nprint(classification_report(yte,(p>0.5).astype(int), zero_division=0))"),
 co("import joblib, pathlib\npathlib.Path('../outputs/models').mkdir(parents=True, exist_ok=True)\njoblib.dump(m, '../outputs/models/best_model.joblib'); print('model saved')")])
nbf.write(n5, str(OUT/"05_ml_prediction.ipynb"))
print("notebooks written")
