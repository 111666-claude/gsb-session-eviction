import unittest

from sessions.core import Sessions


class OpenTest(unittest.TestCase):
    def test_open_returns_true(self):
        self.assertTrue(Sessions().open("a", 0))

    def test_size_counts_session(self):
        book = Sessions()
        book.open("a", 0)
        self.assertEqual(book.size(), 1)


class CloseTest(unittest.TestCase):
    def test_close_removes_session(self):
        book = Sessions()
        book.open("a", 0)
        book.close("a", 0)
        self.assertEqual(book.size(), 0)

    def test_scanned_starts_at_zero(self):
        self.assertEqual(Sessions().scanned_count(), 0)


if __name__ == "__main__":
    unittest.main()
