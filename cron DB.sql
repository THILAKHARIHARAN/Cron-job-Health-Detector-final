-- ==========================================
-- Cron Job Health Dashboard Database
-- ==========================================

DROP DATABASE IF EXISTS cron_health_dashboard;
CREATE DATABASE cron_health_dashboard;
USE cron_health_dashboard;

-- ==========================================
-- Table: cron_jobs
-- ==========================================

CREATE TABLE cron_jobs (
    job_id INT AUTO_INCREMENT PRIMARY KEY,
    job_name VARCHAR(100) NOT NULL,
    schedule_expression VARCHAR(50) NOT NULL,
    status ENUM('Healthy','Warning','Critical') NOT NULL DEFAULT 'Healthy',
    last_run DATETIME,
    duration_seconds INT DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        ON UPDATE CURRENT_TIMESTAMP
);

-- ==========================================
-- Table: job_execution_history
-- ==========================================

CREATE TABLE job_execution_history (
    execution_id INT AUTO_INCREMENT PRIMARY KEY,
    job_id INT NOT NULL,
    execution_time DATETIME NOT NULL,
    status ENUM('Success','Failed','Warning') NOT NULL,
    duration_seconds INT,
    error_message TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT fk_job
    FOREIGN KEY (job_id)
    REFERENCES cron_jobs(job_id)
    ON DELETE CASCADE
);

-- ==========================================
-- Sample Cron Jobs
-- ==========================================

INSERT INTO cron_jobs
(job_name, schedule_expression, status, last_run, duration_seconds)
VALUES
('Database Backup', '0 0 * * *', 'Healthy', NOW(), 45),

('Email Reports', '0 */6 * * *', 'Warning',
 DATE_SUB(NOW(), INTERVAL 2 HOUR), 120),

('Log Cleanup', '0 2 * * 0', 'Critical',
 DATE_SUB(NOW(), INTERVAL 1 DAY), 300),

('Data Sync', '*/30 * * * *', 'Healthy',
 DATE_SUB(NOW(), INTERVAL 30 MINUTE), 60),

('User Analytics', '0 */4 * * *', 'Warning',
 DATE_SUB(NOW(), INTERVAL 3 HOUR), 95),

('Invoice Generator', '0 1 * * *', 'Healthy',
 DATE_SUB(NOW(), INTERVAL 1 HOUR), 80);

-- ==========================================
-- Sample Execution History
-- ==========================================

INSERT INTO job_execution_history
(job_id, execution_time, status, duration_seconds, error_message)
VALUES
(1, NOW(), 'Success', 45, NULL),
(2, NOW(), 'Warning', 120, 'Execution took longer than expected'),
(3, NOW(), 'Failed', 300, 'Disk space insufficient'),
(4, NOW(), 'Success', 60, NULL),
(5, NOW(), 'Warning', 95, 'High memory usage detected'),
(6, NOW(), 'Success', 80, NULL);

-- ==========================================
-- Useful Views for Dashboard
-- ==========================================

CREATE VIEW dashboard_stats AS
SELECT
    SUM(CASE WHEN status='Healthy' THEN 1 ELSE 0 END) AS healthy_count,
    SUM(CASE WHEN status='Warning' THEN 1 ELSE 0 END) AS warning_count,
    SUM(CASE WHEN status='Critical' THEN 1 ELSE 0 END) AS critical_count,
    COUNT(*) AS total_jobs
FROM cron_jobs;

CREATE VIEW cron_job_dashboard AS
SELECT
    job_id,
    job_name,
    schedule_expression,
    last_run,
    status,
    duration_seconds
FROM cron_jobs;

-- ==========================================
-- Test Queries
-- ==========================================

SELECT * FROM cron_job_dashboard;
SELECT * FROM dashboard_stats;
SELECT * FROM job_execution_history;