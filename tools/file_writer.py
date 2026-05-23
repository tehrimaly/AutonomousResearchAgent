import os
import json
import datetime
from pathlib import Path
from langchain_core.tools import tool

# All outputs land in a single folder that is mounted as a Docker volume
_OUTPUT_DIR = Path(os.getenv("OUTPUT_DIR", "/app/outputs"))


def _ensure_output_dir() -> Path:
    _OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    return _OUTPUT_DIR


@tool
def write_file(filename: str, content: str, metadata: dict | None = None) -> str:
    """Write content to a file inside the outputs directory.

    Use this to persist intermediate findings, downloaded data, generated
    code, or partial reports so they survive across agent iterations.

    Args:
        filename: Relative filename, e.g. "findings_step1.txt" or "data.json".
                  Subdirectories are created automatically.
        content:  The text content to write.
        metadata: Optional dict of extra info (e.g. source URL, timestamp).
                  Appended as a JSON comment at the top of the file.

    Returns:
        Absolute path of the written file, or an error message.
    """
    try:
        out_dir = _ensure_output_dir()

        # Prevent path traversal attacks
        safe_name = Path(filename).name  # strip any directory components
        if not safe_name:
            return "ERROR: invalid filename"

        # Add a timestamp prefix so multiple runs don't overwrite each other
        ts = datetime.datetime.utcnow().strftime("%Y%m%dT%H%M%S")
        final_name = f"{ts}_{safe_name}"
        out_path = out_dir / final_name

        header = ""
        if metadata:
            header = f"# metadata: {json.dumps(metadata)}\n"

        out_path.write_text(header + content, encoding="utf-8")
        return f"Written to: {out_path} ({out_path.stat().st_size} bytes)"

    except OSError as exc:
        return f"ERROR writing file: {exc}"


@tool
def read_file(filename: str) -> str:
    """Read a previously written output file.

    Args:
        filename: Exact filename (without timestamp prefix) to search for,
                  or the full timestamped name returned by write_file.

    Returns:
        File contents, or an error message if not found.
    """
    try:
        out_dir = _ensure_output_dir()
        candidates = sorted(out_dir.glob(f"*{Path(filename).name}"))
        if not candidates:
            return f"ERROR: no file matching '{filename}' in outputs/"
        # Return the most recently written match
        chosen = candidates[-1]
        return chosen.read_text(encoding="utf-8")
    except OSError as exc:
        return f"ERROR reading file: {exc}"
