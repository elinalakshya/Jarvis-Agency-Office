import subprocess
import sys

def install_package(parameters=None, **kwargs):
    package_name = (parameters or {}).get("package_name", "").strip()
    
    if not package_name:
        return "Error: No package_name provided."
    
    # Safety: only allow basic package names (letters, numbers, dashes, underscores)
    if not all(c.isalnum() or c in "-_." for c in package_name):
        return f"BOUNDARY VIOLATION: Invalid package name '{package_name}'"

    print(f"[Installer] Running: pip install {package_name}")
    try:
        result = subprocess.run(
            [sys.executable, "-m", "pip", "install", package_name],
            capture_output=True,
            text=True,
            timeout=120  # 2 minute timeout
        )
        
        if result.returncode == 0:
            return f"SUCCESS: Installed '{package_name}' successfully."
        else:
            error = result.stderr.strip()[-500:]  # last 500 chars of error
            return f"FAILED to install '{package_name}'.\nError:\n{error}"
            
    except subprocess.TimeoutExpired:
        return f"FAILED: Installation of '{package_name}' timed out after 120 seconds."
    except Exception as e:
        return f"FAILED: {e}"

TOOL = {
    "name": "install_package",
    "description": "Install a Python package using pip. Use this when a test fails with 'ModuleNotFoundError'. Example: install_package('pandas').",
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "package_name": {"type": "STRING", "description": "The exact name of the Python package to install, e.g. 'requests', 'pandas', 'python-dotenv'"}
        },
        "required": ["package_name"]
    },
    "handler": install_package
}