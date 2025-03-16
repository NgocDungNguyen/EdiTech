import os
import json
from pathlib import Path

# Base paths
BASE_DIR = Path(__file__).resolve().parent.parent.parent
DATA_DIR = BASE_DIR / "data"
MODELS_DIR = DATA_DIR / "models"
BACKUPS_DIR = DATA_DIR / "backups"
DATABASE_PATH = DATA_DIR / "edison_vision.db"
ICONS_DIR = BASE_DIR / "app" / "assets" / "icons"

# Ensure directories exist
for dir_path in [DATA_DIR, MODELS_DIR, BACKUPS_DIR, ICONS_DIR]:
    dir_path.mkdir(parents=True, exist_ok=True)

# Default configuration
DEFAULT_CONFIG = {
    "database": {
        "path": str(DATABASE_PATH)
    },
    "camera": {
        "device_id": 0,
        "frame_width": 640,
        "frame_height": 480,
        "fps": 30
    },
    "face_recognition": {
        "tolerance": 0.6,
        "model": "hog"  # or 'cnn' for GPU
    },
    "attendance": {
        "default_checkin_window": 5  # minutes
    },
    "backup": {
        "auto_backup": True,
        "backup_interval": 24  # hours
    }
}

def load_config():
    """Load configuration from config.json or create default if not exists."""
    config_path = BASE_DIR / "config.json"
    
    if not config_path.exists():
        # Create default config file
        with open(config_path, 'w') as f:
            json.dump(DEFAULT_CONFIG, f, indent=4)
        return DEFAULT_CONFIG
    
    # Load existing config
    with open(config_path, 'r') as f:
        config = json.load(f)
    
    # Update with any missing default values
    for key, value in DEFAULT_CONFIG.items():
        if key not in config:
            config[key] = value
        elif isinstance(value, dict):
            for sub_key, sub_value in value.items():
                if sub_key not in config[key]:
                    config[key][sub_key] = sub_value
    
    return config
