import argparse
import subprocess
import sys
from datetime import datetime, timezone

from anomaly_engine import analyze_run
from database import get_db, init_db


def utc_now():
    return datetime.now(timezone.utc).isoformat()


def run_job(job_name, command):
    init_db()
    started_at = utc_now()
    start = datetime.now(timezone.utc)

    result = subprocess.run(command, capture_output=True, text=True)

    finished_at = utc_now()
    duration = (datetime.now(timezone.utc) - start).total_seconds()
    status = "success" if result.returncode == 0 else "failed"
    anomaly = analyze_run(job_name, duration, result.returncode, result.stderr)

    with get_db() as conn:
        conn.execute(
            """
            INSERT INTO job_runs (
                job_name, status, started_at, finished_at, duration_seconds,
                exit_code, stdout, stderr, anomaly_score, anomaly_reason
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                job_name,
                status,
                started_at,
                finished_at,
                duration,
                result.returncode,
                result.stdout,
                result.stderr,
                anomaly["score"],
                anomaly["reason"],
            ),
        )

    return result.returncode


def main():
    parser = argparse.ArgumentParser(description="Run and record a monitored cron job.")
    parser.add_argument("job_name")
    parser.add_argument("command", nargs=argparse.REMAINDER)
    args = parser.parse_args()

    if not args.command:
        parser.error("command is required")

    sys.exit(run_job(args.job_name, args.command))


if __name__ == "__main__":
    main()
