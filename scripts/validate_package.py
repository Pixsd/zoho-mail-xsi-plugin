"""Offline structural checks, not an official marketplace certification."""
import json
from pathlib import Path
import re
import xml.etree.ElementTree as ET

root = Path(__file__).resolve().parents[1]
for file in ('.cursor-plugin/plugin.json', '.claude-plugin/plugin.json'):
    manifest = json.loads((root / file).read_text())
    assert manifest['name'] == 'zoho-mail-xsi-plugin'
    assert re.fullmatch(r'\d+\.\d+\.\d+', manifest['version'])
    assert manifest['description'] and manifest['author']['name']
for file, variable in [('mcp.json', 'CURSOR_PLUGIN_ROOT'), ('.mcp.json', 'CLAUDE_PLUGIN_ROOT')]:
    server = json.loads((root / file).read_text())['mcpServers']['zoho-mail-xsi-plugin']
    assert server['command'] == 'python3'
    assert server['args'] == ['${' + variable + '}/scripts/launch.py']
    assert (root / 'scripts/launch.py').is_file()
skill = (root / 'skills/check-mail/SKILL.md').read_text()
assert skill.startswith('---\nname: check-mail\ndescription:')
for file in ('README.md', 'LICENSE', 'PRIVACY.md', 'docs/SUBMISSION.md', 'requirements.lock'):
    assert (root / file).is_file(), file
logo = ET.parse(root / 'assets/logo.svg').getroot()
assert logo.attrib['viewBox'] == '0 0 256 256'
print('Package structure validated (not marketplace approval).')
