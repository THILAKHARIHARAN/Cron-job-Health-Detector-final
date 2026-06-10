from pathlib import Path


backup_dir = Path(__file__).resolve().parents[1] / "backups"
backup_dir.mkdir(exist_ok=True)
(backup_dir / "backup.txt").write_text("backup completed\n", encoding="utf-8")

print(f"backup written to {backup_dir}")
