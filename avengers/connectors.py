import requests
import json
import subprocess
import logging
from pathlib import Path
from typing import Optional

# Configure module logger
logger = logging.getLogger(__name__)

# Path to the avengers configuration file
CONFIG_PATH = Path(__file__).parent.parent / "config" / "avengers.json"


def _load_avenger_config(avenger_key: str) -> Optional[dict]:
    """
    Load and validate a single avenger's configuration from the JSON file.
    Case-insensitive matching for the avenger ID.
    """
    if not CONFIG_PATH.exists():
        logger.error("Config file not found at: %s", CONFIG_PATH)
        return None

    try:
        with CONFIG_PATH.open("r", encoding="utf-8") as f:
            config = json.load(f)
    except json.JSONDecodeError as e:
        logger.error("Failed to parse JSON config: %s", e)
        return None
    except OSError as e:
        logger.error("Error reading config file: %s", e)
        return None

    # Find the avenger case-insensitively
    for a in config.get("avengers", []):
        if a.get("id", "").upper() == avenger_key.upper():
            # Check if it's active
            if a.get("status", "").lower() != "active":
                logger.error("Avenger '%s' is not active.", avenger_key)
                return None
            return a

    logger.error("Avenger '%s' not found in config.", avenger_key)
    return None


def _execute_avenger_repo(repo_path: str, avenger_key: str) -> str:
    """
    Execute the avenger's repository via subprocess.
    Supports running a folder (looks for main.py) or a specific file.
    """
    path = Path(repo_path)

    if not path.exists():
        return f"FAILED: Repository path does not exist: {repo_path}"

    # If it's a folder, try to find the main entry point
    if path.is_dir():
        possible_mains = ["main.py", "app.py", "run.py", "index.js"]
        main_file = None
        for name in possible_mains:
            candidate = path / name
            if candidate.exists():
                main_file = candidate
                break
        
        if not main_file:
            return f"FAILED: No main entry point (main.py, app.py, etc.) found in folder: {repo_path}"
        
        target_file = main_file
    else:
        target_file = path

    # Determine execution command based on file extension
    suffix = target_file.suffix.lower()
    if suffix == ".py":
        cmd = ["python", str(target_file)]
    elif suffix == ".sh":
        cmd = ["bash", str(target_file)]
    elif suffix in {".js", ".ts"}:
        cmd = ["node", str(target_file)]
    else:
        cmd = [str(target_file)]

    logger.info("Executing %s: %s", avenger_key, " ".join(cmd))

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=300,  # 5-minute timeout
            cwd=str(target_file.parent),
        )
    except subprocess.TimeoutExpired:
        return f"FAILED: {avenger_key} execution timed out after 300 seconds"
    except PermissionError:
        return f"FAILED: Permission denied executing {repo_path}"
    except FileNotFoundError:
        return f"FAILED: Interpreter not found for {repo_path}"
    except OSError as e:
        return f"FAILED: OS error executing {avenger_key}: {e}"

    if result.returncode == 0:
        logger.info("%s completed successfully", avenger_key)
        return f"SUCCESS: {avenger_key} completed\nOutput: {result.stdout[:500]}"
    else:
        error_msg = result.stderr.strip() if result.stderr else "Unknown error"
        logger.error("%s failed with exit code %d: %s", avenger_key, result.returncode, error_msg)
        return f"FAILED: {avenger_key} exited with code {result.returncode}\nError: {error_msg[:500]}"


import requests  # Add this at the top of the file if not there

import requests  # Make sure this is at the top of the file

def _run_avenger(avenger_key: str, task: str = "") -> str:
    """Generic function to run an avenger by key."""
    config = _load_avenger_config(avenger_key)
    if not config:
        return f"FAILED: Could not load config for {avenger_key}"

    status = config.get("status", "").lower()
    if status != "active":
        return f"SKIPPED: {avenger_key} status is '{status}', not 'active'"

    # Special case: CAP uses the YouTube Agent API
    if avenger_key.upper() == "CAP":
        try:
            headers = {"x-api-key": "jarvis-secret-key-2026"}
            response = requests.post(
                "http://localhost:3456/generate",
                json={"topic": task or "AI agencies"},
                headers=headers,
                timeout=10
            )
            if response.status_code in (200, 202):
                return f"SUCCESS: CAP triggered. Job queued. Response: {response.text[:200]}"
            else:
                return f"FAILED: CAP API returned {response.status_code}: {response.text[:200]}"
        except requests.exceptions.ConnectionError:
            return "FAILED: YouTube Agent is not running. Start it with 'npm start' first."
        except Exception as e:
            return f"FAILED: CAP API error: {e}"

    # Default: run as subprocess (for other Avengers)
    repo_path = config.get("repo_path", "")
    if not repo_path:
        return f"FAILED: {avenger_key} has empty repo_path"

    return _execute_avenger_repo(repo_path, avenger_key)


# Public API functions for each avenger
def run_cap(task: str) -> str:
    logger.debug("run_cap called with task: %s", task)
    return _run_avenger("CAP", task)

def run_happy(task: str) -> str:
    logger.debug("run_happy called with task: %s", task)
    return _run_avenger("HAPPY", task)

def run_iron_man(task: str) -> str:
    logger.debug("run_iron_man called with task: %s", task)
    return _run_avenger("IRON_MAN", task)

def run_thor(task: str) -> str:
    logger.debug("run_thor called with task: %s", task)
    return _run_avenger("THOR", task)

def run_doctor_strange(task: str) -> str:
    logger.debug("run_doctor_strange called with task: %s", task)
    return _run_avenger("DOCTOR_STRANGE", task)

def run_hawk_eye(task: str) -> str:
    logger.debug("run_hawk_eye called with task: %s", task)
    return _run_avenger("HAWK_EYE", task)

def run_spider_man(task: str) -> str:
    logger.debug("run_spider_man called with task: %s", task)
    return _run_avenger("SPIDER_MAN", task)

def run_black_panther(task: str) -> str:
    logger.debug("run_black_panther called with task: %s", task)
    return _run_avenger("BLACK_PANTHER", task)

if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)
    print("Testing CAP...")
    print(run_cap("test_task"))

if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)
    print("Testing CAP...")
    print(run_cap("test_task"))