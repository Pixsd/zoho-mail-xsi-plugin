# Zoho Mail XSI Plugin

Independent Zoho Mail MCP connector for Grok Bot, with a mail-check skill and compatible plugin metadata. Not affiliated with or endorsed by Zoho, xAI or SpaceXSI.

**Status: development release; offline tests pass. A live Zoho/Grok Bot acceptance test is still required before marketplace submission.**

## What it does

- `check_new_mail(since)` checks every folder returned by Zoho, including custom folders, Sent and Spam/Trash when present. It includes read messages, returns sender/subject/folder/time in Europe/Rome, and flags suspected delivery failures or delays.
- Up to four folders are read concurrently. A normal small check takes one host tool call, with several Zoho API requests internally. There is no promised live latency benchmark.
- Each HTTP attempt has a cancellable 15-second deadline covering connect, headers and streamed body. Transient read and refresh failures get one retry. HTTP 429 and permanent errors do not. Writes and authorization-code exchange are never repeated automatically.
- Shared token cache, bounded OAuth lock waits, a 45-second tool network budget, and sanitized local diagnostics.
- Read/search messages and explicitly approved draft/send/reply operations. No delete, forwarding, attachments or administrator tools.

## Repository layout

```text
.cursor-plugin/plugin.json  Cursor plugin manifest
.claude-plugin/plugin.json  Compatibility manifest (also supported by Grok Build)
mcp.json                    Cursor MCP entry
.mcp.json                   Claude/Grok Build compatibility MCP entry
skills/check-mail/SKILL.md  Mail-check workflow
connector.py                MCP server and Zoho HTTP/OAuth client
mail_check.py               Cross-folder scan
scripts/                    Configuration, launch and package validation
assets/logo.svg             Square logo with a background plate
docs/SUBMISSION.md           xAI form fields and acceptance checklist
```

The Grok Bot marketplace accepts a public GitHub repository or MCP endpoint. Its submission page does not specify a separate mandatory `xai-plugin.json`. This repository provides a local MCP server with documented command installation. Cursor/Claude-compatible metadata is additional packaging, not evidence of marketplace approval. See [submission notes](docs/SUBMISSION.md).

## Install on the computer that runs the MCP server

Linux or macOS, Python 3.11+. Windows is not currently supported (`fcntl` and POSIX file permissions are used).

```bash
git clone https://github.com/Pixsd/zoho-mail-xsi-plugin.git
cd zoho-mail-xsi-plugin
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.lock
python3 scripts/configure.py --mailbox you@example.com --region com
```

Use the region that owns your Zoho account, not your physical location. For a Zoho EU account use `--region eu`. Other accepted suffixes are `in`, `com.au`, `jp`, `ca`, `com.cn`, `sa`; actual access depends on your account and has not been tested in every region.

Configuration is written to `~/.local/share/zoho-mail-xsi-plugin/private/settings.json`. Credentials are separate. For multiple installations/mailboxes, set a different absolute `ZOHO_MAIL_DATA_DIR` for each one, both during setup and in the host's launch environment. Inherited `ZOHO_MAILBOX` and `ZOHO_REGION` override the saved settings.

### OAuth credentials

Use your own Zoho OAuth client and authorization grant. Required scopes for all tools:

```text
ZohoMail.accounts.READ,ZohoMail.folders.READ,ZohoMail.messages.READ,ZohoMail.messages.CREATE
```

For read-only use, omit `ZohoMail.messages.CREATE`; write tools remain listed but Zoho will reject writes. Follow [Zoho's OAuth documentation](https://www.zoho.com/mail/help/api/using-oauth-2.html) to generate a grant with these scopes in the correct data center.

Place the client JSON (`client_id`, `client_secret`) and authorization code in separate owned regular files with mode `0600`, outside the repository. Pass file paths, never secret values:

```bash
python3 scripts/launch.py --bootstrap --client-json /secure/path/client.json --code-file /secure/path/code.txt
```

Bootstrap writes `private/credentials.json`; it refuses to overwrite existing credentials. Remove the short-lived input files after successful setup. Do not commit credentials, settings, logs, caches or mailbox exports.

### Existing connector migration

Keep the original installation available for rollback. Install this version in a separate directory. Configure the same mailbox and Zoho region. Securely copy the existing `private/credentials.json` into the new data directory's `private/credentials.json` (directory `0700`, file `0600`). Do not copy logs or the access-token cache. Stop the old server before switching registration; do not delete credentials until the new connector is verified. A fresh access token will be obtained when needed.

## Connect Grok Bot

On Grok Bot's computer, install the repository and dependencies as above. In **Connect apps → Add a custom connector**, select **Command**:

- Name: `zoho-mail-xsi-plugin`
- Command: the absolute path to the host's `python3`
- Arguments: `["/absolute/path/to/zoho-mail-xsi-plugin/scripts/launch.py"]`

Use paths on the Bot's computer, not your laptop. If using a custom data directory, provide `ZOHO_MAIL_DATA_DIR` in the command server environment. A Bot can also register this same command as a custom MCP server. See the [official Grok Bot instructions](https://docs.x.ai/grok-bot/computer-and-apps).

The launcher locates its adjacent `.venv` regardless of the host working directory. Startup and tool discovery do not access Zoho. There should be **10 tools**. The separate host skill can be installed from `skills/check-mail/SKILL.md`; plain command registration does not automatically install skills.

### Cursor / Grok Build packaging

The plugin manifests and MCP entries use the respective plugin-root variable. Install dependencies in the **installed plugin directory**, then configure the external data directory once. Restart the host after setup. The default launcher uses `python3` from PATH; command-only registration above also allows an absolute interpreter path. In-app plugin-cache installation has not yet been acceptance-tested; do not claim one-click onboarding.

## Usage

```json
{"since":"2026-11-13T08:00:00+01:00"}
```

Call `check_new_mail`. Times include the Rome UTC offset, including daylight saving. Naive local times are rejected because the autumn clock change is ambiguous.

When `complete` is false, keep the original `since` and pass `next_cursor` in another call. Some folders may already have returned valid results. Do not advance a saved watermark until the scan completes. After completion, `next_since` keeps a two-minute overlap for the next poll; deduplicate `(folder_id, message_id)` across results. Cursor contents are local scan state, not an authorization token.

The scanner reads 50 messages per page, up to four pages per folder per call by default, and caps output size. It supports at most 100 folders. It returns a continuation rather than silently omitting unfinished folders. Folder pagination is not a transactional snapshot: mail moved/deleted during a scan may shift offsets; rescan the interval if that happens. Very late-indexed mail may require a wider overlap.

A `delivery_notice` is a **suspected** bounce or delay based on subject/summary. Read the notice to confirm. Exact automatic linking to the original Sent message is **not implemented** in this release; no false match is inferred from similar subjects.

Use `search_messages` with Zoho syntax, e.g. `entire:MacRumors`, not a bare word. Call `get_recent_errors` for up to 50 sanitized entries after failures. See [privacy](PRIVACY.md) for retention.

Writes require explicit approval of exact recipients/content and `approved=true`. This flag is an assertion by the host, not a security boundary against a compromised host. After a write timeout, check Sent/Drafts before considering a new user-approved attempt.

## Validate

```bash
.venv/bin/python -m unittest -v
.venv/bin/python scripts/validate_package.py
.venv/bin/python mcp_probe.py
```

Tests use fake credentials and HTTP mocks. They include an actual SDK stdio handshake, timeout cancellation, retries, token cache isolation and partial-result continuation. No live mailbox is read and no messages are sent.

A 15-second HTTP deadline does not fix a host-side MCP discovery/transport hang. Compare connector diagnostics with host logs. Tool work stays off the MCP event loop so discovery/ping can continue during a slow request. A request plus retry can take roughly 30 seconds; a multi-request tool can consume its 45-second network budget. Scheduling and local filesystem overhead are outside that budget.

## Publish

See [docs/SUBMISSION.md](docs/SUBMISSION.md) for the xAI form, proposed description and required live tests. This project is MIT licensed; see [LICENSE](LICENSE).
