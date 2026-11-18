import unittest

from flask import session
from werkzeug.exceptions import BadRequest

import app


class CsrfProtectionTests(unittest.TestCase):
    def test_form_token_is_accepted(self):
        token = 'session-token'
        with app.app.test_request_context(
            '/account/update', method='POST', data={'csrf_token': token}
        ):
            session['_csrf_token'] = token
            self.assertIsNone(app.protect_csrf())

    def test_header_token_is_accepted(self):
        token = 'session-token'
        with app.app.test_request_context(
            '/account/update', method='POST', headers={'X-CSRF-Token': token}
        ):
            session['_csrf_token'] = token
            self.assertIsNone(app.protect_csrf())

    def test_missing_or_mismatched_token_is_rejected(self):
        with app.app.test_request_context('/account/update', method='POST'):
            session['_csrf_token'] = 'expected'
            with self.assertRaises(BadRequest):
                app.protect_csrf()

        with app.app.test_request_context(
            '/account/update', method='POST', data={'csrf_token': 'wrong'}
        ):
            session['_csrf_token'] = 'expected'
            with self.assertRaises(BadRequest):
                app.protect_csrf()

    def test_flutterwave_webhook_is_exempt_from_form_tokens(self):
        with app.app.test_request_context('/webhooks/flutterwave', method='POST'):
            self.assertIsNone(app.protect_csrf())


if __name__ == '__main__':
    unittest.main()
