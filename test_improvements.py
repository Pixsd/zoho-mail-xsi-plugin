import os
os.environ.setdefault('ZOHO_MAILBOX', 'test@example.com')
import unittest
from unittest.mock import patch
from pathlib import Path
import tempfile
import json
import time
import anyio
import httpx
import connector as c
from mail_check import check, delivery_notice

class Improvements(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.patch = patch.object(c, 'BASE', Path(self.tmp.name)); self.patch.start()
    def tearDown(self):
        self.patch.stop(); self.tmp.cleanup()
    def client(self, handler):
        client = c.MailClient(transport=httpx.MockTransport(handler))
        client.account_id = '1'; client.access = 'test-token'; client.expiry = float('inf')
        return client
    def test_actual_total_timeout_and_retry(self):
        calls = []
        async def slow(req):
            calls.append(req)
            await anyio.sleep(2)
        client = self.client(slow)
        start = time.monotonic()
        with patch.object(c, 'REQUEST_DEADLINE', .04), self.assertRaises(c.SafeError):
            client.folders('1')
        self.assertEqual(len(calls), 2)
        self.assertLess(time.monotonic() - start, .6)
        logs = (c.BASE / 'private/errors.jsonl').read_text()
        self.assertNotIn('test-token', logs)
        self.assertEqual(len(logs.splitlines()), 2)
    def test_slow_drip_body_is_cancelled(self):
        class Drip(httpx.AsyncByteStream):
            async def __aiter__(self):
                for _ in range(100):
                    await anyio.sleep(.01)
                    yield b' '
        async def handler(req):
            return httpx.Response(200, stream=Drip())
        with patch.object(c, 'REQUEST_DEADLINE', .04), self.assertRaises(c.SafeError):
            self.client(handler).folders('1')
    def test_timeout_never_retries_write(self):
        calls = []
        def fail(req):
            calls.append(req); raise httpx.ReadTimeout('secret')
        with self.assertRaises(c.SafeError):
            self.client(fail).compose('send', '1', 'a@example.com', 's', 'b', approved=True)
        self.assertEqual(len(calls), 1)
    def test_retry_recovers_and_429_not_retried(self):
        calls = []
        def handler(req):
            calls.append(req)
            return httpx.Response(503 if len(calls) == 1 else 200, json={'data': []})
        self.assertEqual(self.client(handler).folders('1'), {'data': []})
        self.assertEqual(len(calls), 2)
        calls.clear()
        def rate(req):
            calls.append(req); return httpx.Response(429, json={})
        with self.assertRaises(c.RateLimited): self.client(rate).folders('1')
        self.assertEqual(len(calls), 1)
    def test_cross_folder_and_rome_dst(self):
        def handler(req):
            if req.url.path.endswith('/folders'):
                return httpx.Response(200, json={'data': [{'folderId': '2', 'folderName': 'Inbox'}, {'folderId': '3', 'folderName': 'Spam'}]})
            fid = req.url.params['folderId']
            return httpx.Response(200, json={'data': [{'messageId': fid, 'receivedTime': 1782900000000, 'fromAddress': 'x@example.com', 'subject': 'Delivery failed' if fid == '3' else 'Hi'}]})
        result = check(self.client(handler), '2026-01-01T00:00:00+01:00')
        self.assertTrue(result['complete']); self.assertEqual(len(result['messages']), 2)
        self.assertTrue(all(x['received_at'].endswith('+02:00') for x in result['messages']))
        self.assertEqual(result['messages'][1]['delivery_notice']['confidence'], 'suspected')
    def test_partial_failure_and_resume(self):
        broken = [True]
        def handler(req):
            if req.url.path.endswith('/folders'):
                return httpx.Response(200, json={'data': [{'folderId': '2'}, {'folderId': '3'}]})
            if req.url.params['folderId'] == '3' and broken[0]: return httpx.Response(400, json={})
            return httpx.Response(200, json={'data': []})
        client = self.client(handler)
        first = check(client, '2026-01-01T00:00:00Z')
        self.assertFalse(first['complete']); self.assertIsNone(first['next_since'])
        broken[0] = False
        self.assertTrue(check(client, '2026-01-01T00:00:00Z', first['next_cursor'])['complete'])
    def test_ambiguous_time_and_bad_cursor_rejected(self):
        client = self.client(lambda req: self.fail('must not call network'))
        for since, cursor in [('2026-10-25T02:30:00', ''), ('2026-01-01T00:00:00Z', 'bad')]:
            with self.assertRaises(c.SafeError): check(client, since, cursor)
    def test_notice_is_not_confirmed_or_linked_by_subject(self):
        self.assertIsNone(delivery_notice({'subject': 'Meeting'}))
        notice = delivery_notice({'subject': 'Delivery delayed'})
        self.assertEqual(notice['correlation'], 'unresolved')
        self.assertEqual(notice['kind'], 'delayed')
    def test_pagination_and_exact_since_boundary(self):
        timestamp = 1768000000000
        rows = [dict(messageId=str(i + 10), receivedTime=timestamp - i * 1000) for i in range(65)]
        calls = []
        def handler(req):
            if req.url.path.endswith('/folders'):
                return httpx.Response(200, json={'data': [{'folderId': '2'}]})
            start = int(req.url.params['start']); calls.append(start)
            return httpx.Response(200, json={'data': rows[start - 1:start + 49]})
        from datetime import datetime, timezone
        since = datetime.fromtimestamp((timestamp - 64000) / 1000, timezone.utc).isoformat()
        client = self.client(handler)
        first = check(client, since, max_pages=1)
        self.assertFalse(first['complete'])
        second = check(client, since, first['next_cursor'], max_pages=1)
        self.assertTrue(second['complete'])
        ids = [m['message_id'] for m in first['messages'] + second['messages']]
        self.assertEqual(len(ids), 64); self.assertEqual(len(set(ids)), 64)
        self.assertEqual(calls, [1, 51])
        self.assertTrue(all(m['received_at'].endswith('+01:00') for m in first['messages']))
    def test_large_output_can_make_progress(self):
        rows = [dict(messageId=str(i + 10), receivedTime=1768000000000, subject='x' * 998) for i in range(50)]
        def handler(req):
            if req.url.path.endswith('/folders'):
                return httpx.Response(200, json={'data': [{'folderId': '2'}]})
            start = int(req.url.params['start'])
            return httpx.Response(200, json={'data': rows[start - 1:start + 49]})
        client = self.client(handler); cursor = ''; ids = []
        for _ in range(10):
            result = check(client, '2026-01-01T00:00:00Z', cursor)
            ids.extend(m['message_id'] for m in result['messages'])
            if result['complete']: break
            cursor = result['next_cursor']
        self.assertTrue(result['complete']); self.assertEqual(len(set(ids)), 50)
    def test_diagnostic_reader_and_permissions(self):
        c.log_error('request', 'ReadTimeout', attempt=1, http_status=None)
        result = c.recent_errors(1)
        self.assertEqual(result['errors'][0]['code'], 'ReadTimeout')
        path = c.BASE / 'private/errors.jsonl'
        self.assertEqual(path.stat().st_mode & 0o777, 0o600)
        path.chmod(0o644)
        with self.assertRaises(c.SafeError): c.recent_errors()
    def test_total_budget_prevents_further_network(self):
        client = self.client(lambda req: self.fail('Budget must prevent this request'))
        c.CALL_STATE.deadline = time.monotonic() - 1
        try:
            with self.assertRaises(c.SafeError): client.folders('1')
        finally:
            c.CALL_STATE.__dict__.pop('deadline', None)
