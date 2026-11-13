# Changelog

## 0.1.2

- Recognize the subject `Mail Delivery Status Notification (Delay)` as a suspected delivery delay. Add regression coverage for the three notices reported in Inbox.

## 0.1.1

- Omit `includearchive=true` from per-folder mail checks. The live report showed that this flag made Zoho return HTTP 200 with empty results for folders containing ordinary messages, causing false complete/empty scans.
- Add regression coverage reproducing that response behavior: three Inbox delivery delays and eight Sent messages must match ordinary folder listing. Preserve legitimate empty-folder completion.
- Treat archived-message coverage as unverified. Do not interpret this workaround as verified inclusion of archived mail.
- After upgrading, start a fresh scan without an old cursor, from the last known-good check (or earlier), and deduplicate IDs. A watermark from a faulty empty scan must not skip the affected interval.

## 0.1.0

- Package the original private connector as `zoho-mail-xsi-plugin` with reusable mailbox/region configuration.
- Add `check_new_mail`: four concurrent folder readers, Rome timestamps, pagination and explicit incomplete results.
- Add cancellable 15-second HTTP attempts, one transient read/refresh retry and a 45-second tool network budget.
- Bound OAuth lock waits; preserve shared access-token caching and account ownership checks.
- Add capped sanitized diagnostics and `get_recent_errors`.
- Flag suspected delivery failures/delays without claiming an exact Sent correlation.
- Preserve user-approved draft/send/reply tools; never automatically repeat writes.
