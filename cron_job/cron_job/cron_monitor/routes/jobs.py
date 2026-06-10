import subprocess
import random
from datetime import datetime, timezone
from flask import Blueprint, abort, request

from database import get_db, row_to_dict
from llm_narrator import narrate_run
from anomaly_engine import analyze_run


jobs_bp = Blueprint("jobs", __name__)


def utc_now():
    return datetime.now(timezone.utc).isoformat()


# --- Configured Jobs CRUD ---

@jobs_bp.get("")
def list_configured_jobs():
    with get_db() as conn:
        rows = conn.execute(
            "SELECT id, name, type, category, assignee, schedule, cmd, status, created_at FROM cron_jobs ORDER BY name"
        ).fetchall()
    return {"jobs": [dict(row) for row in rows]}


@jobs_bp.post("")
def add_configured_job():
    data = request.get_json() or {}
    name = data.get("name", "").strip()
    if not name:
        abort(400, description="Job name is required")
    job_type = data.get("type", "other")
    category = data.get("category", "other")
    assignee = data.get("assignee", "")
    schedule = data.get("schedule", "")
    cmd = data.get("cmd", "")

    with get_db() as conn:
        try:
            conn.execute(
                """
                INSERT INTO cron_jobs (name, type, category, assignee, schedule, cmd)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (name, job_type, category, assignee, schedule, cmd)
            )
        except Exception as e:
            abort(400, description=f"Database error or duplicate job name: {str(e)}")
    return {"status": "success"}


@jobs_bp.delete("/<int:job_id>")
def delete_configured_job(job_id):
    with get_db() as conn:
        conn.execute("DELETE FROM cron_jobs WHERE id = ?", (job_id,))
    return {"status": "success"}


# --- Job Execution and Simulation ---

@jobs_bp.post("/<int:job_id>/run")
def run_configured_job(job_id):
    data = request.get_json() or {}
    done = data.get("done", "Executed via dashboard")
    person = data.get("person", "System Operator")

    with get_db() as conn:
        row = conn.execute("SELECT id, name, cmd, type FROM cron_jobs WHERE id = ?", (job_id,)).fetchone()

    if not row:
        abort(404, description="Job not found")

    job = dict(row)
    job_name = job["name"]
    cmd = job["cmd"]

    if not cmd:
        abort(400, description="No command configured for this job")

    started_at = utc_now()
    start_time = datetime.now(timezone.utc)

    # Execute command
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, shell=True, timeout=30)
        stdout = result.stdout
        stderr = result.stderr
        exit_code = result.returncode
    except subprocess.TimeoutExpired as e:
        stdout = e.stdout or ""
        stderr = (e.stderr or "") + "\nTimeout expired (30 seconds)"
        exit_code = -1
    except Exception as e:
        stdout = ""
        stderr = str(e)
        exit_code = -1

    finished_at = utc_now()
    duration = (datetime.now(timezone.utc) - start_time).total_seconds()
    status = "success" if exit_code == 0 else "failed"

    anomaly = analyze_run(job_name, duration, exit_code, stderr)
    job_status = "Healthy" if status == "success" else ("Warning" if anomaly["score"] < 0.7 else "Critical")

    with get_db() as conn:
        conn.execute(
            """
            INSERT INTO job_runs (
                job_name, status, started_at, finished_at, duration_seconds,
                exit_code, stdout, stderr, anomaly_score, anomaly_reason, done, person
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                job_name,
                status,
                started_at,
                finished_at,
                duration,
                exit_code,
                stdout,
                stderr,
                anomaly["score"],
                anomaly["reason"],
                done,
                person
            )
        )
        conn.execute("UPDATE cron_jobs SET status = ? WHERE id = ?", (job_status, job_id))

    return {
        "status": status,
        "exit_code": exit_code,
        "duration_seconds": duration,
        "anomaly_score": anomaly["score"],
        "anomaly_reason": anomaly["reason"]
    }


@jobs_bp.post("/simulate")
def simulate_run():
    with get_db() as conn:
        row = conn.execute("SELECT id, name, type FROM cron_jobs ORDER BY RANDOM() LIMIT 1").fetchone()

    if row:
        job = dict(row)
        job_name = job["name"]
        job_type = job["type"]
    else:
        # Fallback mocks if no jobs exist yet
        job_name = "System Maintenance"
        job_type = "maintenance"

    started_at = utc_now()
    duration = round(random.uniform(2.0, 45.0), 2)
    exit_code = random.choices([0, 1, 2], weights=[0.8, 0.1, 0.1])[0]
    stderr = "Intermittent timeout error (simulated)" if exit_code != 0 else ""
    status = "success" if exit_code == 0 else "failed"

    anomaly = analyze_run(job_name, duration, exit_code, stderr)

    done = "Simulated run via dashboard"
    person = "Simulated Worker"

    with get_db() as conn:
        conn.execute(
            """
            INSERT INTO job_runs (
                job_name, status, started_at, finished_at, duration_seconds,
                exit_code, stdout, stderr, anomaly_score, anomaly_reason, done, person
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                job_name,
                status,
                started_at,
                started_at,
                duration,
                exit_code,
                "Job output success (simulated)" if exit_code == 0 else "",
                stderr,
                anomaly["score"],
                anomaly["reason"],
                done,
                person
            )
        )
        if row:
            job_status = "Healthy" if status == "success" else ("Warning" if anomaly["score"] < 0.7 else "Critical")
            conn.execute("UPDATE cron_jobs SET status = ? WHERE name = ?", (job_status, job_name))

    return {
        "status": status,
        "job_name": job_name,
        "job_type": job_type,
        "exit_code": exit_code,
        "duration_seconds": duration,
        "anomaly_score": anomaly["score"],
        "anomaly_reason": anomaly["reason"],
        "started_at": started_at,
        "finished_at": started_at,
        "done": done,
        "person": person
    }


# --- Job Run History API ---

@jobs_bp.get("/runs")
def list_runs():
    job_name = request.args.get("job_name")
    limit = min(int(request.args.get("limit", 50)), 200)

    query = """
        SELECT id, job_name, status, started_at, finished_at, duration_seconds,
               exit_code, anomaly_score, anomaly_reason, done, person
        FROM job_runs
    """
    params = []
    if job_name:
        query += " WHERE job_name = ?"
        params.append(job_name)
    query += " ORDER BY started_at DESC LIMIT ?"
    params.append(limit)

    with get_db() as conn:
        rows = conn.execute(query, params).fetchall()

    return {"runs": [dict(row) for row in rows]}


@jobs_bp.get("/runs/<int:run_id>")
def get_run(run_id):
    with get_db() as conn:
        row = conn.execute("SELECT * FROM job_runs WHERE id = ?", (run_id,)).fetchone()

    run = row_to_dict(row)
    if run is None:
        abort(404, description="job run not found")

    run["narrative"] = narrate_run(run)
    return run


# Fallback for old API endpoint compatibility
@jobs_bp.get("/<int:run_id>")
def get_run_legacy(run_id):
    return get_run(run_id)


@jobs_bp.post("/runs/prune")
def prune_runs():
    with get_db() as conn:
        conn.execute("DELETE FROM job_runs")
        conn.execute("UPDATE cron_jobs SET status = 'Healthy'")
    return {"status": "success"}
