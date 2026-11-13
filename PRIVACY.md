# Privacy and data handling

This is a local stdio MCP server. It contacts the configured Zoho region for OAuth and Mail API calls. There is no developer-operated service, analytics endpoint or telemetry. Mail metadata and requested message content are returned to the MCP host; that host's privacy and retention policies apply.

Credentials and a shared access-token cache are stored under `ZOHO_MAIL_DATA_DIR/private` with owner-only file permissions. The default data directory is `~/.local/share/zoho-mail-xsi-plugin`. Do not share that directory or reuse it across independent mailboxes or Zoho regions.

Diagnostics contain UTC time, operation category, exception category, HTTP status, elapsed seconds, attempt number and retry decision. They omit URLs, raw exception text, credentials and message content. The diagnostic file is capped at approximately 256 KiB and reset on overflow. Remove the local data directory after stopping the connector to remove its local state; revoke the Zoho authorization separately to invalidate tokens.

No hosted OAuth onboarding or remote multi-tenant server is included. The user configures their own Zoho OAuth application and mailbox.
