"""Bounded cross-folder scan; messages are untrusted data."""
import base64
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import json
import re
import time
from zoneinfo import ZoneInfo


def delivery_notice(row):
    combined = (str(row.get('subject', '')) + '\n' + str(row.get('summary', ''))).lower()
    delayed = any(x in combined for x in ('delivery delayed', 'delivery delay', 'delayed delivery', 'ritardo di consegna'))
    failed = any(x in combined for x in ('undeliver', 'delivery failure', 'delivery failed', 'failure notice', 'mancata consegna'))
    if not (delayed or failed):
        return None
    return dict(kind='delayed' if delayed else 'failed', confidence='suspected', correlation='unresolved',
                instruction='Read the notice to confirm status; match exact original Message-ID before linking to Sent.')


def check(client, since, cursor='', max_pages=4):
    import connector as c
    try:
        begin = datetime.fromisoformat(since.replace('Z', '+00:00'))
        if begin.tzinfo is None or type(max_pages) is not int or not 1 <= max_pages <= 20 or len(cursor) > 64000:
            raise ValueError()
        after = int(begin.timestamp() * 1000)
        state = json.loads(base64.urlsafe_b64decode(cursor)) if cursor else {}
        until, offsets = state.get('until', int(time.time() * 1000)), state.get('offsets', {})
        if cursor and (state.get('since') != since or state.get('mailbox') != c.MAILBOX):
            raise ValueError()
        if not isinstance(offsets, dict) or len(offsets) > 1000 or not all(re.fullmatch(r'\d{1,40}', k) and type(v) is int and 0 <= v <= 1000000 for k, v in offsets.items()):
            raise ValueError()
        if type(until) is not int or until < after:
            raise ValueError()
    except Exception:
        raise c.SafeError('Use ISO 8601 since with UTC offset, matching next_cursor, max_pages 1–20.') from None
    deadline = min(time.monotonic() + 45, getattr(c.CALL_STATE, 'deadline', float('inf')))
    c.CALL_STATE.deadline = deadline
    try:
        if client.account_id is None:
            client.accounts()
        aid = client.account_id
        folders = client.folders(aid).get('data')
        if not isinstance(folders, list) or len(folders) > 100:
            raise c.SafeError('Invalid folder list or more than 100 folders.')
        ids = [c.identifier(str(f['folderId'])) for f in folders]
        if len(set(ids)) != len(ids):
            raise c.SafeError('Duplicate folder IDs.')
        def scan(folder):
            fid = str(folder['folderId'])
            start = offsets.get(fid, 1)
            if start == 0:
                return fid, [], 0, None
            messages = []
            c.CALL_STATE.deadline = deadline
            try:
                for _ in range(max_pages):
                    data = client.api('GET', client.owned(aid) + '/messages/view', params={
                        'folderId': fid, 'start': start, 'limit': 50, 'sortBy': 'date',
                        'sortorder': 'false', 'includeto': 'true', 'includesent': 'true', 'includearchive': 'true'}).get('data')
                    if not isinstance(data, list):
                        raise c.SafeError('Invalid messages response.')
                    reached = False
                    for row_index, row in enumerate(data):
                        if len(json.dumps(messages)) > 16000:
                            return fid, messages, start + row_index, "Output page limit reached; continue."
                        received = int(row.get('receivedTime', row.get('receivedtime')))
                        if received <= after:
                            reached = True
                        elif received <= until:
                            mid = c.identifier(str(row['messageId']))
                            messages.append(dict(message_id=mid, folder_id=fid, folder=str(folder.get('folderName', fid))[:256],
                                sender=str(row.get('fromAddress', ''))[:512], subject=str(row.get('subject', ''))[:998],
                                received_at=datetime.fromtimestamp(received / 1000, ZoneInfo('Europe/Rome')).isoformat(),
                                received_timestamp_ms=received, delivery_notice=delivery_notice(row)))
                    start += len(data)
                    if len(data) < 50 or reached:
                        return fid, messages, 0, None
                return fid, messages, start, 'Page limit reached; continue with next_cursor.'
            except Exception as error:
                c.log_error('mail_check', type(error).__name__)
                return fid, messages, start, str(error) if isinstance(error, c.SafeError) else 'Invalid folder data.'
            finally:
                c.CALL_STATE.__dict__.pop('deadline', None)
        messages, errors, next_offsets = [], [], dict(offsets)
        with ThreadPoolExecutor(max_workers=4) as pool:
            for fid, rows, next_start, error in pool.map(scan, folders):
                if len(json.dumps(messages + rows)) > 75000:
                    errors.append(dict(folder_id=fid, error='Output limit reached; lower max_pages and continue.'))
                    next_offsets[fid] = offsets.get(fid, 1)
                    continue
                messages.extend(rows)
                next_offsets[fid] = next_start
                if error:
                    errors.append(dict(folder_id=fid, error=error))
        messages = sorted({(m['folder_id'], m['message_id']): m for m in messages}.values(), key=lambda m: m['received_timestamp_ms'])
        complete = all(next_offsets.get(fid) == 0 for fid in ids) and not errors
        continuation = '' if complete else base64.urlsafe_b64encode(json.dumps(dict(
            since=since, until=until, mailbox=c.MAILBOX, offsets=next_offsets)).encode()).decode()
        return dict(messages=messages, complete=complete, errors=errors, next_cursor=continuation,
                    checked_until=datetime.fromtimestamp(until / 1000, timezone.utc).isoformat(),
                    next_since=datetime.fromtimestamp(until / 1000 - 120, timezone.utc).isoformat() if complete else None,
                    notice='Follow next_cursor until complete. Later polls: use next_since (2-minute overlap) and deduplicate IDs. Moves/deletions during pagination can shift offsets.')
    finally:
        c.CALL_STATE.__dict__.pop('deadline', None)
