import asyncio
import contextlib
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import tempfile
import unittest
from urllib.parse import parse_qs
from unittest.mock import patch
import httpx
os.environ.setdefault('ZOHO_MAILBOX', 'test@example.com')
import connector as c

CREDS = {'client_id': 'mock-client-123', 'client_secret': 'mock-secret-456', 'refresh_token': 'mock-refresh-789'}
ACCOUNT = {'accountId': '123', 'primaryEmailAddress': c.MAILBOX, 'type': 'ZOHO_ACCOUNT', 'enabled': True}

class Tests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.base = Path(self.temp.name)
        self.patcher = patch.object(c, 'BASE', self.base)
        self.patcher.start()
        self.calls = []
        self.account = dict(ACCOUNT)
        def handler(req):
            self.calls.append(req)
            if str(req.url) == c.TOKEN:
                return httpx.Response(200, json={'access_token': 'mock-access-123', 'expires_in': 3600})
            if req.url.path == '/api/accounts':
                return httpx.Response(200, json={'data': [self.account]})
            return httpx.Response(200, json={'status': {'code': 200}, 'data': {'messageId': '789'}})
        self.client = c.MailClient(dict(CREDS), httpx.MockTransport(handler))
    def tearDown(self):
        pass
        self.patcher.stop()
        self.temp.cleanup()
    def test_read_paths_and_auth(self):
        self.client.accounts()
        self.client.folders('123')
        self.client.list_messages('123', '456')
        self.client.search('123', 'from:someone@example.com')
        self.client.read('123', '456', '789')
        self.assertEqual([x.url.path for x in self.calls], ['/oauth/v2/token', '/api/accounts', '/api/accounts/123/folders', '/api/accounts/123/messages/view', '/api/accounts/123/messages/search', '/api/accounts/123/folders/456/messages/789/content'])
        self.assertEqual(self.calls[0].method, 'POST')
        self.assertEqual(self.calls[0].url.query, b'')
        self.assertEqual(parse_qs(self.calls[0].content.decode())['refresh_token'], [CREDS['refresh_token']])
        self.assertTrue(self.calls[0].headers['content-type'].startswith('application/x-www-form-urlencoded'))
        for req in self.calls[1:]:
            self.assertEqual(req.method, 'GET')
            self.assertEqual(req.url.host, 'mail.zoho.com')
            self.assertEqual(req.headers['authorization'], 'Zoho-oauthtoken mock-access-123')
        self.assertEqual(self.calls[4].url.params['searchKey'], 'from:someone@example.com')
    def test_distinct_writes(self):
        for kind in ('draft', 'send', 'reply'):
            self.client.compose(kind, '123', 'friend@example.com', 'Subject', 'Body', message_id='789', approved=True)
        writes = [r for r in self.calls if r.method == 'POST' and r.url.host == 'mail.zoho.com']
        self.assertEqual(len(writes), 3)
        payloads = [json.loads(r.content) for r in writes]
        self.assertEqual(payloads[0]['mode'], 'draft')
        self.assertNotIn('mode', payloads[1])
        self.assertNotIn('action', payloads[1])
        self.assertEqual(payloads[2]['action'], 'reply')
        self.assertEqual(writes[2].url.path, '/api/accounts/123/messages/789')
        self.assertTrue(all(p['fromAddress'] == c.MAILBOX and p['mailFormat'] == 'plaintext' for p in payloads))
    def test_approval_required_before_network(self):
        for kind in ('draft', 'send', 'reply'):
            with self.assertRaises(c.SafeError):
                self.client.compose(kind, '123', 'friend@example.com', 's', 'b')
        self.assertEqual(self.calls, [])
    def test_input_and_account_validation(self):
        for bad in ('../accounts', '123?token=x', 'http://evil', '', '123/456'):
            with self.assertRaises(c.SafeError):
                self.client.read('123', bad, '789')
        with self.assertRaises(c.SafeError):
            self.client.search('123', 'all', limit=1000)
        with self.assertRaises(c.SafeError):
            self.client.compose('send', '123', 'a@example.com\r\nBcc:bad@example.com', 's', 'b', approved=True)
        with self.assertRaises(c.SafeError):
            self.client.folders('999')
        self.assertFalse(any('/999/' in r.url.path for r in self.calls))
    def test_wrong_owner(self):
        self.account['primaryEmailAddress'] = 'other@example.com'
        with self.assertRaises(c.SafeError):
            self.client.compose('send', '123', 'friend@example.com', 's', 'b', approved=True)
        self.assertFalse(any(r.method == 'POST' and r.url.host == 'mail.zoho.com' for r in self.calls))
    def test_token_cache_and_refresh(self):
        self.client.accounts()
        self.client.folders('123')
        self.assertEqual(sum(r.url.host == 'accounts.zoho.com' for r in self.calls), 1)
        self.client.expiry = 0
        self.client.cache_path().unlink()
        self.client.folders('123')
        self.assertEqual(sum(r.url.host == 'accounts.zoho.com' for r in self.calls), 2)
        self.assertEqual((self.base / 'private/oauth.lock').stat().st_mode & 0o777, 0o600)
    def test_redaction_and_bounds(self):
        self.client.token()
        output = self.client.output({'x': 'mock-secret-456 and mock-access-123', 'refresh_token': 'unknown-secret'})
        self.assertNotIn('mock-secret-456', output)
        self.assertNotIn('mock-access-123', output)
        self.assertNotIn('unknown-secret', output)
        self.assertTrue(json.loads(self.client.output({'x': 'a' * 200000}))['truncated'])
    def test_no_error_leak_or_write_retry(self):
        def failure(req):
            raise httpx.ReadTimeout('mock-secret-456 https://bad?secret=secret')
        self.client.account_id = '123'
        self.client.access = 'mock-access-123'
        self.client.expiry = float('inf')
        self.client.transport = httpx.MockTransport(failure)
        with self.assertRaises(c.SafeError) as error:
            self.client.compose('send', '123', 'friend@example.com', 's', 'b', approved=True)
        self.assertNotIn('mock-secret', str(error.exception))
        self.assertNotIn('secret=', str(error.exception))
    def test_secure_files(self):
        path = self.base / 'private/config.json'
        c.secure_write(path, CREDS)
        self.assertEqual(json.loads(c.protected_read(path)), CREDS)
        self.assertEqual(path.stat().st_mode & 0o777, 0o600)
        path.chmod(0o644)
        with self.assertRaises(c.SafeError):
            c.protected_read(path)
        link = self.base / 'link'
        link.symlink_to(path)
        with self.assertRaises(c.SafeError):
            c.protected_read(link)
    def test_bootstrap_form_and_no_secret_stdout(self):
        inp = self.base / 'private/client.json'
        code = self.base / 'private/code.txt'
        target = self.base / 'private/credentials.json'
        c.secure_write(inp, {k: CREDS[k] for k in ('client_id', 'client_secret')})
        code.write_text('mock-grant-code')
        code.chmod(0o600)
        calls = []
        def handler(req):
            calls.append(req)
            return httpx.Response(200, json={'refresh_token': CREDS['refresh_token'], 'access_token': 'secret-access'})
        mockclient = c.MailClient(transport=httpx.MockTransport(handler))
        out = io.StringIO()
        with patch.object(c, 'CONFIG', target), patch.object(c, 'MailClient', return_value=mockclient), contextlib.redirect_stdout(out):
            self.assertEqual(c.bootstrap(str(inp), str(code)), 0)
        self.assertEqual(calls[0].url.query, b'')
        payload = parse_qs(calls[0].content.decode())
        self.assertEqual(payload['grant_type'], ['authorization_code'])
        self.assertEqual(payload['code'], ['mock-grant-code'])
        self.assertNotIn('secret', out.getvalue())
        self.assertNotIn('secret-access', target.read_text())
        self.assertEqual(json.loads(c.protected_read(target)), CREDS)
    def test_cross_process_refresh_lock(self):
        marker = self.base / 'entered'
        script = "import connector as c; from pathlib import Path; c.BASE=Path(%r);\nwith c.exchange_lock(): Path(%r).touch()" % (str(self.base), str(marker))
        with c.exchange_lock():
            worker = subprocess.Popen([os.sys.executable, '-c', script], cwd=str(Path(c.__file__).resolve().parent))
            try:
                worker.wait(timeout=.3)
                self.fail('Second process bypassed refresh lock')
            except subprocess.TimeoutExpired:
                self.assertFalse(marker.exists())
        self.assertEqual(worker.wait(timeout=5), 0)
        self.assertTrue(marker.exists())
    def test_revoked_cached_token_recovers(self):
        # Zoho can invalidate a cached access token before its expiry (e.g. when other
        # processes mint newer tokens). A 401 must not poison the cache until expiry.
        tokens = iter(['stale-access', 'fresh-access'])
        def handler(req):
            self.calls.append(req)
            if str(req.url) == c.TOKEN:
                return httpx.Response(200, json={'access_token': next(tokens), 'expires_in': 3600})
            if req.headers.get('authorization') == 'Zoho-oauthtoken stale-access':
                return httpx.Response(401, json={'data': {'errorCode': 'INVALID_OAUTHTOKEN'}, 'status': {'code': 401}})
            if req.url.path == '/api/accounts':
                return httpx.Response(200, json={'data': [self.account]})
            return httpx.Response(200, json={'status': {'code': 200}, 'data': []})
        self.client.transport = httpx.MockTransport(handler)
        self.client.token()
        self.assertEqual(self.client.accounts()['data'][0]['accountId'], '123')
        self.client.folders('123')
        self.assertEqual(sum(r.url.host == 'accounts.zoho.com' for r in self.calls), 2)
    def test_write_401_clears_token_without_retry(self):
        tokens = iter(['stale-access', 'fresh-access'])
        def handler(req):
            self.calls.append(req)
            if str(req.url) == c.TOKEN:
                return httpx.Response(200, json={'access_token': next(tokens), 'expires_in': 3600})
            if req.headers.get('authorization') == 'Zoho-oauthtoken stale-access':
                return httpx.Response(401, json={'status': {'code': 401}})
            return httpx.Response(200, json={'status': {'code': 200}, 'data': {'messageId': '1'}})
        self.client.transport = httpx.MockTransport(handler)
        self.client.account_id = '123'
        with self.assertRaises(c.SafeError):
            self.client.compose('send', '123', 'friend@example.com', 's', 'b', approved=True)
        writes = [r for r in self.calls if r.method == 'POST' and r.url.host == 'mail.zoho.com']
        self.assertEqual(len(writes), 1)
        self.assertIsNone(self.client.access)
        self.client.folders('123')
        self.assertEqual(self.calls[-1].headers['authorization'], 'Zoho-oauthtoken fresh-access')
    def test_shared_token_cache_across_clients(self):
        self.client.token()
        self.assertEqual(self.client.cache_path().stat().st_mode & 0o777, 0o600)
        other = c.MailClient(dict(CREDS), httpx.MockTransport(lambda r: self.fail('second process must reuse the cached token')))
        try:
            self.assertEqual(other.token(), 'mock-access-123')
        finally:
            pass
        self.assertEqual(sum(r.url.host == 'accounts.zoho.com' for r in self.calls), 1)
    def test_expired_or_tampered_cache_is_ignored(self):
        self.client.token()
        path = self.client.cache_path()
        c.secure_write(path, {'access_token': 'old', 'expires_at': time.time() + 10})
        self.client.access = None
        self.assertEqual(self.client.token(), 'mock-access-123')
        path.write_text('not json')
        path.chmod(0o644)
        self.client.access = None
        self.assertEqual(self.client.token(), 'mock-access-123')
        self.assertEqual(path.stat().st_mode & 0o777, 0o600)
    def test_401_keeps_token_another_process_already_replaced(self):
        self.client.token()
        c.secure_write(self.client.cache_path(), {'access_token': 'newer-from-other-process', 'expires_at': time.time() + 3000})
        self.client.invalidate('mock-access-123')
        self.assertEqual(self.client.cached_access()[0], 'newer-from-other-process')
    def test_refresh_failure_cooldown_and_credential_reload(self):
        attempts = []
        def handler(req):
            attempts.append(req)
            return httpx.Response(200, json={'error': 'Access Denied', 'error_description': 'You have made too many requests continuously.'})
        self.client.transport = httpx.MockTransport(handler)
        with self.assertRaises(c.RateLimited):
            self.client.token()
        with self.assertRaises(c.SafeError) as error:
            self.client.token()
        self.assertIn('waiting', str(error.exception))
        self.assertEqual(len(attempts), 1)
    def test_http_errors_are_classified_without_leaks(self):
        def handler(req):
            if str(req.url) == c.TOKEN:
                return httpx.Response(200, json={'access_token': 'mock-access-123', 'expires_in': 3600})
            if req.url.path == '/api/accounts':
                return httpx.Response(200, json={'data': [self.account]})
            if req.url.path.endswith('/folders'):
                return httpx.Response(429, json={})
            return httpx.Response(500, json={'data': {'errorCode': 'SERVER_FAIL'}})
        self.client.transport = httpx.MockTransport(handler)
        self.client.token()
        with self.assertRaises(c.RateLimited):
            self.client.folders('123')
        with self.assertRaises(c.SafeError) as error:
            self.client.compose('send', '123', 'friend@example.com', 's', 'b', approved=True)
        self.assertIn('HTTP 500, SERVER_FAIL', str(error.exception))
        self.assertIn('Verify Drafts/Sent', str(error.exception))
    def test_malformed_account_fields_do_not_crash(self):
        self.account['emailAddress'] = None
        self.account['mailboxAddress'] = None
        self.assertEqual(self.client.accounts()['data'][0]['accountId'], '123')
    def test_tools_do_not_block_event_loop(self):
        async def run():
            ticks = []
            async def ticker():
                while True:
                    ticks.append(time.monotonic())
                    await asyncio.sleep(.02)
            def slow(*a):
                time.sleep(.5)
                return {'ok': True}
            task = asyncio.create_task(ticker())
            with patch.object(c.client, 'folders', slow):
                out = await c.get_folders('123')
            task.cancel()
            return out, ticks
        out, ticks = asyncio.run(run())
        self.assertEqual(json.loads(out), {'ok': True})
        self.assertGreater(len(ticks), 10)
        self.assertLess(max(b - a for a, b in zip(ticks, ticks[1:])), .2)
    def test_host_and_methods_blocked(self):
        for method, url in [('DELETE', c.MAIL + '/api/accounts/123'), ('GET', 'https://evil.example/api/accounts'), ('POST', c.MAIL + '/api/organization/123')]:
            with self.assertRaises(c.SafeError):
                self.client.request(method, url)
        self.assertEqual(self.calls, [])

class Protocol(unittest.TestCase):
    def test_real_stdio_initialize_and_list(self):
        from mcp import ClientSession, StdioServerParameters
        from mcp.client.stdio import stdio_client
        async def run():
            args = StdioServerParameters(command=sys.executable, args=[str(Path(c.__file__).resolve())], env={'ZOHO_MAIL_DATA_DIR': tempfile.mkdtemp(prefix='zoho-protocol-')})
            async with stdio_client(args) as (read, write):
                async with ClientSession(read, write) as session:
                    initialized = await session.initialize()
                    self.assertEqual(initialized.serverInfo.name, 'Zoho Mail')
                    tools = (await session.list_tools()).tools
                    names = {x.name for x in tools}
                    self.assertEqual(names, {'get_recent_errors', 'check_new_mail', 'get_accounts', 'get_folders', 'list_messages', 'search_messages', 'read_message', 'save_draft', 'send_message', 'reply_message'})
                    self.assertFalse(any('delete' in x or 'admin' in x or 'forward' in x for x in names))
                    for tool in tools:
                        if tool.name in {'send_message', 'reply_message', 'save_draft'}:
                            self.assertFalse(tool.annotations.readOnlyHint)
                            self.assertFalse(tool.annotations.idempotentHint)
                    refused = await session.call_tool('send_message', {'account_id': '123', 'to_address': 'friend@example.com', 'subject': 's', 'content': 'b'})
                    self.assertIn('approval', refused.content[0].text)
        asyncio.run(run())

if __name__ == '__main__':
    unittest.main(verbosity=2)
