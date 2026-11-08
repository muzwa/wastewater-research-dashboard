"""Validated, append-only Excel import to a GitHub master CSV (fictional demo data ONLY)."""
import base64
import hashlib
import hmac
import io
import re
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import requests
import streamlit as st

REPO = "muzwa/wastewater-research-dashboard"
BRANCH = "main"
MASTER = "data/master_data.csv"
FIELDS = ["measurement_id","sample_id","collection_date","site","code","antibiotic",
          "reported_result","status","concentration_ng_l","lod_ng_l","loq_ng_l"]
CHEMS = {"CIP":"Ciprofloxacin","SMX":"Sulfamethoxazole","TMP":"Trimethoprim"}
SITES = {"HOSP","IN","OUT","RIV"}
ALIASES = {"Measurement ID":"measurement_id","Sample ID":"sample_id",
           "Collection date":"collection_date","Site":"site","Code":"code",
           "Antibiotic":"antibiotic","Reported result (ng/L)":"reported_result",
           "Result status":"status","Numeric conc. (ng/L)":"concentration_ng_l",
           "LOD (ng/L)":"lod_ng_l","LOQ (ng/L)":"loq_ng_l"}

def secret(key):
    try:
        return st.secrets.get(key)
    except (FileNotFoundError, KeyError, AttributeError):
        return None

def gh(method, path, token, **kwargs):
    res = requests.request(method, f"https://api.github.com/repos/{REPO}/{path.lstrip('/')}",
                           headers={"Authorization":f"Bearer {token}",
                                    "Accept":"application/vnd.github+json",
                                    "X-GitHub-Api-Version":"2022-11-28"},
                           timeout=25, **kwargs)
    if not res.ok:
        raise RuntimeError(f"GitHub {method} returned HTTP {res.status_code}; verify token permissions and connectivity.")
    return res.json()

def github_master(token):
    obj = gh("GET", f"contents/{MASTER}?ref={BRANCH}", token)
    return pd.read_csv(io.BytesIO(base64.b64decode(obj["content"])),
                       dtype={"sample_id":str}, keep_default_na=False)

def current_master():
    token = secret("GITHUB_TOKEN")
    if token:
        try:
            return github_master(token)
        except Exception:
            st.warning("GitHub temporarily unavailable. Showing bundled data; saving may not work.")
    return pd.read_csv(Path(__file__).parent / MASTER, dtype={"sample_id":str}, keep_default_na=False)

def import_excel(file):
    if file.size > 10_000_000:
        raise ValueError("File size exceeds 10 MB.")
    if file.name.lower().endswith(".csv"):
        return pd.read_csv(io.BytesIO(file.getvalue()), keep_default_na=False)
    if not file.name.lower().endswith(".xlsx"):
        raise ValueError("Upload an Excel .xlsx or CSV file.")
    book = pd.ExcelFile(io.BytesIO(file.getvalue()))
    if "Measurements" not in book.sheet_names:
        raise ValueError("The Excel workbook must contain a Measurements sheet.")
    scan = pd.read_excel(book, sheet_name="Measurements", header=None, nrows=16)
    header_row = next((int(i) for i,r in scan.iterrows()
                       if {"Sample ID","Code","Result status"}.issubset(set(map(str,r.dropna())))),None)
    if header_row is None:
        raise ValueError("Measurements column headings were not found.")
    return pd.read_excel(book, sheet_name="Measurements", header=header_row)

def normalize(df, cleaner):
    df = df.rename(columns=ALIASES).copy()
    if "measurement_id" not in df and {"sample_id","code"}.issubset(df):
        df["measurement_id"] = df["sample_id"].astype(str)+"-"+df["code"].astype(str)
    if "antibiotic" not in df and "code" in df:
        df["antibiotic"] = df["code"].map(CHEMS)
    x = cleaner(df)
    if not x["sample_id"].map(lambda s: re.fullmatch(r"[A-Za-z0-9_-]{1,40}",s) is not None).all():
        raise ValueError("Sample IDs must be alphanumeric, dashes or underscores, at most 40 characters.")
    if not x["code"].isin(CHEMS).all() or not x["site"].isin(SITES).all():
        raise ValueError("Only the current 3 antibiotics and 4 sampling sites are supported.")
    if x.groupby("sample_id")["site"].nunique().gt(1).any() or x.groupby("sample_id")["collection_date"].nunique().gt(1).any():
        raise ValueError("Each sample must have one consistent collection date and site.")
    for r in x.itertuples(index=False):
        reported = str(r.reported_result).strip()
        if r.status == "Quantified":
            try:
                valid = abs(float(reported)-float(r.concentration_ng_l)) < 1e-7
            except (TypeError, ValueError):
                valid = False
            if not valid:
                raise ValueError(f"{r.sample_id}/{r.code}: reported and numeric concentrations differ.")
        elif r.status == "Not detected":
            if reported.upper()!="ND":
                raise ValueError(f"{r.sample_id}/{r.code}: ND status must have reported value ND.")
        else:
            try:
                bound=float(reported[1:]) if reported.startswith("<") else -1
            except ValueError:
                bound=-1
            if not (bound>0 and abs(bound-float(r.loq_ng_l))<1e-7):
                raise ValueError(f"{r.sample_id}/{r.code}: below-LOQ reporting must use '<LOQ'.")
    x["measurement_id"]=x["sample_id"]+"-"+x["code"]
    x["antibiotic"]=x["code"].map(CHEMS)
    return x[FIELDS].copy()

def classify(existing, incoming):
    old={(r.sample_id,r.code):r for r in existing.itertuples(index=False)}
    sample_meta=existing.groupby("sample_id").first()
    fresh=[]; duplicates=[]; conflicts=[]
    for r in incoming.itertuples(index=False):
        key=(r.sample_id,r.code)
        if r.sample_id in sample_meta.index:
            old_sample=sample_meta.loc[r.sample_id]
            if str(old_sample.site)!=r.site or pd.Timestamp(old_sample.collection_date)!=pd.Timestamp(r.collection_date):
                conflicts.append(f"{r.sample_id}: location/date differs from stored sample")
                continue
        prev=old.get(key)
        if prev is None:
            fresh.append(key)
            continue
        matching=(str(prev.site)==r.site and pd.Timestamp(prev.collection_date)==pd.Timestamp(r.collection_date)
                  and prev.status==r.status and float(prev.lod_ng_l)==float(r.lod_ng_l)
                  and float(prev.loq_ng_l)==float(r.loq_ng_l))
        if r.status=="Quantified" and prev.status=="Quantified":
            matching &= abs(float(prev.concentration_ng_l)-float(r.concentration_ng_l))<1e-7
        else:
            matching &= str(prev.reported_result).strip().upper()==str(r.reported_result).strip().upper()
        (duplicates if matching else conflicts).append(key if matching else f"{r.sample_id}/{r.code}: result differs")
    return fresh,duplicates,conflicts

def to_csv(frame):
    x=frame[FIELDS].copy()
    x["collection_date"]=pd.to_datetime(x["collection_date"]).dt.strftime("%Y-%m-%d")
    return x.to_csv(index=False,lineterminator="\n",float_format="%.10g")

def commit_upload(file, incoming, cleaner, token):
    """Create ONE atomic GitHub commit containing master CSV and an archive of the original file."""
    existing=normalize(github_master(token),cleaner)
    fresh,dupes,conflicts=classify(existing,incoming)
    if conflicts:
        raise ValueError("Conflicts detected on save; reload and review instead of overwriting.")
    if not fresh:
        return 0,None
    new_keys=set(fresh)
    accepted=incoming.loc[incoming.apply(lambda r:(r.sample_id,r.code) in new_keys,axis=1)]
    merged=pd.concat([existing,accepted],ignore_index=True)
    if merged[["sample_id","code"]].duplicated().any():
        raise ValueError("Duplicate measurement IDs: no changes made.")
    csv_text=to_csv(merged)
    stamp=datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    digest=hashlib.sha256(file.getvalue()).hexdigest()[:12]
    name=re.sub(r"[^A-Za-z0-9._-]","_",file.name)[:80]
    archive=f"data/archive/{stamp}-{digest}-{name}"
    head=gh("GET",f"git/ref/heads/{BRANCH}",token)["object"]["sha"]
    tree0=gh("GET",f"git/commits/{head}",token)["tree"]["sha"]
    master_blob=gh("POST","git/blobs",token,json={"content":csv_text,"encoding":"utf-8"})["sha"]
    archive_blob=gh("POST","git/blobs",token,json={
        "content":base64.b64encode(file.getvalue()).decode(),"encoding":"base64"})["sha"]
    tree=gh("POST","git/trees",token,json={"base_tree":tree0,"tree":[
        {"path":MASTER,"mode":"100644","type":"blob","sha":master_blob},
        {"path":archive,"mode":"100644","type":"blob","sha":archive_blob}]})["sha"]
    commit=gh("POST","git/commits",token,json={
        "message":f"Append {len(fresh)} validated measurements from {name}",
        "tree":tree,"parents":[head]})["sha"]
    gh("PATCH",f"git/refs/heads/{BRANCH}",token,json={"sha":commit,"force":False})
    return len(fresh),archive

def upload_panel(cleaner):
    with st.expander("📤 Data Management — upload new Excel records",expanded=False):
        st.caption("DEMONSTRATION ONLY: This repository is PUBLIC. Upload fictional or explicitly public records only; never confidential or unpublished research data.")
        token=secret("GITHUB_TOKEN")
        password=secret("UPLOAD_PASSWORD")
        if not token or not password:
            st.info("Persistent uploads await setup of GITHUB_TOKEN and UPLOAD_PASSWORD in Streamlit app Secrets. See GitHub README.")
            return
        if not st.session_state.get("uploader_authenticated",False):
            with st.form("unlock_form"):
                supplied=st.text_input("Authorised uploader password",type="password")
                unlock=st.form_submit_button("Unlock data management")
            if unlock:
                if supplied and hmac.compare_digest(supplied,str(password)):
                    st.session_state["uploader_authenticated"]=True
                    st.rerun()
                st.error("Incorrect password.")
            return
        if st.button("Lock upload controls"):
            st.session_state["uploader_authenticated"]=False
            st.rerun()
        uploaded=st.file_uploader("Upload Excel Measurements sheet or CSV",type=["xlsx","csv"])
        if uploaded is None:
            st.caption("An Excel file may contain all three original worksheets; only Measurements is imported.")
            return
        try:
            incoming=normalize(import_excel(uploaded),cleaner)
            existing=normalize(github_master(token),cleaner)
            fresh,duplicates,conflicts=classify(existing,incoming)
        except Exception as e:
            st.error(f"Validation failed: {e}")
            return
        c1,c2,c3=st.columns(3)
        c1.metric("New measurements",len(fresh))
        c2.metric("Already stored",len(duplicates))
        c3.metric("Conflicts",len(conflicts))
        if conflicts:
            st.error("Nothing can be saved until conflicts are reviewed. Existing research records are protected.")
            for x in conflicts[:12]:
                st.write("•",x)
            return
        if not fresh:
            st.info("All the uploaded measurements are already stored; nothing needs appending.")
            return
        accepted=incoming.loc[incoming.apply(lambda r:(r.sample_id,r.code) in set(fresh),axis=1)]
        st.dataframe(accepted,use_container_width=True,hide_index=True)
        approval=st.checkbox("I confirm these are fictional or explicitly public records and approve appending them.")
        if st.button("Approve and permanently save",type="primary",disabled=not approval):
            try:
                count,archive=commit_upload(uploaded,incoming,cleaner,token)
                st.success(f"Saved {count} new measurements and archived the original file ({archive}). The app should redeploy automatically.")
            except Exception as e:
                st.error(f"Save was not completed: {e}")
