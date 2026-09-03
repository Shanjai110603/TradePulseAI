import os
import zipfile
from pathlib import Path

def create_project_zip():
    project_dir = Path(r"c:\Users\shanj\OneDrive\Desktop\Ai-telegrambot").resolve()
    output_zip = project_dir / "TradePulseQuotexBot.zip"

    exclude_dirs = {".git", "__pycache__", "node_modules", ".pytest_cache", "build", ".tmp"}
    exclude_files = {"TradePulseQuotexBot.zip", "create_zip.py"}
    exclude_extensions = {".pyc", ".pyo", ".tmp"}

    with zipfile.ZipFile(output_zip, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as zf:
        for root, dirs, files in os.walk(project_dir):
            dirs[:] = [d for d in dirs if d not in exclude_dirs and not d.startswith(".")]
            for file in files:
                if file in exclude_files or any(file.endswith(ext) for ext in exclude_extensions):
                    continue
                full_path = Path(root) / file
                rel_path = full_path.relative_to(project_dir)
                if "scanner\\build" in str(rel_path) or "scanner/build" in str(rel_path):
                    continue
                try:
                    zf.write(full_path, arcname=str(rel_path))
                except Exception:
                    pass

    print(f"Zip updated successfully: {output_zip.stat().st_size / (1024*1024):.2f} MB")

if __name__ == "__main__":
    create_project_zip()
