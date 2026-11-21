import io
import tempfile
import time
import unittest
from unittest.mock import patch

from werkzeug.security import generate_password_hash

import app
from supabase_storage import SupabaseUploadStorage
from upload_storage import LocalUploadStorage


VALID_PNG = (
    b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01'
    b'\x08\x02\x00\x00\x00\x90wS\xde\x00\x00\x00\x0cIDATx\x9cc\xf8\xcf\xc0'
    b'\x00\x00\x03\x01\x01\x00\x18\xdd\x8d\xb0\x00\x00\x00\x00IEND\xaeB`\x82'
)
VALID_JPEG = b'\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x00\x00\x01\x00\x01\x00\x00\xff\xd9'
VALID_GIF = b'GIF89a\x01\x00\x01\x00\x80\x00\x00\x00\x00\x00\xff\xff\xff!\xf9\x04\x01\x00\x00\x00\x00,\x00\x00\x00\x00\x01\x00\x01\x00\x00\x02\x02D\x01\x00;'
VALID_WEBP = b'RIFF\x14\x00\x00\x00WEBPVP8 \x08\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00'


class KwachaStaySecurityTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.orig_db = app.DATABASE
        self.orig_db_url = app.DATABASE_URL
        self.orig_env = app.APP_ENV
        self.orig_storage = app.upload_storage
        self.orig_backend = app.STORAGE_BACKEND
        self.orig_uploads = app.app.config['UPLOADS_ENABLED']
        self.orig_rl = app.RATELIMIT_ENABLED
        self.orig_idle = app.SESSION_IDLE_TIMEOUT_SECONDS
        self.orig_admin_idle = app.ADMIN_SESSION_IDLE_TIMEOUT_SECONDS

        app.DATABASE_URL = ''
        app.DATABASE = self.temp_dir.name + '/security-test.db'
        app.APP_ENV = 'development'
        app.upload_storage = LocalUploadStorage(self.temp_dir.name)
        app.STORAGE_BACKEND = 'local'
        app.app.config['UPLOADS_ENABLED'] = True
        app.RATELIMIT_ENABLED = True
        app.init_db()
        app.app.config['TESTING'] = True

    def tearDown(self):
        app.DATABASE = self.orig_db
        app.DATABASE_URL = self.orig_db_url
        app.APP_ENV = self.orig_env
        app.upload_storage = self.orig_storage
        app.STORAGE_BACKEND = self.orig_backend
        app.app.config['UPLOADS_ENABLED'] = self.orig_uploads
        app.RATELIMIT_ENABLED = self.orig_rl
        app.SESSION_IDLE_TIMEOUT_SECONDS = self.orig_idle
        app.ADMIN_SESSION_IDLE_TIMEOUT_SECONDS = self.orig_admin_idle
        self.temp_dir.cleanup()

    def create_user(self, name, email, phone, password='StrongPass1', role='tenant', is_admin=0):
        with app.app.app_context():
            db = app.get_db()
            cursor = db.execute(
                '''INSERT INTO users (full_name, email, phone, password, role, is_admin)
                   VALUES (?, ?, ?, ?, ?, ?)''',
                (name, email, phone, generate_password_hash(password), role, is_admin),
            )
            db.commit()
            return cursor.lastrowid

    def create_property(self, owner_id, title='Kabulonga House', is_active=1):
        with app.app.app_context():
            db = app.get_db()
            cursor = db.execute(
                '''INSERT INTO properties
                   (owner_id, title, description, price_per_night, compound, property_type, is_active, image_main)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)''',
                (owner_id, title, 'Clean home in Lusaka', 1000, 'Kabulonga', 'House', is_active, '/static/uploads/a.png'),
            )
            db.commit()
            return cursor.lastrowid

    def login_session(self, client, user_id, csrf='sec-csrf'):
        with client.session_transaction() as sess:
            sess['user_id'] = user_id
            sess['_csrf_token'] = csrf
            sess['_session_last_active'] = time.time()
        return csrf

    # --- 1. Authentication, Password Policy, & Rate Limiting ---

    def test_password_strength_enforced_on_signup_and_change_password(self):
        client = app.app.test_client()
        with client.session_transaction() as sess:
            sess['_csrf_token'] = 'c1'

        # Weak password (too short) rejected at signup
        resp = client.post('/signup', data={
            'full_name': 'Weak User',
            'email': 'weak@example.com',
            'country_code': '+260',
            'phone': '971111111',
            'password': 'abc12',
            'role': 'tenant',
            'csrf_token': 'c1',
        })
        self.assertEqual(resp.status_code, 200)
        with app.app.app_context():
            self.assertIsNone(app.get_db().execute("SELECT id FROM users WHERE email = 'weak@example.com'").fetchone())

        # Weak 6-char password rejected on change_password (previously allowed 6 chars)
        uid = self.create_user('Chanda', 'chanda@example.com', '+260971111112', password='OldPassword1')
        csrf = self.login_session(client, uid)
        resp = client.post('/profile/change_password', data={
            'current_password': 'OldPassword1',
            'new_password': 'abc123',
            'confirm_password': 'abc123',
            'csrf_token': csrf,
        }, follow_redirects=True)
        self.assertIn(b'at least 8 characters', resp.data)

    def test_login_rate_limiting_blocks_brute_force_and_resets_on_success(self):
        self.create_user('Target', 'target@example.com', '+260971222222', password='CorrectPass1')
        client = app.app.test_client()
        with client.session_transaction() as sess:
            sess['_csrf_token'] = 'bf-csrf'

        # 5 failed attempts allowed before identifier lockout triggers on 6th
        for _ in range(5):
            r = client.post('/login', data={
                'email': 'target@example.com',
                'password': 'WrongPassword9',
                'csrf_token': 'bf-csrf',
            })
            self.assertEqual(r.status_code, 200)

        locked = client.post('/login', data={
            'email': 'target@example.com',
            'password': 'CorrectPass1',
            'csrf_token': 'bf-csrf',
        })
        self.assertEqual(locked.status_code, 429)

    def test_banned_user_existing_session_is_revoked_immediately(self):
        uid = self.create_user('Bad Actor', 'bad@example.com', '+260971333333', role='tenant')
        client = app.app.test_client()
        self.login_session(client, uid)
        self.assertEqual(client.get('/tenant/dashboard').status_code, 200)

        # Ban user in DB while session is active
        with app.app.app_context():
            db = app.get_db()
            db.execute("UPDATE users SET role = 'banned' WHERE id = ?", (uid,))
            db.commit()

        resp = client.get('/tenant/dashboard', follow_redirects=False)
        self.assertEqual(resp.status_code, 302)
        self.assertTrue(resp.headers['Location'].endswith('/login'))

    def test_session_idle_timeout_expires_stale_session(self):
        uid = self.create_user('Idle User', 'idle@example.com', '+260971444444', role='tenant')
        client = app.app.test_client()
        with client.session_transaction() as sess:
            sess['user_id'] = uid
            sess['_csrf_token'] = 'idle-csrf'
            sess['_session_last_active'] = time.time() - (app.SESSION_IDLE_TIMEOUT_SECONDS + 10)

        resp = client.get('/tenant/dashboard', follow_redirects=False)
        self.assertEqual(resp.status_code, 302)
        self.assertTrue(resp.headers['Location'].endswith('/login'))

    # --- 2. Role-Based Access Control & Horizontal Authorization ---

    def test_landlord_cannot_edit_or_delete_other_landlord_property_or_self_feature(self):
        owner1 = self.create_user('Owner 1', 'o1@example.com', '+260971500001', role='owner')
        owner2 = self.create_user('Owner 2', 'o2@example.com', '+260971500002', role='owner')
        prop1 = self.create_property(owner1, 'Owner 1 Villa')

        client = app.app.test_client()
        csrf = self.login_session(client, owner2)

        # Owner 2 cannot edit Owner 1's property
        edit_resp = client.post(f'/property/{prop1}/edit', data={
            'title': 'Hacked Title',
            'description': 'Hacked',
            'price': '1',
            'price_period': 'night',
            'compound': 'Kabulonga',
            'property_type': 'House',
            'csrf_token': csrf,
        })
        self.assertEqual(edit_resp.status_code, 302)
        with app.app.app_context():
            title = app.get_db().execute('SELECT title FROM properties WHERE id = ?', (prop1,)).fetchone()[0]
            self.assertEqual(title, 'Owner 1 Villa')

        # Owner 2 cannot delete Owner 1's property
        client.post(f'/property/{prop1}/delete', data={'csrf_token': csrf})
        with app.app.app_context():
            self.assertIsNotNone(app.get_db().execute('SELECT id FROM properties WHERE id = ?', (prop1,)).fetchone())

        # Non-admin owner cannot self-feature a new listing
        client.post('/add_house', data={
            'title': 'Self Featured Attempt',
            'description': 'Testing featured flag protection on server side.',
            'price': '900',
            'price_period': 'night',
            'compound': 'Kabulonga',
            'property_type': 'House',
            'image_url': '/static/uploads/test.png',
            'is_featured': 'on',
            'csrf_token': csrf,
        })
        with app.app.app_context():
            row = app.get_db().execute("SELECT is_featured FROM properties WHERE title = 'Self Featured Attempt'").fetchone()
            self.assertIsNotNone(row)
            self.assertEqual(row['is_featured'], 0)

    def test_tenant_cannot_access_other_tenant_booking_or_reply_to_other_messages(self):
        owner = self.create_user('Host', 'hostm@example.com', '+260971600001', role='owner')
        tenant1 = self.create_user('Tenant 1', 't1@example.com', '+260971600002', role='tenant')
        tenant2 = self.create_user('Tenant 2', 't2@example.com', '+260971600003', role='tenant')
        prop_id = self.create_property(owner)

        with app.app.app_context():
            db = app.get_db()
            booking_id = db.execute(
                '''INSERT INTO bookings
                   (property_id, user_id, tenant_name, tenant_phone, check_in, check_out, total_price, booking_status)
                   VALUES (?, ?, 'Tenant 1', '+260971600002', '2027-05-01', '2027-05-03', 2050, 'pending')''',
                (prop_id, tenant1),
            ).lastrowid
            msg_id = db.execute(
                '''INSERT INTO messages (sender_id, receiver_id, property_id, content)
                   VALUES (?, ?, ?, 'Private inquiry from tenant 1')''',
                (tenant1, owner, prop_id),
            ).lastrowid
            db.commit()

        client = app.app.test_client()
        csrf = self.login_session(client, tenant2)

        # Tenant 2 cannot view Tenant 1's booking receipt
        receipt_resp = client.get(f'/booking/{booking_id}/receipt', follow_redirects=False)
        self.assertEqual(receipt_resp.status_code, 302)

        # Tenant 2 cannot cancel Tenant 1's booking
        client.post(f'/booking/cancel/{booking_id}', data={'csrf_token': csrf})
        with app.app.app_context():
            status = app.get_db().execute('SELECT booking_status FROM bookings WHERE id = ?', (booking_id,)).fetchone()[0]
            self.assertEqual(status, 'pending')

        # Tenant 2 cannot reply to Tenant 1 <-> Host message thread (IDOR fix)
        reply_resp = client.post(f'/message/reply/{msg_id}', data={
            'content': 'Injected reply',
            'csrf_token': csrf,
        })
        self.assertEqual(reply_resp.status_code, 403)
        with app.app.app_context():
            is_read = app.get_db().execute('SELECT is_read FROM messages WHERE id = ?', (msg_id,)).fetchone()[0]
            self.assertEqual(is_read, 0)

    def test_inactive_property_hidden_from_public_and_tenants(self):
        owner = self.create_user('Host', 'hosti@example.com', '+260971700001', role='owner')
        prop_id = self.create_property(owner, title='Delisted Secret', is_active=0)
        client = app.app.test_client()

        resp = client.get(f'/property/{prop_id}', follow_redirects=False)
        self.assertEqual(resp.status_code, 302)

        # Owner can still view their own delisted property
        self.login_session(client, owner)
        self.assertEqual(client.get(f'/property/{prop_id}').status_code, 200)

    def test_unauthorized_users_cannot_access_admin_endpoints(self):
        tenant = self.create_user('Tenant', 'ta@example.com', '+260971800001', role='tenant')
        owner = self.create_user('Owner', 'oa@example.com', '+260971800002', role='owner')
        prop_id = self.create_property(owner)

        client = app.app.test_client()
        csrf = self.login_session(client, tenant)

        for path in (
            '/admin',
            f'/admin/verify_property/{prop_id}',
            f'/admin/ban_user/{owner}',
            f'/admin/toggle_admin/{tenant}',
            f'/admin/force_delist/{prop_id}',
        ):
            r = client.get(path, follow_redirects=False) if path == '/admin' else client.post(path, data={'csrf_token': csrf}, follow_redirects=False)
            self.assertEqual(r.status_code, 302, f'Expected redirect blocking non-admin on {path}')

        with app.app.app_context():
            self.assertEqual(app.get_db().execute('SELECT is_verified FROM properties WHERE id = ?', (prop_id,)).fetchone()[0], 0)
            self.assertEqual(app.get_db().execute('SELECT is_admin FROM users WHERE id = ?', (tenant,)).fetchone()[0], 0)

    # --- 3. SQL Injection & Input Validation ---

    def test_sql_injection_and_malformed_query_params_handled_safely(self):
        owner = self.create_user('Owner', 'sqlo@example.com', '+260971900001', role='owner')
        self.create_property(owner, title='Safe Property')
        client = app.app.test_client()

        # SQLi payloads in search, numeric filters, and pagination should never 500 or drop tables
        resp = client.get(
            "/?q=' OR 1=1--&min_price=1;DROP TABLE users;--&max_price=abc&min_bedrooms=xyz&page=notanumber"
        )
        self.assertEqual(resp.status_code, 200)

        # SQLi in login form must fail cleanly
        with client.session_transaction() as sess:
            sess['_csrf_token'] = 'sqli-csrf'
        login_resp = client.post('/login', data={
            'email': "' OR '1'='1' --",
            'password': "' OR '1'='1",
            'csrf_token': 'sqli-csrf',
        })
        self.assertEqual(login_resp.status_code, 200)
        with app.app.app_context():
            self.assertEqual(app.get_db().execute('SELECT COUNT(*) FROM users').fetchone()[0], 1)

    def test_xss_image_urls_and_open_redirects_rejected(self):
        owner = self.create_user('Host', 'xsso@example.com', '+260972000001', role='owner')
        tenant = self.create_user('Guest', 'xsst@example.com', '+260972000002', role='tenant')
        client = app.app.test_client()
        csrf = self.login_session(client, owner)

        # javascript: URL rejected in add_house
        client.post('/add_house', data={
            'title': 'Bad Image Listing',
            'description': 'Attempt to store javascript URL',
            'price': '500',
            'price_period': 'night',
            'compound': 'Kabulonga',
            'property_type': 'House',
            'image_url': 'javascript:alert(1)',
            'csrf_token': csrf,
        })
        with app.app.app_context():
            self.assertIsNone(app.get_db().execute("SELECT id FROM properties WHERE title = 'Bad Image Listing'").fetchone())

        # javascript: URL rejected in profile_pic
        client.post('/profile/edit', data={
            'full_name': 'Host',
            'phone': '+260972000001',
            'profile_pic': 'javascript:alert(document.cookie)',
            'csrf_token': csrf,
        })
        with app.app.app_context():
            pic = app.get_db().execute('SELECT profile_pic FROM users WHERE id = ?', (owner,)).fetchone()[0]
            self.assertIsNone(pic)

        # External Referer on send_message must NOT open-redirect
        msg_resp = client.post(
            '/send_message',
            data={'receiver_id': str(tenant), 'content': 'Hello!', 'csrf_token': csrf},
            headers={'Referer': 'https://evil.example/phish'},
            follow_redirects=False,
        )
        self.assertEqual(msg_resp.status_code, 302)
        self.assertNotIn('evil.example', msg_resp.headers['Location'])

    # --- 4. File Upload Security ---

    def test_file_upload_restrictions_magic_bytes_role_and_canonical_mime(self):
        tenant = self.create_user('Tenant', 'upt@example.com', '+260972100001', role='tenant')
        owner = self.create_user('Owner', 'upo@example.com', '+260972100002', role='owner')
        client = app.app.test_client()

        # Tenant cannot upload to /upload_image
        csrf = self.login_session(client, tenant)
        r_tenant = client.post(
            '/upload_image',
            data={'image': (io.BytesIO(VALID_PNG), 'a.png')},
            headers={'X-CSRF-Token': csrf},
            content_type='multipart/form-data',
        )
        self.assertEqual(r_tenant.status_code, 403)

        # Switch to landlord
        csrf = self.login_session(client, owner)

        # Reject PHP script renamed to .jpg
        r_fake = client.post(
            '/upload_image',
            data={'image': (io.BytesIO(b'<?php system($_GET["c"]); ?>'), 'shell.jpg')},
            headers={'X-CSRF-Token': csrf},
            content_type='multipart/form-data',
        )
        self.assertEqual(r_fake.status_code, 400)

        # Reject HTML/XSS file renamed to .png
        r_html = client.post(
            '/upload_image',
            data={'image': (io.BytesIO(b'<html><script>alert(1)</script></html>'), 'xss.png')},
            headers={'X-CSRF-Token': csrf},
            content_type='multipart/form-data',
        )
        self.assertEqual(r_html.status_code, 400)

        # Genuine PNG bytes saved with .jpg extension are accepted and normalized to canonical .png
        r_normalized = client.post(
            '/upload_image',
            data={'image': (io.BytesIO(VALID_PNG), 'saved-as.jpg')},
            headers={'X-CSRF-Token': csrf},
            content_type='multipart/form-data',
        )
        self.assertEqual(r_normalized.status_code, 200)
        self.assertTrue(r_normalized.get_json()['url'].endswith('.png'))

        # Reject disallowed executable extension
        r_exe = client.post(
            '/upload_image',
            data={'image': (io.BytesIO(b'MZ\x90\x00'), 'malware.exe')},
            headers={'X-CSRF-Token': csrf},
            content_type='multipart/form-data',
        )
        self.assertEqual(r_exe.status_code, 400)

        # Reject oversized image (> 5 MB)
        oversized = VALID_PNG + (b'\x00' * (app.MAX_IMAGE_UPLOAD_BYTES + 10))
        r_big = client.post(
            '/upload_image',
            data={'image': (io.BytesIO(oversized), 'huge.png')},
            headers={'X-CSRF-Token': csrf},
            content_type='multipart/form-data',
        )
        self.assertEqual(r_big.status_code, 400)

        # Accept valid PNG, JPEG, GIF, WebP and ensure unique non-colliding filenames
        urls = set()
        for payload, fname in ((VALID_PNG, 'a.png'), (VALID_PNG, 'a.png'), (VALID_JPEG, 'b.jpg'), (VALID_GIF, 'c.gif'), (VALID_WEBP, 'd.webp')):
            r_ok = client.post(
                '/upload_image',
                data={'image': (io.BytesIO(payload), fname)},
                headers={'X-CSRF-Token': csrf},
                content_type='multipart/form-data',
            )
            self.assertEqual(r_ok.status_code, 200, f'Expected valid upload for {fname}: {r_ok.data}')
            urls.add(r_ok.get_json()['url'])
        self.assertEqual(len(urls), 5)

        # SupabaseUploadStorage uses canonical MIME type, ignoring forged text/html mimetype
        storage = SupabaseUploadStorage(url='https://proj.supabase.co', service_role_key='svc', bucket='property-images')
        with patch.object(storage, '_request', return_value=b'') as req_mock:
            fake_file = io.BytesIO(VALID_PNG)
            fake_file.mimetype = 'text/html'
            storage.save(fake_file, 'test.png', content_type='image/png')
            self.assertEqual(req_mock.call_args.kwargs['content_type'], 'image/png')

    # --- 5. CSRF, Security Headers, Admin Audit Log & Safe Errors ---

    def test_security_headers_and_admin_noindex_and_cache_control(self):
        admin_id = self.create_user('Admin', 'admh@example.com', '+260972200001', role='owner', is_admin=1)
        client = app.app.test_client()

        resp = client.get('/')
        self.assertEqual(resp.headers.get('X-Content-Type-Options'), 'nosniff')
        self.assertEqual(resp.headers.get('X-Frame-Options'), 'SAMEORIGIN')
        self.assertEqual(resp.headers.get('Referrer-Policy'), 'strict-origin-when-cross-origin')
        self.assertIn("object-src 'none'", resp.headers.get('Content-Security-Policy', ''))
        self.assertIn('Permissions-Policy', resp.headers)

        self.login_session(client, admin_id)
        admin_resp = client.get('/admin')
        self.assertEqual(admin_resp.status_code, 200)
        self.assertEqual(admin_resp.headers.get('X-Robots-Tag'), 'noindex, nofollow')
        self.assertIn('no-store', admin_resp.headers.get('Cache-Control', ''))

    def test_admin_audit_logging_and_no_password_hash_exposure(self):
        admin_id = self.create_user('Admin', 'admlog@example.com', '+260972300001', role='owner', is_admin=1)
        host_id = self.create_user('Host', 'hostlog@example.com', '+260972300002', role='owner', is_admin=0)
        prop_id = self.create_property(host_id, 'Audited House')

        client = app.app.test_client()
        csrf = self.login_session(client, admin_id)

        client.post(f'/admin/verify_property/{prop_id}', data={'csrf_token': csrf})
        client.post(f'/admin/ban_user/{host_id}', data={'csrf_token': csrf})

        with app.app.app_context():
            logs = app.get_db().execute('SELECT action, target_type, target_id FROM admin_audit_logs ORDER BY id').fetchall()
            actions = [(row['action'], row['target_type'], str(row['target_id'])) for row in logs]
            self.assertIn(('property_verified', 'property', str(prop_id)), actions)
            self.assertIn(('user_banned', 'user', str(host_id)), actions)

        admin_page = client.get('/admin')
        self.assertIn(b'property_verified', admin_page.data)
        self.assertNotIn(b'scrypt:', admin_page.data)
        self.assertNotIn(b'pbkdf2:', admin_page.data)

    def test_csrf_required_for_post_logout_and_safe_404_error_page(self):
        uid = self.create_user('Logout User', 'lo@example.com', '+260972400001', role='tenant')
        client = app.app.test_client()
        csrf = self.login_session(client, uid)

        # POST /logout without CSRF rejected (400)
        self.assertEqual(client.post('/logout').status_code, 400)
        # POST /logout with CSRF succeeds
        self.assertEqual(client.post('/logout', data={'csrf_token': csrf}).status_code, 302)

        # Safe 404 page
        not_found = client.get('/nonexistent-route-xyz')
        self.assertEqual(not_found.status_code, 404)
        self.assertIn(b'Page Not Found', not_found.data)
        self.assertNotIn(b'Traceback', not_found.data)

    # --- 6. Admin TOTP 2FA, Global Session Invalidation, & Nonce CSP ---

    def test_admin_totp_2fa_full_lifecycle_and_login_challenge(self):
        admin_id = self.create_user(
            'Sec Admin', 'admin2fa@example.com', '+260972500001',
            password='AdminPass123', role='owner', is_admin=1,
        )
        client = app.app.test_client()
        csrf = self.login_session(client, admin_id)

        # Start 2FA setup
        start_resp = client.post('/admin/security/2fa/start', data={'csrf_token': csrf}, follow_redirects=False)
        self.assertEqual(start_resp.status_code, 302)
        with client.session_transaction() as sess:
            secret = sess.get('pending_totp_setup_secret')
        self.assertTrue(secret)

        # Wrong TOTP code fails to enable
        client.post('/admin/security/2fa/confirm', data={
            'current_password': 'AdminPass123',
            'totp_code': '000000',
            'csrf_token': csrf,
        })
        with app.app.app_context():
            row = app.get_db().execute('SELECT totp_enabled FROM users WHERE id = ?', (admin_id,)).fetchone()
            self.assertEqual(row['totp_enabled'], 0)

        # Valid TOTP code enables 2FA
        valid_code = app.totp_code(secret)
        client.post('/admin/security/2fa/confirm', data={
            'current_password': 'AdminPass123',
            'totp_code': valid_code,
            'csrf_token': csrf,
        })
        with app.app.app_context():
            row = app.get_db().execute('SELECT totp_enabled, totp_secret FROM users WHERE id = ?', (admin_id,)).fetchone()
            self.assertEqual(row['totp_enabled'], 1)
            self.assertEqual(row['totp_secret'], secret)

        # Logout and login again -> must redirect to /admin/verify-2fa (not /admin yet)
        client.post('/logout', data={'csrf_token': csrf})
        with client.session_transaction() as sess:
            sess['_csrf_token'] = 'l2fa-csrf'
        login_resp = client.post('/login', data={
            'email': 'admin2fa@example.com',
            'password': 'AdminPass123',
            'csrf_token': 'l2fa-csrf',
        }, follow_redirects=False)
        self.assertEqual(login_resp.status_code, 302)
        self.assertTrue(login_resp.headers['Location'].endswith('/admin/verify-2fa'))

        # Direct access to /admin before passing 2FA must be blocked
        self.assertEqual(client.get('/admin', follow_redirects=False).status_code, 302)

        # Submitting valid TOTP completes admin login
        with client.session_transaction() as sess:
            v_csrf = sess.get('_csrf_token') or 'v2fa-csrf'
            sess['_csrf_token'] = v_csrf
        verify_resp = client.post('/admin/verify-2fa', data={
            'totp_code': app.totp_code(secret),
            'csrf_token': v_csrf,
        }, follow_redirects=False)
        self.assertEqual(verify_resp.status_code, 302)
        self.assertTrue(verify_resp.headers['Location'].endswith('/admin'))
        self.assertEqual(client.get('/admin').status_code, 200)

        # Disabling 2FA requires password + valid code
        with client.session_transaction() as sess:
            d_csrf = sess['_csrf_token']
        client.post('/admin/security/2fa/disable', data={
            'current_password': 'AdminPass123',
            'totp_code': app.totp_code(secret),
            'csrf_token': d_csrf,
        })
        with app.app.app_context():
            row = app.get_db().execute('SELECT totp_enabled, totp_secret FROM users WHERE id = ?', (admin_id,)).fetchone()
            self.assertEqual(row['totp_enabled'], 0)
            self.assertIsNone(row['totp_secret'])

    def test_password_change_invalidates_sessions_on_other_devices(self):
        uid = self.create_user(
            'Multi Device', 'multi@example.com', '+260972600001',
            password='OldPassword1', role='tenant',
        )
        client_a = app.app.test_client()
        client_b = app.app.test_client()

        # Both devices log in
        for client, tok in ((client_a, 'ca'), (client_b, 'cb')):
            with client.session_transaction() as sess:
                sess['_csrf_token'] = tok
            r = client.post('/login', data={
                'email': 'multi@example.com',
                'password': 'OldPassword1',
                'csrf_token': tok,
            }, follow_redirects=False)
            self.assertEqual(r.status_code, 302)

        self.assertEqual(client_b.get('/tenant/dashboard').status_code, 200)

        # Device A changes password -> Device A stays logged in, Device B is immediately invalidated
        with client_a.session_transaction() as sess:
            csrf_a = sess['_csrf_token']
        client_a.post('/profile/change_password', data={
            'current_password': 'OldPassword1',
            'new_password': 'NewPassword2',
            'confirm_password': 'NewPassword2',
            'csrf_token': csrf_a,
        })
        self.assertEqual(client_a.get('/tenant/dashboard').status_code, 200)
        b_resp = client_b.get('/tenant/dashboard', follow_redirects=False)
        self.assertEqual(b_resp.status_code, 302)
        self.assertTrue(b_resp.headers['Location'].endswith('/login'))

    def test_csp_nonce_is_per_request_and_present_on_script_tags(self):
        client = app.app.test_client()
        r1 = client.get('/')
        r2 = client.get('/')
        csp1 = r1.headers.get('Content-Security-Policy', '')
        csp2 = r2.headers.get('Content-Security-Policy', '')

        self.assertIn("script-src-elem 'self' 'nonce-", csp1)
        self.assertNotIn("script-src-elem 'self' 'unsafe-inline'", csp1)
        self.assertNotEqual(csp1, csp2)

        # Extract nonce from CSP and confirm it is rendered on <script nonce="..."> in HTML
        import re as _re
        nonce1 = _re.search(r"'nonce-([^']+)'", csp1).group(1)
        self.assertIn(f'nonce="{nonce1}"'.encode('utf-8'), r1.data)


if __name__ == '__main__':
    unittest.main()
