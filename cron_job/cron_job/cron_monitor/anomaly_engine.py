from database import get_db


def analyze_run(job_name, duration_seconds, exit_code, stderr):
    score = 0.0
    reasons = []

    if exit_code != 0:
        score += 0.7
        reasons.append("non-zero exit code")

    if stderr:
        score += 0.2
        reasons.append("stderr output detected")

    durations = _recent_success_durations(job_name)
    if len(durations) >= 3:
        avg = sum(durations) / len(durations)
        if avg > 0 and duration_seconds > avg * 2:
            score += 0.3
            reasons.append("runtime is more than 2x recent average")

    score = min(score, 1.0)
    return {
        "score": score,
        "reason": ", ".join(reasons) if reasons else "normal run",
    }


def _recent_success_durations(job_name, limit=10):
    with get_db() as conn:
        rows = conn.execute(
            """
            SELECT duration_seconds
            FROM job_runs
            WHERE job_name = ? AND status = 'success'
            ORDER BY started_at DESC
            LIMIT ?
            """,
            (job_name, limit),
        ).fetchall()
    return [row["duration_seconds"] for row in rows]
