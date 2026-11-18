import base64
import hashlib
import hmac
import json
import re
import sqlite3
import tempfile
import time
import unittest
from unittest.mock import patch

from werkzeug.security import check_password_hash, generate_password_hash

import app


class EmailSystemTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.original_database = app.DATABASE
        self.original_provider = app.EMAIL_PROVIDER
        self.original_api_key = app.RESEND_API_KEY
        self.original_sender = app.RESEND_FROM_EMAIL
        self.original_webhook_secret = app.RESEND_WEBHOOK_SECRET
        self.original_base_url = app.PUBLIC_BASE_URL
        app.DATABASE = self.temp_dir.name + '/email-test.db'
        app.EMAIL_PROVIDER = 'resend'
        app.RESEND_API_KEY = 're_test'
        app.RESEND_FROM_EMAIL = 'KwachaStay <test@example.com>'
        app.RESEND_WEBHOOK_SECRET = ''
        app.PUBLIC_BASE_URL = 'https://kwachastay.example'
        app.init_db()
        app.app.config['TESTING'] = True

    def tearDown(self):
        app.DATABASE = self.original_database
        app.EMAIL_PROVIDER = self.original_provider
        app.RESEND_API_KEY = self.original_api_key
        app.RESEND_FROM_EMAIL = self.original_sender
        app.RESEND_WEBHOOK_SECRET = self.original_webhook_secret
        app.PUBLIC_BASE_URL = self.original_base_url
        self.temp_dir.cleanup()

    def add_user(self, email='guest@example.com'):
        with app.app.app_context():
            db = app.get_db()
            cursor = db.execute(
                '''INSERT INTO users (full_name, email, phone, password, email_verified_at, phone_verified_at)
                   VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)''',
                ('Test Guest', email, '+260971234567', generate_password_hash('Oldpass1')),
            )
            db.commit()
            return cursor.lastrowid

    def csrf(self, client):
        with client.session_transaction() as session:
            session['_csrf_token'] = 'test-csrf'
        return 'test-csrf'

    def test_password_reset_is_single_use_and_hashes_token(self):
        self.add_user()
        client = app.app.test_client()
        csrf = self.csrf(client)
        with patch.object(app, 'send_email', return_value='provider-id') as send:
            response = client.post('/forgot_password', data={'email': 'guest@example.com', 'csrf_token': csrf})
        self.assertEqual(response.status_code, 302)
        send.assert_called_once()
        html = send.call_args.args[2]
        token = re.search(r'/reset_password/([^"<\s]+)', html).group(1)
        with app.app.app_context():
            user = app.get_db().execute('SELECT password_reset_token, password_reset_token_hash FROM users').fetchone()
            self.assertIsNone(user['password_reset_token'])
            self.assertEqual(user['password_reset_token_hash'], app.token_digest(token))

        csrf = self.csrf(client)
        response = client.post(
            f'/reset_password/{token}',
            data={'password': 'Newpass123', 'confirm_password': 'Newpass123', 'csrf_token': csrf},
        )
        self.assertEqual(response.status_code, 302)
        with app.app.app_context():
            user = app.get_db().execute('SELECT password, password_reset_token_hash FROM users').fetchone()
            self.assertTrue(check_password_hash(user['password'], 'Newpass123'))
            self.assertIsNone(user['password_reset_token_hash'])
        self.assertEqual(client.get(f'/reset_password/{token}').status_code, 302)

    def test_forgot_password_does_not_reveal_unknown_email(self):
        client = app.app.test_client()
        csrf = self.csrf(client)
        with patch.object(app, 'send_email') as send:
            response = client.post('/forgot_password', data={'email': 'unknown@example.com', 'csrf_token': csrf})
        self.assertEqual(response.status_code, 302)
        send.assert_not_called()

    def test_expired_reset_token_is_rejected(self):
        user_id = self.add_user()
        token = 'expired-token'
        with app.app.app_context():
            db = app.get_db()
            db.execute('UPDATE users SET password_reset_token_hash = ?, password_reset_expires = ? WHERE id = ?',
                       (app.token_digest(token), time.time() - 1, user_id))
            db.commit()
        self.assertEqual(app.app.test_client().get(f'/reset_password/{token}').status_code, 302)

    def test_resend_webhook_is_signed_and_idempotent(self):
        secret = base64.b64encode(b'test-webhook-secret').decode('ascii')
        app.RESEND_WEBHOOK_SECRET = 'whsec_' + secret
        event_id = 'evt_test_1'
        event = {'type': 'email.delivered', 'data': {'email_id': 'msg_test_1', 'to': ['guest@example.com']}}
        body = json.dumps(event).encode('utf-8')
        timestamp = str(int(time.time()))
        signature = base64.b64encode(
            hmac.new(b'test-webhook-secret', f'{event_id}.{timestamp}.'.encode() + body, hashlib.sha256).digest()
        ).decode('ascii')
        with app.app.app_context():
            db = app.get_db()
            db.execute('''INSERT INTO email_messages
                          (provider, provider_message_id, recipient, subject, status)
                          VALUES ('resend', 'msg_test_1', 'guest@example.com', 'Test', 'accepted')''')
            db.commit()
        client = app.app.test_client()
        headers = {'svix-id': event_id, 'svix-timestamp': timestamp, 'svix-signature': f'v1,{signature}'}
        self.assertEqual(client.post('/webhooks/resend', data=body, headers=headers).status_code, 200)
        self.assertEqual(client.post('/webhooks/resend', data=body, headers=headers).json['status'], 'duplicate')
        with app.app.app_context():
            status = app.get_db().execute('SELECT status FROM email_messages WHERE provider_message_id = ?', ('msg_test_1',)).fetchone()[0]
            self.assertEqual(status, 'delivered')


if __name__ == '__main__':
    unittest.main()
