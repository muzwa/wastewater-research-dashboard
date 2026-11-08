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


st.markdown("### 🧪 Wastewater Pharmaceutical Monitoring")
st.caption("PhD research analytics prototype · Fictional records · ng/L")

st.subheader("🔎 Filter your dashboard")
st.caption("These controls apply to all charts, tables and calculations. They stay visible on phones and computers.")

with st.expander("📁 Upload another Excel or CSV file (optional)", expanded=False):
    uploaded = st.file_uploader("Laboratory measurements", type=["xlsx", "csv"])
    st.caption("Uploads affect only your current session. Other visitors continue to see the built-in dummy data.")

try:
    data = clean(read_uploaded(uploaded) if uploaded is not None else demo_data())
except Exception as exc:
    st.error(f"Data validation error: {exc}")
    st.stop()

with st.container(border=True):
    sites = st.multiselect(
        "Sampling locations", options=list(SITES.keys()),
        default=list(SITES.keys()), format_func=lambda site: SITES[site],
        help="Remove or add a location to update the charts."
    )
    compounds = st.multiselect(
        "Antibiotics", options=list(CHEMS.keys()),
        default=list(CHEMS.keys()), format_func=lambda code: CHEMS[code],
        help="Choose one or more antibiotic residues."
    )
    dmin = data["collection_date"].min().date()
    dmax = data["collection_date"].max().date()
    period = st.radio(
        "Date range", ["All dates", "Last 14 days", "Custom range"],
        horizontal=True, help="Select a preset or specify exact collection dates."
    )
    if period == "Custom range":
        selected_dates = st.date_input(
            "From / To", value=(dmin, dmax), min_value=dmin, max_value=dmax,
            format="DD/MM/YYYY"
        )
        if not isinstance(selected_dates, (list, tuple)) or len(selected_dates) != 2:
            st.info("Please select both the start and end dates.")
            st.stop()
        dates = tuple(selected_dates)
    elif period == "Last 14 days":
        from datetime import timedelta
        dates = (max(dmin, dmax - timedelta(days=13)), dmax)
    else:
        dates = (dmin, dmax)
    st.caption(f"Showing collection dates: {dates[0]:%d %b %Y} – {dates[1]:%d %b %Y}")

st.caption("This is a demonstration. No shared database or user accounts are connected.")

if not compounds or not sites:
    st.info("Select at least one sampling location and antibiotic.")
    st.stop()
if len(dates) != 2:
    st.info("Select both start and end dates.")
    st.stop()
df = data.loc[data["site"].isin(sites) & data["code"].isin(compounds) &
              data["collection_date"].dt.date.between(*dates)].copy()
if df.empty:
    st.info("No records match these filters.")
    st.stop()

total = len(df)
quant = df["status"].eq("Quantified")
below = df["status"].eq("Detected <LOQ")
not_detected = df["status"].eq("Not detected")
k1, k2, k3, k4, k5 = st.columns(5)
k1.metric("Samples", df["sample_id"].nunique())
k2.metric("Analyses", total)
k3.metric("Quantified", int(quant.sum()))
k4.metric("Detection frequency", f"{(1-not_detected.mean())*100:.1f}%")
k5.metric("Below LOQ / ND", f"{int(below.sum())} / {int(not_detected.sum())}")

overview, trends, treatment, records = st.tabs(
    ["📊 Overview", "📈 Research trends", "💧 Inlet / outlet", "🗂️ Records & quality"]
)
with overview:
    st.subheader("Mean quantified concentration by sampling location")
    avg = df.loc[quant].groupby(["site_label", "code"], as_index=False)["concentration_ng_l"].mean()
    if not avg.empty:
        st.plotly_chart(px.bar(avg, x="site_label", y="concentration_ng_l", color="code",
                               barmode="group", labels={"concentration_ng_l": "ng/L", "site_label": "Location"}),
                        use_container_width=True)
    st.subheader("Reporting statuses")
    counts = df.groupby(["site_label", "status"]).size().reset_index(name="results")
    st.plotly_chart(px.bar(counts, x="site_label", y="results", color="status", barmode="stack"),
                    use_container_width=True)
    st.info("Only quantified results are included in means. Below-LOQ and non-detected results are not set to zero.")

with trends:
    choice = st.selectbox("Antibiotic for time trend", compounds, format_func=lambda c: CHEMS[c])
    t = df.loc[quant & df["code"].eq(choice)]
    if not t.empty:
        st.plotly_chart(px.line(t, x="collection_date", y="concentration_ng_l", color="site_label",
                                markers=True, labels={"collection_date": "Date", "concentration_ng_l": "ng/L"}),
                        use_container_width=True)
    st.subheader("Quantified measurement distributions")
    if quant.any():
        st.plotly_chart(px.box(df.loc[quant], x="code", y="concentration_ng_l", points="all",
                               labels={"concentration_ng_l": "ng/L"}), use_container_width=True)
        st.dataframe(df.loc[quant].groupby("code")["concentration_ng_l"]
                     .agg(["count", "mean", "median", "min", "max"]).round(1), use_container_width=True)

with treatment:
    st.subheader("Date-matched inlet/outlet concentration comparison")
    pair = df.loc[quant & df["site"].isin(["IN", "OUT"])].pivot_table(
        index=["collection_date", "code"], columns="site", values="concentration_ng_l", aggfunc="mean"
    )
    if {"IN", "OUT"}.issubset(pair.columns):
        pair = pair.dropna(subset=["IN", "OUT"]).reset_index()
        pair = pair[pair["IN"] > 0]
        pair["apparent_reduction_pct"] = (1 - pair["OUT"] / pair["IN"]) * 100
        if not pair.empty:
            st.plotly_chart(px.line(pair, x="collection_date", y="apparent_reduction_pct",
                                    color="code", markers=True, labels={"apparent_reduction_pct": "Apparent reduction (%)"}),
                            use_container_width=True)
            st.dataframe(pair.round(2), use_container_width=True, hide_index=True)
    else:
        st.info("Select both IN and OUT sites to show paired observations.")
    st.warning("Same-date concentration differences are NOT validated treatment efficiencies. Flow and hydraulic residence time must be considered.")

with records:
    st.subheader("Laboratory measurement records")
    display = df.drop(columns=["site_label", "compound_label"])
    st.dataframe(display, hide_index=True, use_container_width=True)
    st.download_button("Download filtered CSV", display.to_csv(index=False).encode("utf-8"),
                       file_name="wastewater_filtered.csv", mime="text/csv")
    st.subheader("Data quality")
    st.dataframe(df["status"].value_counts().rename_axis("Status").reset_index(name="Count"),
                 use_container_width=True, hide_index=True)
    st.caption("Illustrative LOD/LOQ values are not laboratory-validated.")

st.divider()
st.caption("Research demonstration only · No regulatory or health-risk conclusions · Uploaded files are session-local.")
