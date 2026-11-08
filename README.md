# Wastewater Pharmaceutical Monitoring — Research Dashboard

Interactive dashboard for **fictional wastewater antibiotic measurements** supporting a PhD research prototype. There are 20 samples from four sampling locations across five dates, containing 60 analyte observations for ciprofloxacin (CIP), sulfamethoxazole (SMX), and trimethoprim (TMP).

**All measurements are invented. Do not use this demo for scientific conclusions, clinical decisions, or regulatory compliance.**

## Run locally

```bash
pip install -r requirements.txt
streamlit run app.py
```

## Deploy online

Visit https://share.streamlit.io/ and sign in with GitHub. Click **Create app** / **Deploy**, choose repository `muzwa/wastewater-research-dashboard`, branch `main`, and main file path `app.py`. Select a unique subdomain if offered, then deploy.

## Dashboard pages

- Overview: summary measurements and detection-status breakdown
- Research trends: antibiotic concentration timelines, distributions and summary statistics
- Inlet / outlet: matched-date apparent concentration reductions
- Records & quality: individual observations and filtered CSV download

The sidebar filters date, site, and chemical. Uploading a compatible Excel/CSV file changes **only the current browser session**.

## Excel format

The prototype accepts the earlier research workbook with a `Measurements` sheet, with headings including `Measurement ID`, `Sample ID`, `Collection date`, `Site`, `Code`, `Reported result (ng/L)`, `Result status`, `Numeric conc. (ng/L)`, `LOD (ng/L)`, and `LOQ (ng/L)`. It also accepts a tidy CSV with the corresponding lowercase underscore column names.

## Scientific safeguards

- Non-detects and detected-below-LOQ results have blank numerical concentrations, never artificial zero values.
- Means and plots of concentration use only quantified results.
- The illustrative LOD/LOQ values must be replaced with method-specific validated limits before real research use.
- Identical-date inlet/outlet comparisons do not necessarily represent true treatment removal rates; hydraulic retention, matching protocols, flow, and sampling design matter.

## Privacy and use

This repository is public and contains fictional data only. **Do not commit unpublished, private, identifiable, or sponsor-restricted research data** to this repository. Community Cloud is suitable for a public demonstration; a production workflow needs institution-approved private storage, authentication, access roles, audit logs, and research data governance.

Uploads are temporary and do not update colleagues' dashboards. SQL storage is a possible future phase, not part of this version.
