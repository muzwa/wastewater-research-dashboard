"""Wastewater pharmaceutical monitoring — fictional research demonstration.

Run: streamlit run app.py
Data uploaded through this interface is session-local, not shared with other viewers.
"""
from io import BytesIO
import pandas as pd
import plotly.express as px
import streamlit as st

st.set_page_config(page_title="Wastewater Research Analytics", page_icon="🧪", layout="wide")
SITES = {"HOSP": "Hospital discharge", "IN": "Treatment plant inlet", "OUT": "Treatment plant outlet", "RIV": "Receiving river"}
CHEMS = {"CIP": "Ciprofloxacin", "SMX": "Sulfamethoxazole", "TMP": "Trimethoprim"}
LIMITS = {"CIP": (15, 35), "SMX": (20, 60), "TMP": (10, 30)}
STATUS = ["Quantified", "Detected <LOQ", "Not detected"]
RAW = """sample_id,collection_date,site,CIP,SMX,TMP
W001,2026-09-07,HOSP,920,1550,420
W002,2026-09-07,IN,740,1120,320
W003,2026-09-07,OUT,125,420,95
W004,2026-09-07,RIV,38,95,<30
W005,2026-09-14,HOSP,820,1250,390
W006,2026-09-14,IN,810,990,290
W007,2026-09-14,OUT,140,390,88
W008,2026-09-14,RIV,<35,112,30
W009,2026-09-21,HOSP,1100,1480,510
W010,2026-09-21,IN,690,1300,360
W011,2026-09-21,OUT,118,450,110
W012,2026-09-21,RIV,41,105,<30
W013,2026-09-28,HOSP,980,1800,475
W014,2026-09-28,IN,840,1210,340
W015,2026-09-28,OUT,155,470,105
W016,2026-09-28,RIV,46,120,35
W017,2026-10-05,HOSP,1050,1620,455
W018,2026-10-05,IN,790,1150,310
W019,2026-10-05,OUT,135,410,98
W020,2026-10-05,RIV,35,98,ND
"""


@st.cache_data
def demo_data():
    from io import StringIO
    samples = pd.read_csv(StringIO(RAW), dtype=str, keep_default_na=False)
    rows = []
    for _, s in samples.iterrows():
        for chem in CHEMS:
            value = s[chem]
            status = "Not detected" if value == "ND" else ("Detected <LOQ" if value.startswith("<") else "Quantified")
            lod, loq = LIMITS[chem]
            rows.append({
                "measurement_id": f"{s['sample_id']}-{chem}",
                "sample_id": s["sample_id"],
                "collection_date": s["collection_date"],
                "site": s["site"], "code": chem, "antibiotic": CHEMS[chem],
                "reported_result": value, "status": status,
                "concentration_ng_l": float(value) if status == "Quantified" else float("nan"),
                "lod_ng_l": lod, "loq_ng_l": loq,
            })
    return pd.DataFrame(rows)


def read_uploaded(file):
    if file.name.lower().endswith(".csv"):
        return pd.read_csv(file)
    if not file.name.lower().endswith(".xlsx"):
        raise ValueError("Upload an .xlsx or .csv file.")
    blob = BytesIO(file.getvalue())
    preview = pd.read_excel(blob, sheet_name="Measurements", header=None, nrows=20)
    header_row = None
    for idx, row in preview.iterrows():
        cells = set(str(c).strip() for c in row.dropna())
        if {"Sample ID", "Code", "Result status"}.issubset(cells):
            header_row = idx
            break
    if header_row is None:
        raise ValueError("Could not locate Measurements headings in the workbook.")
    blob.seek(0)
    return pd.read_excel(blob, sheet_name="Measurements", header=header_row)


def clean(df):
    aliases = {
        "Measurement ID": "measurement_id", "Sample ID": "sample_id",
        "Collection date": "collection_date", "Site": "site",
        "Code": "code", "Antibiotic": "antibiotic",
        "Reported result (ng/L)": "reported_result", "Result status": "status",
        "Numeric conc. (ng/L)": "concentration_ng_l",
        "LOD (ng/L)": "lod_ng_l", "LOQ (ng/L)": "loq_ng_l",
    }
    df = df.rename(columns=aliases).copy()
    required = ["measurement_id", "sample_id", "collection_date", "site", "code",
                "reported_result", "status", "concentration_ng_l", "lod_ng_l", "loq_ng_l"]
    missing = set(required) - set(df.columns)
    if missing:
        raise ValueError("Missing columns: " + ", ".join(sorted(missing)))
    df = df.dropna(subset=["sample_id"])
    for col in ["site", "code", "status", "sample_id"]:
        df[col] = df[col].astype(str).str.strip()
    df["site"] = df["site"].str.upper()
    df["code"] = df["code"].str.upper()
    df["collection_date"] = pd.to_datetime(df["collection_date"], errors="coerce")
    for col in ["concentration_ng_l", "lod_ng_l", "loq_ng_l"]:
        df[col] = pd.to_numeric(df[col], errors="coerce")
    if df["collection_date"].isna().any():
        raise ValueError("Invalid sample dates.")
    if not df["status"].isin(STATUS).all():
        raise ValueError("Unknown laboratory result status.")
    if df["measurement_id"].duplicated().any() or df[["sample_id", "code"]].duplicated().any():
        raise ValueError("Duplicate measurement ID or sample/compound combination.")
    if (df["lod_ng_l"] <= 0).any() or (df["loq_ng_l"] < df["lod_ng_l"]).any():
        raise ValueError("Invalid detection/quantification limits.")
    q = df["status"].eq("Quantified")
    if (q & (df["concentration_ng_l"].isna() | (df["concentration_ng_l"] < df["loq_ng_l"]))).any():
        raise ValueError("Quantified results must have concentrations at or above LOQ.")
    if ((~q) & df["concentration_ng_l"].notna()).any():
        raise ValueError("Non-quantified observations must have blank numeric concentrations.")
    df["site_label"] = df["site"].map(SITES).fillna(df["site"])
    df["compound_label"] = df["code"].map(CHEMS).fillna(df["code"])
    return df



# Embed the user's preferred original HTML dashboard rather than Streamlit's
# default widgets. The original controls, cards, tabs and charts remain in place.
from pathlib import Path
from data_manager import current_master, upload_panel

st.markdown(
    """
    <style>
    .stApp { background: #f6f9fb; }
    .block-container { max-width: 100% !important; padding: 0 !important; }
    [data-testid="stHeader"] { background: transparent; height: 1.2rem; }
    [data-testid="stToolbar"], [data-testid="collapsedControl"] { display: none; }
    </style>
    """,
    unsafe_allow_html=True,
)

upload_panel(clean)
data = clean(current_master())
template = Path(__file__).with_name("dashboard_template.html").read_text(encoding="utf-8")
records_json = data.to_json(orient="records").replace("<", "\\u003c")
html_page = (template.replace("__DATA__", records_json)
             .replace("__SAMPLE_COUNT__", str(data["sample_id"].nunique()))
             .replace("__ANALYSIS_COUNT__", str(len(data))))
st.iframe(html_page, width="stretch", height="content")
