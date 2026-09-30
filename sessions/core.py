"""会话管理：会话上限、按最近活跃驱逐、断线保留窗口内可重连。

实现要点：在线会话用 OrderedDict 按最近活跃排序（LRU），
开会话/刷新/驱逐/重连均为摊还 O(1)，size 不扫表。
"""

from collections import OrderedDict

MAX_SESSIONS = 3
KEEP_MS = 30000


class Sessions:
    """会话台账。"""

    def __init__(self, max_sessions=MAX_SESSIONS, keep_ms=KEEP_MS):
        self.max_sessions = max_sessions
        self.keep_ms = keep_ms
        self.sessions = OrderedDict()  # player -> 最近活跃时间，按 LRU 排序
        self.closed = {}  # player -> 关闭时间
        self.evicted = 0
        self.scanned = 0

    def _evict_if_needed(self):
        while self.sessions and len(self.sessions) >= self.max_sessions:
            self.sessions.popitem(last=False)
            self.evicted += 1

    def open(self, player, now_ms):
        """开会话；超出上限时驱逐最近活跃时间最旧的会话。"""
        self.closed.pop(player, None)
        if player in self.sessions:
            self.sessions[player] = now_ms
            self.sessions.move_to_end(player)
            return True
        self._evict_if_needed()
        if len(self.sessions) < self.max_sessions:
            self.sessions[player] = now_ms
        return True

    def touch(self, player, now_ms):
        """刷新该会话的最近活跃时间（LRU 依据）。"""
        if player not in self.sessions:
            return False
        self.sessions[player] = now_ms
        self.sessions.move_to_end(player)
        return True

    def close(self, player, now_ms):
        """关闭会话，记录关闭时间以保留重连窗口。"""
        if player in self.sessions:
            del self.sessions[player]
            self.closed[player] = now_ms
        return True

    def reconnect(self, player, now_ms):
        """keep_ms 窗口内允许无代价重连，超过窗口算新会话。"""
        if player in self.sessions:
            return True
        closed_at = self.closed.get(player)
        if closed_at is None:
            return False
        if now_ms - closed_at > self.keep_ms:
            del self.closed[player]
            return False
        del self.closed[player]
        self._evict_if_needed()
        if len(self.sessions) < self.max_sessions:
            self.sessions[player] = now_ms
        return True

    def size(self):
        """当前会话数，O(1)，不扫会话表。"""
        self.scanned += 1
        return len(self.sessions)

    def scanned_count(self):
        return self.scanned
