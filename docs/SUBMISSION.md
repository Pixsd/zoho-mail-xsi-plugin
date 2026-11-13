# xAI marketplace submission

Checked against official sources on 2026-11-13. Repository publication and marketplace submission are separate actions. Publishing this source does not mean xAI has approved it.

## Confirmed requirements and format choice

The [Grok Bot submission form](https://x.ai/bot/marketplace/submit-a-plugin) accepts an MCP server URL **or public GitHub repository**. It requests publisher identity, organization, a square SVG/PNG logo URL with a background plate, destination(s), description, testing instructions and confirmation of local **and in-app** testing. Submission also accepts the linked publisher terms.

[Bot documentation](https://docs.x.ai/grok-bot/computer-and-apps) supports custom MCP registration by command/arguments on its computer. This project uses that route. It does not provide a hosted HTTPS endpoint or hosted OAuth service.

[Cursor's plugin reference](https://cursor.com/docs/reference/plugins) documents `.cursor-plugin/plugin.json`, `mcp.json`, skills and a repository-based distribution route. We include that layout. [Grok Build's documentation](https://docs.x.ai/build/features/skills-plugins-marketplaces) describes Claude-compatible plugins; `.claude-plugin/plugin.json` and `.mcp.json` provide that compatibility. These are supporting formats, not a claim that Grok Build requirements are Grok Bot's submission requirements. The Bot form itself does not prescribe a dedicated manifest filename.

## Proposed form values

| Field | Value |
|---|---|
| First / last name | Publisher to fill in |
| Work email | Publisher to fill in |
| Organization name / handle | Publisher to fill in; handle lowercase with no spaces |
| Website | https://github.com/Pixsd/zoho-mail-xsi-plugin |
| Logotype URL | https://raw.githubusercontent.com/Pixsd/zoho-mail-xsi-plugin/main/assets/logo.svg |
| Listing destination | Grok Bot (select Cursor only after testing there too) |
| Public GitHub Repository | https://github.com/Pixsd/zoho-mail-xsi-plugin |

### Brief description

Independent Zoho Mail connector for Grok Bot. Check new messages across folders in one tool call, with sender, subject, folder and Europe/Rome timestamps. Includes bounded HTTP requests, one transient read retry, local diagnostics, message search/read and explicitly approved draft/send/reply tools. Uses a user-configured Zoho OAuth client on the Bot's computer.

### Testing instructions

Clone the repository on the Bot's computer. Follow README installation and OAuth setup with a reviewer-owned Zoho test account. Run the offline tests and package validator. Register `python3 /absolute/path/scripts/launch.py` as a Command connector. Confirm 10 tools, then call `check_new_mail` with an explicit-offset timestamp covering seeded test emails in Inbox, a custom folder and Spam. Compare sender, subject, folder and Rome time to Zoho. Follow any `next_cursor` until `complete=true`. Use `get_recent_errors` for failures. Writes require explicit approval of the exact test message; never retry a timed-out write automatically. No shared test credentials are embedded.

## Acceptance record (complete before submitting)

- [x] Offline unit/integration tests executed locally (see TESTING.md).
- [x] Repository includes install steps, metadata, logo, privacy explanation and license.
- [ ] Install this exact release on Grok Bot's computer.
- [ ] Complete OAuth against a reviewer/user-owned test mailbox.
- [ ] Verify cold start, tool discovery and a normal single-call mail check.
- [ ] Verify Inbox, custom folders, Spam/Trash and Sent coverage against Zoho UI.
- [ ] Investigate archived-message coverage separately; version 0.1.1 does not claim it.
- [ ] Re-run the reported 11-message interval after upgrading, with no old cursor or watermark; confirm all three Inbox notices and eight Sent messages.
- [ ] Verify multiple pages/continuation, timestamp boundary and daylight saving examples.
- [ ] Compare live timing before/after; record sample size, mailbox size and cold/warm token state. No speed claim is made yet.
- [ ] Confirm diagnostics on an intentional test failure and responsiveness of discovery/ping.
- [ ] If testing writes, approve a specific test message to an address you control; verify exactly one message. Do not use production recipients.
- [ ] Fill publisher identity fields and confirm rights to publish the source/logo.
- [ ] Check the form's local-and-in-app-tested box only after the above live checks pass.
- [ ] Review the linked publisher terms and submit through the form.

Do not include private message content, credentials or raw production logs in public test evidence. Automatic exact bounce-to-Sent correlation remains a documented limitation; it is not part of the release claim.
