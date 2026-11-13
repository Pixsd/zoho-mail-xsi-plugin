# Validation record

2026-11-13, local macOS environment, Python 3.15.2, dependencies from `requirements.lock`.

- 36 offline tests passed (`python -m unittest -q`).
- Structural package validation passed (`python scripts/validate_package.py`).
- Real stdio MCP probe passed: server `Zoho Mail`, 10 tools, ping OK.
- Tests cover original approval/ownership/cache behavior plus HTTP header/body cancellation, exactly one transient retry, no write retry, 429 handling, Rome winter/summer offsets, exact timestamp boundaries, multi-page continuation, large-output progress, partial folder failures and sanitized log permissions.
- GitHub Actions is configured for Python 3.11 and 3.13 on Linux. Check the actual workflow run before treating those environments as verified.

No live Zoho mailbox, Grok Bot installation or Cursor installation has been tested in this development environment. No live speed improvement is claimed. The marketplace's in-app test checkbox must remain unchecked until the live acceptance procedure in `docs/SUBMISSION.md` passes.

## 0.1.1 archive-flag regression

A user-provided Grok Bot report for 0.1.0 described an HTTP 200 empty result with `includearchive=true`, despite 11 messages being visible through ordinary folder listing. The new regression models precisely that response: it failed on 0.1.0 and must return all 11 IDs after removing the flag. A second test checks legitimate empty folders. This is a mocked regression, not an independent live Zoho verification. Repeat the affected interval in Grok Bot before switching connectors.
