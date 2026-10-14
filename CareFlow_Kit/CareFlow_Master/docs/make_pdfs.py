"""Convert every guide HTML into its own PDF (weasyprint), then zip the project."""
import os
import shutil
import subprocess
import sys

DOCS = "/home/user/work/CareFlow/docs"
OUT = "/home/user/work/deliverables"
os.makedirs(OUT, exist_ok=True)

JOBS = [
    ("master.html",         "CareFlow_00_Master_Guide.pdf"),
    ("step1.html",          "CareFlow_Step1_Setup.pdf"),
    ("step2.html",          "CareFlow_Step2_Install_Dependencies.pdf"),
    ("step3.html",          "CareFlow_Step3_Import_Your_Data.pdf"),
    ("step4.html",          "CareFlow_Step4_Run_Pipeline.pdf"),
    ("step5.html",          "CareFlow_Step5_Dashboard_And_Demo.pdf"),
    ("documentation.html",  "CareFlow_Project_Documentation.pdf"),
    ("report.html",         "CareFlow_Project_Report.pdf"),
    ("model_eval.html",     "CareFlow_Model_Evaluation_Results.pdf"),
    ("presentation.html",   "CareFlow_Presentation_Content.pdf"),
]

from weasyprint import HTML

ok, fail = [], []
for src, dst in JOBS:
    src_path = os.path.join(DOCS, src)
    dst_path = os.path.join(OUT, dst)
    try:
        HTML(filename=src_path, base_url=DOCS).write_pdf(dst_path)
        size = os.path.getsize(dst_path)
        ok.append((dst, size))
        print(f"OK   {dst:52s} {size/1024:8.1f} KB")
    except Exception as exc:                                     # noqa: BLE001
        fail.append((dst, str(exc)))
        print(f"FAIL {dst}: {exc}")

print(f"\n{len(ok)} PDFs written, {len(fail)} failed")
if fail:
    sys.exit(1)
