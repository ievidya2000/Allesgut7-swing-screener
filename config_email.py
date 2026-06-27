"""Email configuration for notifications."""

import os
import json
from pathlib import Path

EMAIL_CONFIG_FILE = Path(__file__).parent.parent / "email_config.json"

DEFAULT_CONFIG = {
    "smtp_server": "smtp.gmail.com",
    "smtp_port": 587,
    "smtp_username": "",
    "smtp_password": "",
    "from_email": "",
    "to_email": "",
    "use_tls": True,
}


def load_email_config():
    config = DEFAULT_CONFIG.copy()

    # Priority 1: Streamlit secrets (cloud)
    try:
        import streamlit as st
        if hasattr(st, 'secrets') and 'smtp' in st.secrets:
            s = st.secrets['smtp']
            config["smtp_server"] = s.get("server", config["smtp_server"])
            config["smtp_port"] = int(s.get("port", config["smtp_port"]))
            config["smtp_username"] = s.get("username", "")
            config["smtp_password"] = s.get("password", "")
            config["from_email"] = s.get("from_email", "")
            config["to_email"] = s.get("to_email", "")
            return config
    except Exception:
        pass

    # Priority 2: Environment variables
    env_mapping = {
        "SMTP_SERVER": "smtp_server",
        "SMTP_PORT": "smtp_port",
        "SMTP_USERNAME": "smtp_username",
        "SMTP_PASSWORD": "smtp_password",
        "FROM_EMAIL": "from_email",
        "TO_EMAIL": "to_email",
    }
    for env_key, config_key in env_mapping.items():
        env_val = os.getenv(env_key)
        if env_val:
            config[config_key] = env_val

    if config["smtp_port"]:
        config["smtp_port"] = int(config["smtp_port"])

    # Priority 3: Local file (development fallback)
    if not config["smtp_username"] and EMAIL_CONFIG_FILE.exists():
        try:
            with open(EMAIL_CONFIG_FILE, 'r') as f:
                file_config = json.load(f)
            config.update(file_config)
        except Exception:
            pass

    return config


def save_email_config(config):
    with open(EMAIL_CONFIG_FILE, 'w') as f:
        json.dump(config, f, indent=2)


def is_email_configured():
    config = load_email_config()
    return bool(config.get("smtp_username") and config.get("smtp_password") and config.get("to_email"))
