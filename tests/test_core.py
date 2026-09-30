import random
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


class LimitTest(unittest.TestCase):
    def test_never_exceeds_max_sessions(self):
        book = Sessions(max_sessions=2)
        book.open("a", 0)
        book.open("b", 1)
        book.open("c", 2)
        self.assertEqual(book.size(), 2)

    def test_evicted_counter_increments(self):
        book = Sessions(max_sessions=2)
        book.open("a", 0)
        book.open("b", 1)
        book.open("c", 2)
        self.assertEqual(book.evicted, 1)
        book.open("d", 3)
        self.assertEqual(book.evicted, 2)
        self.assertEqual(book.size(), 2)

    def test_repeated_sequence_is_deterministic(self):
        def run():
            book = Sessions(max_sessions=2)
            results = []
            for player, now in [("a", 0), ("b", 1), ("c", 2), ("d", 3)]:
                results.append(book.open(player, now))
            return book.size(), book.evicted, results

        self.assertEqual(run(), run())


class LruEvictionTest(unittest.TestCase):
    def test_evicts_oldest_active_session(self):
        book = Sessions(max_sessions=2)
        book.open("a", 0)
        book.open("b", 1)
        book.touch("a", 2)
        book.open("c", 3)
        self.assertEqual(book.size(), 2)
        self.assertTrue(book.touch("a", 4))
        self.assertTrue(book.touch("c", 4))
        self.assertFalse(book.touch("b", 4))

    def test_open_refreshes_active_session(self):
        book = Sessions(max_sessions=2)
        book.open("a", 0)
        book.open("b", 1)
        book.open("a", 2)
        book.open("c", 3)
        self.assertTrue(book.touch("a", 4))
        self.assertFalse(book.touch("b", 4))

    def test_touch_missing_session_returns_false(self):
        self.assertFalse(Sessions(max_sessions=2).touch("x", 0))


class ReconnectWindowTest(unittest.TestCase):
    def test_reconnect_within_window_is_free(self):
        book = Sessions(keep_ms=30000)
        book.open("a", 0)
        book.close("a", 0)
        self.assertTrue(book.reconnect("a", 20000))
        self.assertEqual(book.size(), 1)
        self.assertEqual(book.evicted, 0)

    def test_reconnect_at_boundary(self):
        book = Sessions(keep_ms=30000)
        book.open("a", 0)
        book.close("a", 0)
        self.assertTrue(book.reconnect("a", 30000))

    def test_reconnect_after_window_fails(self):
        book = Sessions(keep_ms=30000)
        book.open("a", 0)
        book.close("a", 0)
        self.assertFalse(book.reconnect("a", 30001))
        self.assertEqual(book.size(), 0)

    def test_reconnect_then_close_window_restarts(self):
        book = Sessions(keep_ms=30000)
        book.open("a", 0)
        book.close("a", 0)
        self.assertTrue(book.reconnect("a", 10000))
        book.close("a", 10000)
        self.assertTrue(book.reconnect("a", 35000))
        self.assertFalse(book.reconnect("b", 0))


class ScanCostTest(unittest.TestCase):
    def test_scanned_does_not_grow_with_sessions(self):
        book = Sessions(max_sessions=100000)
        for index in range(3000):
            book.open("p-%d" % index, index)
        before = book.scanned_count()
        for _ in range(3000):
            book.size()
        self.assertEqual(book.scanned_count() - before, 3000)
        self.assertLessEqual(book.scanned_count(), 3000)

    def test_size_cost_constant_at_scale(self):
        book = Sessions(max_sessions=1000000)
        for index in range(10000):
            book.open("p-%d" % index, index)
        book.size()
        small = book.scanned_count()
        for index in range(10000, 20000):
            book.open("p-%d" % index, index)
        book.size()
        self.assertEqual(book.scanned_count() - small, 1)


class ReferenceSessions:
    """直白参考实现：dict 全表 min 取最旧，用于差分比对。"""

    def __init__(self, max_sessions, keep_ms):
        self.max_sessions = max_sessions
        self.keep_ms = keep_ms
        self.active = {}
        self.closed = {}
        self.evicted = 0
        self.tick = 0

    def open(self, player, now_ms):
        self.tick += 1
        if player in self.active:
            self.active[player] = (now_ms, self.tick)
            return True
        self.closed.pop(player, None)
        self.active[player] = (now_ms, self.tick)
        if len(self.active) > self.max_sessions:
            oldest = min(self.active, key=self.active.get)
            del self.active[oldest]
            self.evicted += 1
        return True

    def touch(self, player, now_ms):
        if player not in self.active:
            return False
        self.tick += 1
        self.active[player] = (now_ms, self.tick)
        return True

    def close(self, player, now_ms):
        if player not in self.active:
            return False
        del self.active[player]
        self.closed[player] = now_ms
        return True

    def reconnect(self, player, now_ms):
        if player in self.active:
            return True
        closed_at = self.closed.get(player)
        if closed_at is None or now_ms - closed_at > self.keep_ms:
            self.closed.pop(player, None)
            return False
        del self.closed[player]
        self.tick += 1
        self.active[player] = (now_ms, self.tick)
        if len(self.active) > self.max_sessions:
            oldest = min(self.active, key=self.active.get)
            del self.active[oldest]
            self.evicted += 1
        return True

    def size(self):
        return len(self.active)


class DifferentialTest(unittest.TestCase):
    def test_random_sequences_match_reference(self):
        rng = random.Random(230)
        for _ in range(200):
            max_sessions = rng.randint(1, 5)
            keep_ms = rng.randint(0, 50)
            actual = Sessions(max_sessions=max_sessions, keep_ms=keep_ms)
            reference = ReferenceSessions(max_sessions, keep_ms)
            players = ["p%d" % i for i in range(rng.randint(1, 8))]
            now = 0
            for _ in range(rng.randint(20, 80)):
                now += rng.randint(0, 40)
                player = rng.choice(players)
                op = rng.choice(
                    [actual.open, actual.touch, actual.close, actual.reconnect]
                )
                ref_op = getattr(reference, op.__name__)
                self.assertEqual(
                    op(player, now),
                    ref_op(player, now),
                    msg=(op.__name__, player, now),
                )
                self.assertEqual(actual.size(), reference.size())
                self.assertEqual(actual.evicted, reference.evicted)
                self.assertLessEqual(actual.size(), max_sessions)


if __name__ == "__main__":
    unittest.main()
