def narrate_run(run):
    status = run["status"]
    job_name = run["job_name"]
    duration = round(run["duration_seconds"], 2)
    reason = run.get("anomaly_reason") or "normal run"

    if status == "success":
        return f"{job_name} completed successfully in {duration}s. Signal: {reason}."

    return f"{job_name} failed in {duration}s with exit code {run['exit_code']}. Signal: {reason}."


def narrate_dashboard(summary):
    failed = summary.get("failed_runs", 0)
    total = summary.get("total_runs", 0)
    anomalies = summary.get("anomalies", 0)
    return f"{total} runs tracked. {failed} failed, and {anomalies} showed anomalous behavior."
