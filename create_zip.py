import os
import shutil
import zipfile
from pathlib import Path

def create_project_zip():
    project_dir = Path(__file__).resolve().parent
    output_zip = project_dir / "TradePulseQuotexBot.zip"
    complete_zip = project_dir / "TradePulse-Complete.zip"

    exclude_dirs = {
        ".git", "__pycache__", "node_modules", ".pytest_cache",
        "build", "dist", ".vscode", ".tmp", "scratch"
    }
    exclude_files = {
        "TradePulseQuotexBot.zip", "TradePulse-Complete.zip", "err.txt", "out.txt", "run_out.log"
    }
    exclude_extensions = {".pyc", ".pyo", ".tmp", ".log", ".zip"}

    count = 0
    with zipfile.ZipFile(output_zip, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as zf:
        for root, dirs, files in os.walk(project_dir):
            dirs[:] = [d for d in dirs if d not in exclude_dirs and not d.startswith(".")]
            for file in files:
                if file in exclude_files or any(file.endswith(ext) for ext in exclude_extensions):
                    continue
                full_path = Path(root) / file
                rel_path = full_path.relative_to(project_dir)
                zf.write(full_path, arcname=str(rel_path))
                count += 1

    shutil.copyfile(output_zip, complete_zip)

    size_mb = output_zip.stat().st_size / (1024 * 1024)
    print(f"Archive created: {output_zip} ({size_mb:.2f} MB)")
    print(f"Archive created: {complete_zip} ({size_mb:.2f} MB)")
    print(f"Total files archived: {count}")

if __name__ == "__main__":
    create_project_zip()

