# Changelog

## 0.1.0

- Package the original private connector as `zoho-mail-xsi-plugin` with reusable mailbox/region configuration.
- Add `check_new_mail`: four concurrent folder readers, Rome timestamps, pagination and explicit incomplete results.
- Add cancellable 15-second HTTP attempts, one transient read/refresh retry and a 45-second tool network budget.
- Bound OAuth lock waits; preserve shared access-token caching and account ownership checks.
- Add capped sanitized diagnostics and `get_recent_errors`.
- Flag suspected delivery failures/delays without claiming an exact Sent correlation.
- Preserve user-approved draft/send/reply tools; never automatically repeat writes.
