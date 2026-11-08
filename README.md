# Wastewater Research Analytics Dashboard

Working PhD wastewater research analytics prototype, preserving the original dashboard appearance. **All data in this PUBLIC repository is fictional.**

## Live dashboard

https://wastewater-research-dashboard-ttkm8equrfrrbhjstkepmh.streamlit.app/

## Data storage without SQL

- `data/master_data.csv` contains all approved measurements. It starts with 20 fictional samples and 60 analyses.
- The authorised laboratory uploader selects **Data Management — upload new Excel records** above the dashboard.
- The app validates all measurements, skips exact duplicates, and stops if conflicting results are found.
- After approval, the updated master CSV and an unchanged copy of the uploaded Excel/CSV file in `data/archive/` are recorded **together in one GitHub commit**.
- Streamlit Cloud normally redeploys from GitHub automatically. Existing measurements remain available.

## One-time setup for permanent uploads

This repository is **public**. Use fictional or explicitly public demonstration data only.

1. Open https://github.com/settings/personal-access-tokens/new to create a **fine-grained personal access token**:
   - Resource owner: `muzwa`
   - Repository access: **Only select repositories**, then `wastewater-research-dashboard`.
   - Repository permission: **Contents → Read and write**.
   - Set a reasonable expiration and renew later as necessary.
2. Go to https://share.streamlit.io/ and open this application's menu, then **Settings → Secrets**.
3. Add these two values, using your own secret token and a long unique uploader password:

```toml
GITHUB_TOKEN = "YOUR_GITHUB_FINE_GRAINED_TOKEN"
UPLOAD_PASSWORD = "YOUR_STRONG_UNIQUE_UPLOAD_PASSWORD"
```

4. Save the secrets. Open the dashboard and expand **Data Management — upload new Excel records**.
5. Enter your uploader password, choose an Excel workbook, review the validation report, and approve appending the new measurements.

**Never paste the token/password in a chat, GitHub source file or public screenshot.**

## Excel format

Use the established three-sheet workbook. The importer reads its **Measurements** worksheet. It also accepts a tidy CSV with these columns:

```text
measurement_id, sample_id, collection_date, site, code, antibiotic,
reported_result, status, concentration_ng_l, lod_ng_l, loq_ng_l
```

Each measurement is uniquely identified by `(sample_id, code)`. The current demo recognises sites HOSP, IN, OUT, RIV and codes CIP, SMX, TMP. Units: ng/L.

Scientific integrity:
- Quantified measurements are numeric and at or above their stated LOQ.
- `ND` and `<LOQ` values are not converted to zero.
- Conflicting measurements are not overwritten.
- The original uploaded file is archived unchanged.
- Illustrative reporting limits are **not** laboratory-validated.

## Privacy and deployment limitations

This is a **public synthetic-data demonstration**. A GitHub token and uploader password only protect **write access**. All committed files, including archive files and earlier versions, remain publicly visible.

**Do not upload actual unpublished PhD research results, sponsor-restricted materials, private records, or other confidential information to this repository.** Moving to real institutional use will require approved private storage, authenticated viewing, audit trails, backup/restore arrangements, and data governance. PostgreSQL can be added later without redesigning the current dashboard.

## Local development

```bash
pip install -r requirements.txt
streamlit run app.py
```

Without the two Streamlit secrets, the analytics dashboard is viewable, but permanent uploads remain disabled.
