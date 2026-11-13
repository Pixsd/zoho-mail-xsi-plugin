"""Store non-secret mailbox selection; OAuth bootstrap remains a separate step."""
import argparse
import json
import os
from pathlib import Path
import re
import tempfile

parser = argparse.ArgumentParser()
parser.add_argument('--mailbox', required=True)
parser.add_argument('--region', choices=['com', 'eu', 'in', 'com.au', 'jp', 'ca', 'com.cn', 'sa'], default='com')
parser.add_argument('--data-dir', default=os.environ.get('ZOHO_MAIL_DATA_DIR', str(Path.home() / '.local/share/zoho-mail-xsi-plugin')))
args = parser.parse_args()
if not re.fullmatch(r'[^\s@]+@[^\s@]+\.[^\s@]+', args.mailbox):
    parser.error('A mailbox email address is required.')
private = Path(args.data_dir).expanduser().resolve() / 'private'
private.mkdir(mode=0o700, parents=True, exist_ok=True)
if private.is_symlink() or private.stat().st_mode & 0o777 != 0o700:
    parser.error('The private directory must be a real directory with mode 0700.')
fd, temp = tempfile.mkstemp(dir=private)
try:
    with os.fdopen(fd, 'w') as stream:
        os.fchmod(stream.fileno(), 0o600)
        json.dump({'mailbox': args.mailbox.lower(), 'region': args.region}, stream)
    os.replace(temp, private / 'settings.json')
finally:
    if os.path.exists(temp):
        os.unlink(temp)
print('Mailbox settings saved. OAuth credentials must be configured separately.')
