# Validation record

2026-11-13, local macOS environment, Python 3.15.2, dependencies from `requirements.lock`.

- 34 offline tests passed (`python -m unittest -q`).
- Structural package validation passed (`python scripts/validate_package.py`).
- Real stdio MCP probe passed: server `Zoho Mail`, 10 tools, ping OK.
- Tests cover original approval/ownership/cache behavior plus HTTP header/body cancellation, exactly one transient retry, no write retry, 429 handling, Rome winter/summer offsets, exact timestamp boundaries, multi-page continuation, large-output progress, partial folder failures and sanitized log permissions.
- GitHub Actions is configured for Python 3.11 and 3.13 on Linux. Check the actual workflow run before treating those environments as verified.

No live Zoho mailbox, Grok Bot installation or Cursor installation has been tested in this development environment. No live speed improvement is claimed. The marketplace's in-app test checkbox must remain unchecked until the live acceptance procedure in `docs/SUBMISSION.md` passes.
