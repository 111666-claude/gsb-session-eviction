"""会话管理：会话上限、按最近活跃驱逐、断线保留窗口内可重连。

缺陷：不设会话上限（只增不减）、驱逐不看最近活跃、重连窗口不生效、查询全扫会话表。
"""

MAX_SESSIONS = 3
KEEP_MS = 30000


class Sessions:
    """会话台账。"""

    def __init__(self, max_sessions=MAX_SESSIONS, keep_ms=KEEP_MS):
        self.max_sessions = max_sessions
        self.keep_ms = keep_ms
        self.sessions = {}
        self.closed = {}
        self.evicted = 0
        self.scanned = 0

    def open(self, player, now_ms):
        """开会话。缺陷：不看会话上限，超出也不驱逐最久未活跃的会话。"""
        self.sessions[player] = [now_ms, now_ms]
        return True

    def touch(self, player, now_ms):
        """刷新活跃时间。缺陷：不改最近活跃时间（LRU 依据失效）。"""
        return player in self.sessions

    def close(self, player, now_ms):
        """关闭会话。缺陷：直接丢掉，不留重连窗口。"""
        self.sessions.pop(player, None)
        return True

    def reconnect(self, player, now_ms):
        """重连。缺陷：永远失败（没有保留窗口）。"""
        return False

    def size(self):
        """当前会话数。缺陷：每次全扫会话表。"""
        self.scanned += len(self.sessions)
        return len(self.sessions)

    def scanned_count(self):
        return self.scanned
