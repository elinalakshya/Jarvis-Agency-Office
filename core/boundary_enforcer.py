import json
from pathlib import Path

BOUNDARIES_PATH = Path(__file__).resolve().parent.parent / "config" / "boundaries.json"

def load_boundaries():
    try:
        return json.loads(BOUNDARIES_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {"allowed_write_paths": [], "allow_delete": False}

def is_path_allowed(target_path: str) -> bool:
    """Checks if a file path is safe to write to."""
    bounds = load_boundaries()
    target = Path(target_path).resolve()
    
    # Check forbidden first
    for forbidden in bounds.get("forbidden_paths", []):
        if str(target).lower().startswith(str(Path(forbidden).resolve()).lower()):
            return False
            
    # Check allowed
    for allowed in bounds.get("allowed_write_paths", []):
        if str(target).lower().startswith(str(Path(allowed).resolve()).lower()):
            return True
            
    return False

def can_delete() -> bool:
    return load_boundaries().get("allow_delete", False)