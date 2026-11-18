import unittest

from database import PgRow, prepare_statement, translate_sql


class TranslateSqlTests(unittest.TestCase):
    def test_insert_or_ignore_becomes_conflict_and_returning(self):
        translated, expects_id = prepare_statement(
            'INSERT OR IGNORE INTO users (email) VALUES (?)'
        )
        self.assertEqual(
            translated,
            'INSERT INTO users (email) VALUES (%s) ON CONFLICT DO NOTHING RETURNING id',
        )
        self.assertTrue(expects_id)

    def test_date_now_and_placeholders(self):
        translated = translate_sql(
            "SELECT * FROM bookings WHERE check_out <= date('now') AND user_id = ?"
        )
        self.assertIn('CURRENT_DATE', translated)
        self.assertIn('%s', translated)
        self.assertNotIn('?', translated)

    def test_begin_immediate_becomes_noop_select(self):
        self.assertEqual(translate_sql('BEGIN IMMEDIATE'), 'SELECT 1')

    def test_like_is_case_insensitive(self):
        self.assertIn('ILIKE', translate_sql("SELECT * FROM users WHERE email LIKE ?"))

    def test_last_insert_rowid(self):
        self.assertIn('lastval()', translate_sql('SELECT last_insert_rowid()'))

    def test_julianday_casts_column_arguments(self):
        translated = translate_sql("SELECT julianday(created_at), julianday('now', ?)")
        self.assertIn('julianday((created_at)::text)', translated)
        self.assertIn("julianday('now', %s)", translated)

    def test_tables_without_serial_id_do_not_get_returning(self):
        translated, expects_id = prepare_statement(
            'INSERT INTO email_rate_limits (action, rate_key) VALUES (?, ?)'
        )
        self.assertFalse(expects_id)
        self.assertNotIn('RETURNING', translated)


class PgRowTests(unittest.TestCase):
    def test_key_and_index_access(self):
        row = PgRow(['id', 'name'], [7, 'Test'])
        self.assertEqual(row['id'], 7)
        self.assertEqual(row[1], 'Test')
        self.assertEqual(dict(row), {'id': 7, 'name': 'Test'})
        self.assertEqual(len(row), 2)

    def test_iteration_yields_values(self):
        row = PgRow(['a', 'b'], [1, 2])
        self.assertEqual(list(row), [1, 2])


if __name__ == '__main__':
    unittest.main()
