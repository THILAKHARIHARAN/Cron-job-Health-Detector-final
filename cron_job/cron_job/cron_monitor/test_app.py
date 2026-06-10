import unittest
import os
import json
import sqlite3
import tempfile
from pathlib import Path

# Override database path for testing to avoid polluting the production database
import database
test_db_dir = tempfile.TemporaryDirectory()
test_db_path = Path(test_db_dir.name) / "test_monitor.db"
database.DB_PATH = test_db_path

from app import create_app
from database import get_db, init_db, row_to_dict
from anomaly_engine import analyze_run
from llm_narrator import narrate_run, narrate_dashboard
from llm_service import generate_fallback_response, generate_ai_response


class CronMonitorTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Initialize the app and the test database
        cls.app = create_app()
        cls.client = cls.app.test_client()

    def setUp(self):
        # Initialize/clean the test database before each test
        init_db()
        # Clean out runs and jobs to ensure a clean slate
        with get_db() as conn:
            conn.execute("DELETE FROM job_runs")
            conn.execute("DELETE FROM cron_jobs")
            # Ensure settings are seeded properly
            conn.execute("DELETE FROM project_settings")
            conn.execute(
                "INSERT INTO project_settings (id, name, owner, description) VALUES (1, 'Test Dashboard', 'Test Operator', 'Test Description')"
            )

    def tearDown(self):
        # Optional: Additional teardown per test
        pass

    @classmethod
    def tearDownClass(cls):
        # Cleanup temporary database folder
        try:
            test_db_dir.cleanup()
        except Exception:
            pass

    # 1. Test app health check endpoint
    def test_health_check(self):
        response = self.client.get("/health")
        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertEqual(data, {"status": "ok"})

    # 2. Test database helper function row_to_dict
    def test_row_to_dict(self):
        with get_db() as conn:
            row = conn.execute("SELECT * FROM project_settings WHERE id = 1").fetchone()
            self.assertIsNotNone(row)
            data = row_to_dict(row)
            self.assertIsInstance(data, dict)
            self.assertEqual(data["name"], "Test Dashboard")
            self.assertEqual(data["owner"], "Test Operator")

        # Test with None input
        self.assertIsNone(row_to_dict(None))

    # 3. Test project settings retrieval API
    def test_get_project_settings(self):
        response = self.client.get("/api/project")
        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertEqual(data["name"], "Test Dashboard")
        self.assertEqual(data["owner"], "Test Operator")
        self.assertEqual(data["description"], "Test Description")

    # 4. Test updating project settings API
    def test_update_project_settings(self):
        updated_payload = {
            "name": "New System Observability Engine",
            "owner": "Lead SRE Team",
            "description": "Observed and reported with zero delay."
        }
        response = self.client.post("/api/project", json=updated_payload)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json(), {"status": "success"})

        # Confirm update persisted
        get_response = self.client.get("/api/project")
        self.assertEqual(get_response.status_code, 200)
        data = get_response.get_json()
        self.assertEqual(data["name"], "New System Observability Engine")
        self.assertEqual(data["owner"], "Lead SRE Team")
        self.assertEqual(data["description"], "Observed and reported with zero delay.")

    # 5. Test empty jobs list configuration initially
    def test_list_configured_jobs_empty(self):
        response = self.client.get("/api/jobs")
        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertIn("jobs", data)
        self.assertEqual(len(data["jobs"]), 0)

    # 6. Test adding a job configuration
    def test_add_configured_job(self):
        job_payload = {
            "name": "Database Backup",
            "type": "backup",
            "category": "database",
            "assignee": "Afreen",
            "schedule": "0 2 * * *",
            "cmd": "python jobs/backup_job.py"
        }
        response = self.client.post("/api/jobs", json=job_payload)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json(), {"status": "success"})

        # Verify it lists the new job
        list_response = self.client.get("/api/jobs")
        self.assertEqual(list_response.status_code, 200)
        jobs = list_response.get_json()["jobs"]
        self.assertEqual(len(jobs), 1)
        self.assertEqual(jobs[0]["name"], "Database Backup")
        self.assertEqual(jobs[0]["assignee"], "Afreen")
        self.assertEqual(jobs[0]["schedule"], "0 2 * * *")

    # 7. Test bad request when adding a job without a name
    def test_add_configured_job_missing_name(self):
        job_payload = {
            "type": "backup",
            "category": "database",
            "cmd": "python jobs/backup_job.py"
        }
        response = self.client.post("/api/jobs", json=job_payload)
        self.assertEqual(response.status_code, 400)

    # 8. Test deleting a configured job
    def test_delete_configured_job(self):
        # Add a job first
        job_payload = {
            "name": "Cache Pruning",
            "type": "maintenance",
            "category": "system",
            "assignee": "Thilak",
            "schedule": "*/30 * * * *",
            "cmd": "echo 'pruning cache'"
        }
        self.client.post("/api/jobs", json=job_payload)
        
        # Get its ID
        jobs = self.client.get("/api/jobs").get_json()["jobs"]
        job_id = jobs[0]["id"]

        # Delete it
        del_response = self.client.delete(f"/api/jobs/{job_id}")
        self.assertEqual(del_response.status_code, 200)
        self.assertEqual(del_response.get_json(), {"status": "success"})

        # Verify empty jobs list
        jobs_after = self.client.get("/api/jobs").get_json()["jobs"]
        self.assertEqual(len(jobs_after), 0)

    # 9. Test simulating job execution
    def test_simulate_job_run(self):
        # Add a job to test simulation logic path
        self.client.post("/api/jobs", json={
            "name": "Telemetry Health Sync",
            "type": "telemetry",
            "category": "network",
            "cmd": "echo 'sync'"
        })

        response = self.client.post("/api/jobs/simulate")
        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertIn("job_name", data)
        self.assertIn("status", data)
        self.assertIn("duration_seconds", data)

        # Verify the runs API lists the simulated run
        runs_response = self.client.get("/api/jobs/runs")
        self.assertEqual(runs_response.status_code, 200)
        runs = runs_response.get_json()["runs"]
        self.assertEqual(len(runs), 1)
        self.assertEqual(runs[0]["job_name"], data["job_name"])

    # 10. Test running a job manually via execution wrapper endpoint
    def test_run_configured_job(self):
        # Insert a valid executable command job (e.g. echo)
        self.client.post("/api/jobs", json={
            "name": "Ping Job",
            "type": "monitoring",
            "category": "network",
            "cmd": "echo 'ping'"
        })
        
        jobs = self.client.get("/api/jobs").get_json()["jobs"]
        job_id = jobs[0]["id"]

        response = self.client.post(f"/api/jobs/{job_id}/run", json={
            "done": "Manual run execution",
            "person": "Roshini"
        })
        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertEqual(data["status"], "success")
        self.assertEqual(data["exit_code"], 0)

        # Check job run details are persisted
        runs = self.client.get("/api/jobs/runs").get_json()["runs"]
        self.assertEqual(len(runs), 1)
        self.assertEqual(runs[0]["person"], "Roshini")
        self.assertEqual(runs[0]["done"], "Manual run execution")

    # 11. Test querying a single run by ID and via legacy route
    def test_get_run_by_id_and_legacy(self):
        self.client.post("/api/jobs", json={
            "name": "Legacy Check",
            "type": "health",
            "category": "system",
            "cmd": "echo 'legacy'"
        })
        jobs = self.client.get("/api/jobs").get_json()["jobs"]
        job_id = jobs[0]["id"]
        
        # Execute it to generate a run
        self.client.post(f"/api/jobs/{job_id}/run", json={})
        runs = self.client.get("/api/jobs/runs").get_json()["runs"]
        run_id = runs[0]["id"]

        # 11a. Fetch by normal run endpoint
        run_response = self.client.get(f"/api/jobs/runs/{run_id}")
        self.assertEqual(run_response.status_code, 200)
        self.assertEqual(run_response.get_json()["job_name"], "Legacy Check")
        self.assertIn("narrative", run_response.get_json())

        # 11b. Fetch by legacy fallback endpoint
        legacy_response = self.client.get(f"/api/jobs/{run_id}")
        self.assertEqual(legacy_response.status_code, 200)
        self.assertEqual(legacy_response.get_json()["id"], run_id)

    # 12. Test single run query returns 404 if not found
    def test_get_run_not_found(self):
        response = self.client.get("/api/jobs/runs/999999")
        self.assertEqual(response.status_code, 404)

    # 13. Test pruning job runs
    def test_prune_runs(self):
        # Seed test jobs and simulate runs
        self.client.post("/api/jobs", json={
            "name": "Prune Test",
            "type": "maintenance",
            "category": "system",
            "cmd": "echo 'prune'"
        })
        self.client.post("/api/jobs/simulate")
        self.client.post("/api/jobs/simulate")

        # Confirm runs exist
        runs_before = self.client.get("/api/jobs/runs").get_json()["runs"]
        self.assertGreater(len(runs_before), 0)

        # Call prune endpoint
        prune_response = self.client.post("/api/jobs/runs/prune")
        self.assertEqual(prune_response.status_code, 200)
        self.assertEqual(prune_response.get_json(), {"status": "success"})

        # Confirm runs are deleted
        runs_after = self.client.get("/api/jobs/runs").get_json()["runs"]
        self.assertEqual(len(runs_after), 0)

    # 14. Test anomaly engine rules
    def test_anomaly_engine_rules(self):
        # Scenario A: Successful normal run
        res = analyze_run("JobX", 10.0, 0, "")
        self.assertEqual(res["score"], 0.0)
        self.assertEqual(res["reason"], "normal run")

        # Scenario B: Failed run with stderr
        res = analyze_run("JobX", 12.0, 1, "Connection refused")
        self.assertAlmostEqual(res["score"], 0.9) # 0.7 (exit code) + 0.2 (stderr)
        self.assertIn("non-zero exit code", res["reason"])
        self.assertIn("stderr output detected", res["reason"])

    # 15. Test LLM Narrator outputs
    def test_llm_narrator_helpers(self):
        # Test narrate_run for success
        run_success = {
            "status": "success",
            "job_name": "Sync Service",
            "duration_seconds": 15.42,
            "anomaly_reason": "normal run"
        }
        narrative = narrate_run(run_success)
        self.assertIn("Sync Service completed successfully", narrative)

        # Test narrate_run for failure
        run_failure = {
            "status": "failed",
            "job_name": "Sync Service",
            "duration_seconds": 5.10,
            "exit_code": 1,
            "anomaly_reason": "non-zero exit code"
        }
        narrative = narrate_run(run_failure)
        self.assertIn("Sync Service failed in 5.1s with exit code 1", narrative)

        # Test narrate_dashboard summary
        summary = {
            "total_runs": 20,
            "failed_runs": 3,
            "anomalies": 2
        }
        dash_narrative = narrate_dashboard(summary)
        self.assertIn("20 runs tracked. 3 failed, and 2 showed anomalous behavior", dash_narrative)

    # 16. Test LLM Service fallback offline heuristics
    def test_llm_service_fallback(self):
        context = {
            "jobs": [{"name": "Auth Sync", "status": "Healthy", "schedule": "daily", "cmd": "run.sh"}],
            "recent_logs": []
        }

        # 16a. Failures queries
        resp = generate_fallback_response("Why did my runs fail?", context, None)
        self.assertIn("Local SRE Failure Diagnostics", resp)

        # 16b. System status/health queries
        resp = generate_fallback_response("What is the health status?", context, None)
        self.assertIn("Total Registered Jobs", resp)

        # 16c. Team info queries
        resp = generate_fallback_response("Who built the project?", context, None)
        self.assertIn("Gen Techies Engineering Team", resp)
        self.assertIn("THILAKHARIHARAN", resp)
        self.assertIn("AFREEN", resp)
        self.assertIn("ROSHINI", resp)
        self.assertIn("GOWDHAMA", resp)

        # 16d. Attachment log failure diagnostics heuristics
        attached_log = {
            "job_name": "Web Scraper",
            "exit_code": 127,
            "stderr": "Command not found",
            "anomaly_reason": "non-zero exit code"
        }
        resp = generate_fallback_response("Explain this log failure", context, attached_log)
        self.assertIn("Failure Analysis for `Web Scraper`", resp)
        self.assertIn("Command not found", resp)


if __name__ == "__main__":
    unittest.main()
