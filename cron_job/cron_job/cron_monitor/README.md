# Cron Monitor

Small Flask backend for tracking cron job runs in SQLite.

## Setup

```powershell
cd cron_monitor
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python app.py
```

## Run a Monitored Job

```powershell
python cron_wrapper.py sample_job python jobs/sample_job.py
python cron_wrapper.py backup_job python jobs/backup_job.py
```

## Endpoints

- `GET /health`
- `GET /dashboard`
- `GET /api/jobs`
- `GET /api/jobs/<run_id>`
