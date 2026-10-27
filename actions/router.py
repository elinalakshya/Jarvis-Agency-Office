import json
from pathlib import Path
from typing import Any, Dict, Optional


def load_avengers_config() -> Dict[str, Any]:
    """Load avengers configuration from JSON file."""
    config_path = Path(__file__).parent.parent / "config" / "avengers.json"
    with open(config_path, "r") as f:
        return json.load(f)


def get_avenger_connector(avenger_id: str) -> Optional[Dict[str, str]]:
    """Find avenger configuration by ID."""
    config = load_avengers_config()
    for avenger in config.get("avengers", []):
        if avenger.get("id") == avenger_id:
            return avenger
    return None


def router(avenger_id: str, task: str) -> Dict[str, Any]:
    """
    Route a task to the appropriate Avenger connector.
    
    Args:
        avenger_id: Unique identifier of the Avenger (e.g., "CAP", "HAPPY")
        task: Task description or payload to execute
        
    Returns:
        Dictionary with execution result or error information
    """
    # Look up avenger configuration
    avenger = get_avenger_connector(avenger_id)
    if not avenger:
        return {
            "success": False,
            "error": f"Avenger '{avenger_id}' not found in configuration",
            "avenger_id": avenger_id
        }
    
    # Extract connector module name
    connector_module = avenger.get("connector_module")
    
    if not connector_module:
        return {
            "success": False,
            "error": f"Avenger '{avenger_id}' missing connector_module in configuration",
            "avenger_id": avenger_id
        }
    
    try:
        # Import the connectors module (all functions live in this one file)
        from avengers import connectors
        
        # Build the function name: "cap" -> "run_cap"
        func_name = f"run_{connector_module}"
        func = getattr(connectors, func_name, None)
        
        if not func:
            return {
                "success": False,
                "error": f"Function '{func_name}' not found in avengers.connectors",
                "avenger_id": avenger_id
            }
        
        # Execute the task
        result = func(task)
        
        return {
            "success": True,
            "avenger_id": avenger_id,
            "result": result
        }
        
    except ImportError as e:
        return {
            "success": False,
            "error": f"Failed to import avengers.connectors: {str(e)}",
            "avenger_id": avenger_id
        }
    except Exception as e:
        return {
            "success": False,
            "error": f"Execution failed: {str(e)}",
            "avenger_id": avenger_id
        }


# Tool registration dictionary for auto-discovery
TOOL = {
    "name": "run_avenger",
    "description": "Route a task to a specific Avenger connector based on avenger_id. Use when the user says 'run CAP', 'start HAPPY', or any Avenger name.",
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "avenger_id": {
                "type": "STRING",
                "description": "Unique identifier of the Avenger, e.g. CAP, HAPPY, IRON_MAN, PEPPER_POTTS"
            },
            "task": {
                "type": "STRING",
                "description": "Task description or payload to execute"
            }
        },
        "required": ["avenger_id", "task"]
    },
    "handler": router
}