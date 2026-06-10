import os
import json
import urllib.request
import urllib.error
from database import get_db

SYSTEM_PROMPT = """You are a senior Site Reliability Engineer (SRE) and an expert AI Assistant for the Cron-Job Observability Engine.
Your goal is to help operators analyze cron jobs, logs, failures, subprocess runs, telemetry, and suggest remediation steps.

Here is the current state/context of the dashboard:
{dashboard_context_json}

{attached_log_section}

Provide clear, helpful, and technically accurate explanations. 
If analyzing a failure, identify potential root causes and suggest specific preventive or remedial actions.
Use markdown formatting (headings, bullet points, tables, code blocks) in your response. Keep explanations clean and professional.
"""

def get_dashboard_context():
    context = {}
    with get_db() as conn:
        # 1. Jobs context
        jobs = conn.execute("SELECT name, status, type, category, assignee, schedule, cmd FROM cron_jobs").fetchall()
        context["jobs"] = [dict(j) for j in jobs]

        # 2. Telemetry context
        total_runs = conn.execute("SELECT COUNT(*) AS count FROM job_runs").fetchone()["count"]
        failed_runs = conn.execute("SELECT COUNT(*) AS count FROM job_runs WHERE status = 'failed'").fetchone()["count"]
        anomalies = conn.execute("SELECT COUNT(*) AS count FROM job_runs WHERE anomaly_score >= 0.7").fetchone()["count"]
        
        failed_jobs = len([j for j in context["jobs"] if j["status"] != "Healthy"])
        healthy_jobs = len(context["jobs"]) - failed_jobs

        context["telemetry"] = {
            "totalJobs": len(context["jobs"]),
            "failedJobs": failed_jobs,
            "healthyJobs": healthy_jobs,
            "totalRuns": total_runs,
            "failedRuns": failed_runs,
            "anomaliesCount": anomalies
        }

        # 3. Recent Logs/Runs context
        recent_runs = conn.execute(
            """
            SELECT job_name, status, started_at, finished_at, duration_seconds, exit_code, 
                   anomaly_score, anomaly_reason, stdout, stderr, done, person
            FROM job_runs
            ORDER BY started_at DESC
            LIMIT 5
            """
        ).fetchall()
        context["recent_logs"] = [dict(r) for r in recent_runs]
        
    return context

def generate_fallback_response(message, context, attached_log):
    msg_lower = message.lower()
    
    if attached_log:
        job_name = attached_log.get("job_name", "Unknown Job")
        exit_code = attached_log.get("exit_code", -1)
        stderr = attached_log.get("stderr", "")
        reason = attached_log.get("anomaly_reason", "")
        
        response = "### 🤖 Local SRE Diagnostics Engine\n"
        response += "*Note: OpenAI API Key is not set, running local heuristic remediation rules.*\n\n"
        response += f"#### 🔍 Failure Analysis for `{job_name}`\n"
        response += f"- **Severity**: High (Subprocess Failure)\n"
        response += f"- **Exit Status Code**: `{exit_code}`\n"
        if reason:
            response += f"- **Anomaly Reason**: {reason}\n"
        
        response += "\n#### 📋 Root Cause Identification\n"
        if "timeout" in stderr.lower() or "timed out" in stderr.lower() or "timeout" in reason.lower():
            response += "The subprocess exceeded its network/runtime threshold or network socket connection timed out while reading downstream metrics.\n"
        elif "database" in stderr.lower() or "sqlite" in stderr.lower():
            response += "The application database was locked or had a syntax violation on connection write paths.\n"
        elif exit_code == 127:
            response += "The execution wrapper was unable to locate the command executable path (exit code 127: Command not found).\n"
        elif stderr:
            response += f"Console telemetry captured the following error stream:\n```\n{stderr}\n```\n"
        else:
            response += "The process exited with a non-zero status code without writing diagnostic info to standard error. This usually indicates an abrupt OS signal termination (SIGKILL) or an uncaught exception.\n"
            
        response += "\n#### 🛠️ Suggested Fixes & Preventive Action\n"
        response += "1. **Inspect command execution wrapper paths** and verify the python version/dependencies match execution flags.\n"
        response += "2. **Increase the timeout baseline** if the target script requires batch downloads or heavy I/O workloads.\n"
        response += "3. **Implement retries** in the script configuration logic to survive transient errors.\n"
        return response
        
    if any(k in msg_lower for k in ["fail", "unhealthy", "error", "crashed"]):
        unhealthy_jobs = [j for j in context["jobs"] if j["status"] != "Healthy"]
        recent_failures = [r for r in context.get("recent_logs", []) if r["status"] == "failed"]
        
        response = "### 🚨 Local SRE Failure Diagnostics\n"
        if unhealthy_jobs:
            response += f"#### ⚠️ Unhealthy Jobs ({len(unhealthy_jobs)})\n"
            for j in unhealthy_jobs:
                response += f"- **{j['name']}** (Schedule: `{j['schedule']}`, Command: `{j['cmd']}`)\n"
        else:
            response += "#### ✅ Cron Health Status\nAll monitored cron configurations are running healthy under baseline thresholds.\n"
            
        if recent_failures:
            response += "\n#### 🚨 Recent Process Failures\n"
            for f in recent_failures:
                response += f"- **{f['job_name']}** failed (exit {f['exit_code']}) at `{f['started_at']}`. Error: `{f['stderr'] or f['anomaly_reason']}`\n"
        return response

    if any(k in msg_lower for k in ["health", "status", "jobs"]):
        unhealthy_jobs = [j for j in context["jobs"] if j["status"] != "Healthy"]
        response = "### 📊 Cron Job Health Status\n"
        response += f"- **Total Registered Jobs:** {len(context['jobs'])}\n"
        response += f"- **Healthy Jobs:** {len(context['jobs']) - len(unhealthy_jobs)}\n"
        response += f"- **Unhealthy Jobs:** {len(unhealthy_jobs)}\n\n"
        if unhealthy_jobs:
            response += "⚠️ **Unhealthy Configurations:**\n"
            for j in unhealthy_jobs:
                response += f"- **{j['name']}** is currently **{j['status']}**. (Command: `{j['cmd']}`, Schedule: `{j['schedule']}`)\n"
        else:
            response += "✅ All registered cron configurations are currently **Healthy**."
        return response

    if "report" in msg_lower:
        telemetry = context.get("telemetry", {})
        
        response = "### 📋 SRE Incident & Observability Report\n"
        response += f"**Dashboard Context:** Local Offline Engine\n\n"
        response += "#### 1. System Overview\n"
        response += f"- Total Monitored Cron Jobs: **{telemetry.get('totalJobs', 0)}**\n"
        response += f"- Total Executions Captured: **{telemetry.get('totalRuns', 0)}**\n"
        response += f"- Overall Success Rate: **{telemetry.get('successRate', 100)}%**\n\n"
        response += "#### 2. Run Status Metrics\n"
        response += "| Metric | Value |\n"
        response += "| :--- | :--- |\n"
        response += f"| Healthy Jobs | {telemetry.get('healthyJobs', 0)} |\n"
        response += f"| Failed Jobs | {telemetry.get('failedJobs', 0)} |\n"
        response += f"| Total Runs | {telemetry.get('totalRuns', 0)} |\n"
        response += f"| Failed Runs | {telemetry.get('failedRuns', 0)} |\n"
        response += f"| Anomalies | {telemetry.get('anomaliesCount', 0)} |\n\n"
        response += "#### 3. SRE Remediation Actions\n"
        if telemetry.get('failedJobs', 0) > 0 or telemetry.get('failedRuns', 0) > 0:
            response += "⚠️ **Action Required:** There are failed jobs or anomalous runs in the database. Please check the log registry below to perform individual AI audits.\n"
        else:
            response += "✅ **System Stable:** No active incidents or abnormal runtimes reported.\n"
        return response

    if any(k in msg_lower for k in ["fix", "remediation", "suggest"]):
        return ("### 🛠️ General SRE Remediation Guidelines\n"
                "1. **Verify Wrapper Commands**: Check if the command registered (e.g. `python jobs/sample.py`) exists in the target environment.\n"
                "2. **Check Standard Error (Stderr)**: Non-zero exit codes (like exit 1 or exit 127) are usually accompanied by descriptive stderr output. Inspect the registry table.\n"
                "3. **Examine Runtime Overruns**: If a cron job takes more than 2x its average duration, check if it's hung on external API connections or locking tables.")

    if any(k in msg_lower for k in ["gentechies", "creator", "who built", "author", "members", "team"]):
        return ("### 👥 Gen Techies Engineering Team\n"
                "This observability dashboard and process-harness wrapper was engineered by the **Gen Techies** team:\n\n"
                "- **K THILAKHARIHARAN** (CSE Final Year)\n"
                "- **SHAIK AFREEN** (CSE Final Year)\n"
                "- **ROSHINI SRI S** (CSE Final Year)\n"
                "- **GOWDHAMA CHANDHRAN K** (IT Final Year)\n\n"
                "We focus on advanced site reliability automation and database performance telemetry systems.")

    if any(k in msg_lower for k in ["who are you", "what is this", "website", "about"]):
        return ("### 🤖 About Cron AI Assistant\n"
                "I am the **Cron Observability AI Assistant**, built specifically for this dashboard.\n\n"
                "I analyze cron execution histories, search for anomalies in runtime duration, inspect stderr console buffers, and suggest step-by-step remediation fixes. You can ask me to **Analyze Failures**, **Summarize Logs**, or **Check Health** using the quick chips below!")

    # Custom/general user questions fallback
    return (f"### 🤖 Local Diagnostics Reply\n"
            f"You asked: *\"{message}\"*\n\n"
            f"I am running in local diagnostics fallback mode because `OPENAI_API_KEY` is not set.\n"
            f"I can answer queries about cron jobs, system health, and team members. To get dynamic answers powered by GPT-4, configure the `OPENAI_API_KEY` environment variable.")

def generate_ai_response(user_message, attached_log=None):
    openai_key = os.environ.get("OPENAI_API_KEY")
    openai_model = os.environ.get("OPENAI_MODEL", "gpt-4o-mini")

    context = get_dashboard_context()
    
    attached_log_section = ""
    if attached_log:
        attached_log_section = f"The operator has attached the following log for analysis:\n{json.dumps(attached_log, indent=2)}"

    system_prompt = SYSTEM_PROMPT.format(
        dashboard_context_json=json.dumps(context, indent=2),
        attached_log_section=attached_log_section
    )

    if not openai_key:
        return generate_fallback_response(user_message, context, attached_log)

    url = "https://api.openai.com/v1/chat/completions"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {openai_key}"
    }
    
    payload = {
        "model": openai_model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message}
        ],
        "temperature": 0.2
    }

    try:
        req = urllib.request.Request(
            url, 
            data=json.dumps(payload).encode("utf-8"), 
            headers=headers, 
            method="POST"
        )
        with urllib.request.urlopen(req, timeout=30) as response:
            res_data = json.loads(response.read().decode("utf-8"))
            answer = res_data["choices"][0]["message"]["content"]
            return answer
    except Exception as e:
        print(f"Error calling OpenAI API: {e}")
        raise RuntimeError("Unable to reach AI service. Please try again.")
