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


class LimitTest(unittest.TestCase):
    def test_size_never_exceeds_max(self):
        book = Sessions(max_sessions=2)
        for index in range(10):
            book.open("p-%d" % index, index)
            self.assertLessEqual(book.size(), 2)

    def test_evicts_oldest_and_counts(self):
        book = Sessions(max_sessions=2)
        book.open("a", 0)
        book.open("b", 1)
        book.open("c", 2)
        self.assertEqual(book.size(), 2)
        self.assertEqual(book.evicted, 1)
        self.assertNotIn("a", book.sessions)

    def test_reopen_existing_does_not_evict(self):
        book = Sessions(max_sessions=2)
        book.open("a", 0)
        book.open("b", 1)
        book.open("a", 2)
        self.assertEqual(book.evicted, 0)
        self.assertEqual(book.size(), 2)


class LruTest(unittest.TestCase):
    def test_touch_refreshes_last_active(self):
        book = Sessions(max_sessions=2)
        book.open("a", 0)
        book.open("b", 1)
        self.assertTrue(book.touch("a", 2))
        book.open("c", 3)
        self.assertIn("a", book.sessions)
        self.assertNotIn("b", book.sessions)
        self.assertEqual(book.evicted, 1)

    def test_touch_missing_returns_false(self):
        self.assertFalse(Sessions().touch("ghost", 0))


class ReconnectTest(unittest.TestCase):
    def test_reconnect_within_window(self):
        book = Sessions(keep_ms=30000)
        book.open("a", 0)
        book.close("a", 100)
        self.assertTrue(book.reconnect("a", 100 + 30000))
        self.assertEqual(book.size(), 1)

    def test_reconnect_after_window_is_new_session(self):
        book = Sessions(keep_ms=30000)
        book.open("a", 0)
        book.close("a", 100)
        self.assertFalse(book.reconnect("a", 101 + 30000))
        self.assertEqual(book.size(), 0)

    def test_reconnect_unknown_player_fails(self):
        self.assertFalse(Sessions().reconnect("ghost", 0))

    def test_reconnect_evicts_when_full(self):
        book = Sessions(max_sessions=1, keep_ms=30000)
        book.open("a", 0)
        book.close("a", 1)
        book.open("b", 2)
        self.assertTrue(book.reconnect("a", 3))
        self.assertEqual(book.size(), 1)
        self.assertEqual(book.evicted, 1)


class ScanCostTest(unittest.TestCase):
    def test_size_does_not_scan_table(self):
        book = Sessions(max_sessions=100000)
        for index in range(3000):
            book.open("p-%d" % index, index)
        before = book.scanned_count()
        for _ in range(3000):
            book.size()
        self.assertLessEqual(book.scanned_count() - before, 3000)

    def test_scanned_independent_of_session_count(self):
        small = Sessions()
        large = Sessions(max_sessions=100000)
        for index in range(5000):
            large.open("p-%d" % index, index)
        small.open("only", 0)
        small.size()
        large.size()
        self.assertEqual(small.scanned_count(), large.scanned_count())


class DeterminismTest(unittest.TestCase):
    def test_same_ops_same_result(self):
        def run():
            book = Sessions(max_sessions=2, keep_ms=10)
            trace = []
            for op, player, now in [
                ("open", "a", 0), ("open", "b", 1), ("touch", "a", 2),
                ("open", "c", 3), ("close", "a", 4), ("reconnect", "a", 9),
                ("reconnect", "b", 30), ("open", "d", 31),
            ]:
                trace.append(getattr(book, op)(player, now))
            return trace, book.size(), book.evicted

        self.assertEqual(run(), run())


class Reference:
    """参考实现：全扫找最旧会话，口径与 README 一致。"""

    def __init__(self, max_sessions, keep_ms):
        self.max_sessions = max_sessions
        self.keep_ms = keep_ms
        self.online = {}
        self.closed = {}
        self.evicted = 0

    def _evict(self):
        while len(self.online) >= self.max_sessions and self.online:
            oldest = min(self.online, key=lambda p: self.online[p])
            del self.online[oldest]
            self.evicted += 1

    def open(self, player, now):
        self.closed.pop(player, None)
        if player in self.online:
            del self.online[player]
            self.online[player] = now
            return True
        self._evict()
        if len(self.online) < self.max_sessions:
            self.online[player] = now
        return True

    def touch(self, player, now):
        if player not in self.online:
            return False
        del self.online[player]
        self.online[player] = now
        return True

    def close(self, player, now):
        if player in self.online:
            del self.online[player]
            self.closed[player] = now
        return True

    def reconnect(self, player, now):
        if player in self.online:
            return True
        closed_at = self.closed.get(player)
        if closed_at is None:
            return False
        if now - closed_at > self.keep_ms:
            del self.closed[player]
            return False
        del self.closed[player]
        self._evict()
        if len(self.online) < self.max_sessions:
            self.online[player] = now
        return True

    def size(self):
        return len(self.online)


class ReferenceCompareTest(unittest.TestCase):
    def test_random_sequences_match_reference(self):
        import random

        rng = random.Random(20261001)
        players = ["p-%d" % index for index in range(8)]
        for _ in range(200):
            max_sessions = rng.randint(1, 5)
            keep_ms = rng.randint(1, 50)
            book = Sessions(max_sessions=max_sessions, keep_ms=keep_ms)
            ref = Reference(max_sessions=max_sessions, keep_ms=keep_ms)
            now = 0
            for _ in range(rng.randint(10, 60)):
                now += rng.randint(0, 20)
                op = rng.choice(["open", "touch", "close", "reconnect"])
                player = rng.choice(players)
                got = getattr(book, op)(player, now)
                want = getattr(ref, op)(player, now)
                self.assertEqual(got, want)
                self.assertEqual(book.size(), ref.size())
                self.assertEqual(book.evicted, ref.evicted)
                self.assertLessEqual(book.size(), max_sessions)
