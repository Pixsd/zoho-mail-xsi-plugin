"""Regression for the live-reported archive-flag behavior; no live Zoho access."""
import os
os.environ.setdefault('ZOHO_MAILBOX', 'test@example.com')
from datetime import datetime, timezone
import unittest
from unittest.mock import patch
import httpx
import connector as c
from mail_check import check


class ArchiveFlagRegression(unittest.TestCase):
    def test_check_matches_folder_listing_when_archive_flag_hides_mail(self):
        now_ms = 1768000000000
        calls = []
        rows = {
            '2': [dict(messageId=str(200 + i), receivedTime=now_ms - 3600000,
                       fromAddress='postmaster@example.com',
                       subject='Mail Delivery Status Notification (Delay)') for i in range(3)],
            '3': [dict(messageId=str(300 + i), receivedTime=now_ms - 3600000,
                       fromAddress='test@example.com', subject='Proposal') for i in range(8)],
        }

        def handler(request):
            if request.url.path.endswith('/folders'):
                return httpx.Response(200, json={'data': [
                    {'folderId': '2', 'folderName': 'Inbox'},
                    {'folderId': '3', 'folderName': 'Sent'},
                    {'folderId': '4', 'folderName': 'Empty'},
                ]})
            params = request.url.params
            calls.append(dict(params))
            # Model the reported HTTP 200 response, not an invented API error.
            data = [] if params.get('includearchive') == 'true' else rows.get(params['folderId'], [])
            return httpx.Response(200, json={'data': data})

        client = c.MailClient(transport=httpx.MockTransport(handler))
        client.account_id = '1'
        client.access, client.expiry = 'test-token', float('inf')
        expected = {str(row['messageId']) for fid in ('2', '3')
                    for row in client.list_messages('1', fid)['data']}
        since = datetime.fromtimestamp(now_ms / 1000 - 7200, timezone.utc).isoformat()
        with patch('mail_check.time.time', return_value=now_ms / 1000):
            result = check(client, since)
        self.assertEqual({m['message_id'] for m in result['messages']}, expected)
        self.assertEqual(len(result['messages']), 11)
        notices = {m['message_id']: m['delivery_notice'] for m in result['messages']
                   if m['delivery_notice'] is not None}
        self.assertEqual(set(notices), {'200', '201', '202'})
        for notice in notices.values():
            self.assertEqual(notice['kind'], 'delayed')
            self.assertEqual(notice['confidence'], 'suspected')
            self.assertEqual(notice['correlation'], 'unresolved')
        self.assertTrue(result['complete'])
        self.assertEqual(result['errors'], [])
        self.assertEqual(result['next_cursor'], '')
        self.assertTrue(all('includearchive' not in params for params in calls))

    def test_genuinely_empty_folder_still_completes(self):
        def handler(request):
            data = [{'folderId': '2', 'folderName': 'Empty'}] if request.url.path.endswith('/folders') else []
            return httpx.Response(200, json={'data': data})
        client = c.MailClient(transport=httpx.MockTransport(handler))
        client.account_id = '1'
        client.access, client.expiry = 'test-token', float('inf')
        result = check(client, '2026-01-01T00:00:00Z')
        self.assertEqual(result['messages'], [])
        self.assertTrue(result['complete'])
        self.assertEqual(result['errors'], [])


if __name__ == '__main__':
    unittest.main()
