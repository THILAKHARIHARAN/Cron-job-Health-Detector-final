 Cron-Job Observability Engine (Cron Monitor)

Welcome to the **Cron-Job Observability Engine**, a premium, high-performance monitoring dashboard and execution harness designed to observe, track, and diagnose silent cron job failures. Built with a sleek dark-mode glassmorphism aesthetic, it integrates real-time telemetry, heuristic anomaly detection, and an AI-driven Site Reliability Engineering (SRE) Assistant.

This project was engineered by the **Gen Techies** team.

---
 Gen Techies Engineering Team
- **K THILAKHARIHARAN** (Computer Science & Engineering, Final Year)
- **SHAIK AFREEN** (Computer Science & Engineering, Final Year)
- **ROSHINI SRI S** (Computer Science & Engineering, Final Year)
- **GOWDHAMA CHANDHRAN K** (Information Technology, Final Year)

---
 Key Features

1. **Monitored Execution Harness (`cron_wrapper.py`)**
   - Intercepts subprocess commands, measures duration, captures standard outputs (`stdout`/`stderr`), and logs execution metadata to the database.
2. **Real-time Anomaly Detection Engine (`anomaly_engine.py`)**
   - Employs dynamic heuristics to calculate run anomaly scores:
     - **Non-zero Exit Code**: Adds `0.7` penalty.
     - **Standard Error (Stderr) Detected**: Adds `0.2` penalty.
     - **Duration Overrun**: Checks against the average of the last 3+ successful runs. Runtimes exceeding 2x the recent average add `0.3` penalty.
3. **AI-Powered SRE Diagnostics Assistant (`llm_service.py` & `llm_narrator.py`)**
   - Interfaces with OpenAI's `gpt-4o-mini` API to diagnose log failures, describe anomalies, and suggest step-by-step remediation procedures.
   - Built-in **Offline Heuristics Engine** fallback to provide localized diagnostics, incident reporting, and remediation suggestions when the OpenAI API key is absent.
4. **Interactive Dashboard Visualizations**
   - High-fidelity visual interface built with CSS-driven Glassmorphism, animations, responsive design, SVG charts, and a fully interactive **Onboarding Guided Tour** for operators.
5. **Robust Test Coverage (`test_app.py`)**
   - Over 16 automated tests validating blueprint routing, CRUD endpoints, legacy fallbacks, database transactions, anomaly heuristics, and local LLM responses.

---
 Project Architecture

```
cron_monitor
├── app.py            # Flask app factory initialization
├── database.py       # SQLite connection manager and initial database schema
├── anomaly_engine.py # Heuristic scoring algorithm for job run issues
├── cron_wrapper.py   # CLI wrapper script to intercept and log cron execution
├── llm_service.py    # OpenAI interface & local heuristic fallback logic
├── llm_narrator.py   # Natural language summarizer for runs and dashboard
├── test_app.py       # Comprehensive unit tests suite (Flask client and engine logic)
├── monitor.db        # Production SQLite database (created on runtime)
├── requirements.txt  # Project dependency manifest
├── routes/
│   ├── dashboard.py  # Dashboard view routes, project settings, and chatbot endpoints
│   └── jobs.py       # REST API endpoints for job CRUD, runs, simulation, and pruning
├── templates/
│   └── index.html    # Production dashboard template (connected to Flask API)
└── jobs/
    ├── __init__.py
    ├── backup_job.py # Sample backup cron script (creates /backups/backup.txt)
    └── sample_job.py # Sample CLI test script
```

---
Technology Stack

* **Backend Framework**: [Flask 3.0.3](https://flask.palletsprojects.com/) (Python 3) using Blueprints.
* **Databases**:
  * **SQLite3** (Active Application DB): Highly lightweight, zero-configuration local database.
  * **MySQL** (Alternative Schema): Configured through `cron DB.sql` for enterprise deployments.
* **AI & Natural Language Processing**: OpenAI API (`gpt-4o-mini`) using standard `urllib` calls (no heavy SDK requirements), alongside local heuristic regex match fallbacks.
* **Frontend Design**: 
  * Modern Dark neon color palette tailored using curated HSL custom properties.
  * Glassmorphism panels, CSS fadeInUp animations, custom-themed modals, table layouts, and SVG timeline rendering.
  * Interactive step-by-step onboarding tour powered by vanilla JavaScript.

---
 Database Schemas
 1. SQLite Schema (`database.py`)

* **`project_settings`**: Stores global dashboard settings (singleton pattern).
  ```sql
  CREATE TABLE project_settings (
      id INTEGER PRIMARY KEY CHECK (id = 1),
      name TEXT DEFAULT '',
      owner TEXT DEFAULT '',
      description TEXT DEFAULT ''
  );
  ```
* **`cron_jobs`**: Holds configurations for registered cron jobs.
  ```sql
  CREATE TABLE cron_jobs (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      name TEXT NOT NULL UNIQUE,
      type TEXT NOT NULL,
      category TEXT NOT NULL,
      assignee TEXT DEFAULT '',
      schedule TEXT DEFAULT '',
      cmd TEXT DEFAULT '',
      status TEXT DEFAULT 'Healthy',
      created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
  );
  ```
* **`job_runs`**: Records historical telemetry for each execution.
  ```sql
  CREATE TABLE job_runs (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      job_name TEXT NOT NULL,
      status TEXT NOT NULL,
      started_at TEXT NOT NULL,
      finished_at TEXT NOT NULL,
      duration_seconds REAL NOT NULL,
      exit_code INTEGER NOT NULL,
      stdout TEXT DEFAULT '',
      stderr TEXT DEFAULT '',
      anomaly_score REAL DEFAULT 0,
      anomaly_reason TEXT DEFAULT '',
      done TEXT DEFAULT '',
      person TEXT DEFAULT ''
  );
  ```
 2. MySQL Schema (`cron DB.sql` - located in the parent directory)

* Alternative schema structured for standard MySQL instances, containing:
  * **`cron_jobs`** & **`job_execution_history`** with foreign key constraints.
  * Automated sample records for common jobs (Database Backup, Email Reports, Log Cleanup, Data Sync).
  * Useful analytical views: `dashboard_stats` and `cron_job_dashboard`.

---
  Setup & Installation
Prerequisites
* Python 3.8 or higher.
* PowerShell, Bash, or Command Prompt.
 Steps

1. **Navigate to this directory:**
   ```powershell
   cd d:\FINAL GEN\cron_job\cron_job\cron_monitor
   ```

2. **Create and activate a virtual environment:**
   * **Windows (PowerShell)**:
     ```powershell
     python -m venv .venv
     .\.venv\Scripts\Activate.ps1
     ```
   * **macOS/Linux**:
     ```bash
     python3 -m venv .venv
     source .venv/bin/activate
     ```

3. **Install Dependencies:**
   ```powershell
   pip install -r requirements.txt
   ```

4. **(Optional) Configure OpenAI Integration:**
   Set your OpenAI API Key as an environment variable to activate GPT-4o-mini powered SRE diagnostics.
   * **Windows (PowerShell)**:
     ```powershell
     $env:OPENAI_API_KEY="your-api-key-here"
     ```
   * **Linux/macOS**:
     ```bash
     export OPENAI_API_KEY="your-api-key-here"
     ```

5. **Start the Flask Server:**
   ```powershell
   python app.py
   ```
   *The server runs locally at: `http://127.0.0.1:5000/`*

---
  Run & Log Monitored Jobs

You can wrap any execution script or standard system command inside the monitored cron harness:

```powershell
# Format: python cron_wrapper.py <job_name> <command_to_execute>
python cron_wrapper.py "Database Backup" python jobs/backup_job.py
python cron_wrapper.py "System Health Check" ping 127.0.0.1
```

Once executed, `cron_wrapper.py` automatically inserts the run details, standard outputs, stderr flags, and calculated anomaly metrics into the database.

---
  Running Unit Tests

Execute the comprehensive automated test suite to ensure endpoints, models, engines, and templates match specifications:

```powershell
python -m unittest test_app.py
```

All 16 database, routing, and anomaly detection test cases will run against a safe, temporary SQLite instance.

---
 AI SRE Chatbot Prompts (Examples)

The SRE chatbot features interactive chips and handles queries like:
* *"Why did Database Backup fail?"*
* *"Show me the latest health status"*
* *"Who built this application?"*
* *"What is the anomaly rating for the last run?"*
