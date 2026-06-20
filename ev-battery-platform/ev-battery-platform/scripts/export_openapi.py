"""
Extract OpenAPI spec from FastAPI app and save to docs/openapi.yaml.
"""

import json
import os
import sys

# Ensure correct import path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))


def export_openapi():
    print("Generating OpenAPI schema...")
    from main import app
    schema = app.openapi()
    
    os.makedirs("docs", exist_ok=True)
    
    # First, save JSON as a backup
    json_path = os.path.join("docs", "openapi.json")
    with open(json_path, "w") as f:
        json.dump(schema, f, indent=2)
    print(f"Saved JSON schema to {json_path}")

    # Now, save as YAML
    try:
        import yaml
        yaml_path = os.path.join("docs", "openapi.yaml")
        with open(yaml_path, "w") as f:
            yaml.dump(schema, f, default_flow_style=False, sort_keys=False)
        print(f"Saved YAML schema to {yaml_path}")
    except ImportError:
        print("PyYAML not found. Installing PyYAML...")
        import subprocess
        subprocess.check_call([sys.executable, "-m", "pip", "install", "pyyaml"])
        import yaml
        yaml_path = os.path.join("docs", "openapi.yaml")
        with open(yaml_path, "w") as f:
            yaml.dump(schema, f, default_flow_style=False, sort_keys=False)
        print(f"Saved YAML schema to {yaml_path}")


if __name__ == "__main__":
    export_openapi()
