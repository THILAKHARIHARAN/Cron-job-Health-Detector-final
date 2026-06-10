from flask import Blueprint, render_template, request

from database import get_db
from llm_narrator import narrate_dashboard


dashboard_bp = Blueprint("dashboard", __name__)


@dashboard_bp.get("/")
def index():
    return render_template("index.html")


@dashboard_bp.get("/api/project")
def get_project():
    with get_db() as conn:
        row = conn.execute("SELECT name, owner, description FROM project_settings WHERE id = 1").fetchone()
    if row:
        return dict(row)
    return {"name": "Cron-Job Health Dashboard", "owner": "", "description": ""}


@dashboard_bp.post("/api/project")
def update_project():
    data = request.get_json() or {}
    name = data.get("name", "")
    owner = data.get("owner", "")
    description = data.get("description", "")
    with get_db() as conn:
        cursor = conn.execute(
            "UPDATE project_settings SET name = ?, owner = ?, description = ? WHERE id = 1",
            (name, owner, description)
        )
        if cursor.rowcount == 0:
            conn.execute(
                "INSERT OR IGNORE INTO project_settings (id, name, owner, description) VALUES (1, ?, ?, ?)",
                (name, owner, description)
            )
    return {"status": "success"}


@dashboard_bp.get("/dashboard")
def dashboard():
    with get_db() as conn:
        total_jobs = conn.execute("SELECT COUNT(*) AS count FROM cron_jobs").fetchone()["count"]
        total_runs = conn.execute("SELECT COUNT(*) AS count FROM job_runs").fetchone()["count"]
        failed_runs = conn.execute(
            "SELECT COUNT(*) AS count FROM job_runs WHERE status = 'failed'"
        ).fetchone()["count"]
        anomalies = conn.execute(
            "SELECT COUNT(*) AS count FROM job_runs WHERE anomaly_score >= 0.7"
        ).fetchone()["count"]
        overruns = conn.execute(
            "SELECT COUNT(*) AS count FROM job_runs WHERE anomaly_reason LIKE '%runtime%'"
        ).fetchone()["count"]

        if total_runs > 0:
            success_runs = conn.execute(
                "SELECT COUNT(*) AS count FROM job_runs WHERE status = 'success'"
            ).fetchone()["count"]
            success_rate = round((success_runs / total_runs) * 100)
        else:
            success_rate = 100

        recent = conn.execute(
            """
            SELECT id, job_name, status, started_at, finished_at, duration_seconds,
                   exit_code, anomaly_score, anomaly_reason, done, person
            FROM job_runs
            ORDER BY started_at DESC
            LIMIT 10
            """
        ).fetchall()

    summary = {
        "total_runs": total_runs,
        "failed_runs": failed_runs,
        "anomalies": anomalies,
        "total_jobs": total_jobs,
        "success_rate": success_rate,
        "overruns": overruns,
    }
    return {
        "summary": summary,
        "narrative": narrate_dashboard(summary),
        "recent_runs": [dict(row) for row in recent],
    }

@dashboard_bp.post("/api/chat")
def chat():
    from llm_service import generate_ai_response
    data = request.get_json() or {}
    message = data.get("message", "")
    attached_log = data.get("attached_log")
    
    try:
        answer = generate_ai_response(message, attached_log)
        return {"answer": answer}
    except Exception as e:
        # Standard error response message as requested
        return {"error": str(e)}, 500
