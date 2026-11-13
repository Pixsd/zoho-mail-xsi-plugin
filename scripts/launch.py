"""Resolve installed plugin paths without relying on the host working directory."""
import json
import os
from pathlib import Path
import sys

root = Path(__file__).resolve().parents[1]
data = Path(os.environ.get('ZOHO_MAIL_DATA_DIR', str(Path.home() / '.local/share/zoho-mail-xsi-plugin'))).expanduser().resolve()
env = dict(os.environ, ZOHO_MAIL_DATA_DIR=str(data), PYTHONUNBUFFERED='1')
settings = data / 'private/settings.json'
if settings.exists():
    try:
        config = json.loads(settings.read_text())
        if not isinstance(config, dict) or set(config) - {'mailbox', 'region'}:
            raise ValueError()
        for key, target in [('mailbox', 'ZOHO_MAILBOX'), ('region', 'ZOHO_REGION')]:
            if key in config:
                if not isinstance(config[key], str):
                    raise ValueError()
                env.setdefault(target, config[key])
    except Exception:
        sys.exit('Invalid private/settings.json; run scripts/configure.py again.')
python = root / '.venv/bin/python'
if not python.is_file():
    sys.exit('Missing plugin .venv. In the installed plugin directory run: python3 -m venv .venv && .venv/bin/pip install -r requirements.lock')
os.execve(str(python), [str(python), str(root / 'connector.py'), *sys.argv[1:]], env)
