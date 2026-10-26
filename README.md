# Hospital Patient Data Analysis System

A beginner-friendly Flask project for educational operational analytics. It uses SQLite locally and includes synthetic demo records, patient management, visit records, charts, visit history, CSV import, and CSV export.

## Run in VS Code (Windows PowerShell)

1. Install Python 3.11+ and VS Code.
2. Open this folder in VS Code.
3. In Terminal > New Terminal, run:

```powershell
py -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe app.py
```

4. Open http://127.0.0.1:5000

## Publish a public URL

1. Create a GitHub repository and upload these project files (do not upload `.env` or real patient data).
2. In Render, create a new Web Service and connect the repository.
3. Build command: `pip install -r requirements.txt`
4. Start command: `gunicorn app:app`
5. Deploy and open the Render URL.

This starter uses SQLite. On many cloud hosts, local disk data may reset on redeploy/restart unless a persistent disk is configured. For a durable public deployment, use a managed database and adapt the database connection accordingly.

## Features

- Dashboard KPIs and Chart.js charts
- Add/search patients and view visit history
- Add/search/delete visits
- Department workload, monthly trends, visit type and age-band summaries
- CSV patient import and visit report export
- Synthetic demo data created automatically on first run

## Safety and scope

Use synthetic or properly de-identified data only. This is an educational operational analytics project, not a clinical tool. Do not expose identifiable patient records in a public deployment. Add authentication and appropriate access controls before exposing record-level pages.
