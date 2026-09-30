"""会话管理：会话上限、按最近活跃驱逐、断线保留窗口内可重连。"""

from collections import OrderedDict

MAX_SESSIONS = 3
KEEP_MS = 30000


class Sessions:
    """会话台账。

    在线会话保存在 OrderedDict 中，顺序即最近活跃时间从旧到新；
    ``touch``/``open``/``reconnect`` 把会话移到末尾，驱逐直接弹出队首，
    所有操作摊还 O(1)。``size`` 走维护的计数器，不扫描会话表。
    """

    def __init__(self, max_sessions=MAX_SESSIONS, keep_ms=KEEP_MS):
        self.max_sessions = max_sessions
        self.keep_ms = keep_ms
        self.sessions = OrderedDict()
        self.closed = {}
        self._size = 0
        self.evicted = 0
        self.scanned = 0

    def open(self, player, now_ms):
        """开会话；已在线则刷新活跃时间，超上限驱逐最久未活跃会话。"""
        if player in self.sessions:
            self.sessions[player] = now_ms
            self.sessions.move_to_end(player)
            return True
        self.closed.pop(player, None)
        self.sessions[player] = now_ms
        self._size += 1
        if self._size > self.max_sessions:
            self.sessions.popitem(last=False)
            self._size -= 1
            self.evicted += 1
        return True

    def touch(self, player, now_ms):
        """刷新最近活跃时间（LRU 依据），会话不存在返回 False。"""
        if player not in self.sessions:
            return False
        self.sessions[player] = now_ms
        self.sessions.move_to_end(player)
        return True

    def close(self, player, now_ms):
        """关闭会话并记下关闭时间，供 keep_ms 内无代价重连。"""
        if player not in self.sessions:
            return False
        del self.sessions[player]
        self._size -= 1
        self.closed[player] = now_ms
        return True

    def reconnect(self, player, now_ms):
        """keep_ms 内重连关闭的会话返回 True，超过窗口返回 False。"""
        if player in self.sessions:
            return True
        closed_at = self.closed.get(player)
        if closed_at is None:
            return False
        if now_ms - closed_at > self.keep_ms:
            del self.closed[player]
            return False
        del self.closed[player]
        self.sessions[player] = now_ms
        self._size += 1
        if self._size > self.max_sessions:
            self.sessions.popitem(last=False)
            self._size -= 1
            self.evicted += 1
        return True

    def size(self):
        """当前在线会话数，O(1)：只记常数级扫描代价。"""
        self.scanned += 1
        return self._size

    def scanned_count(self):
        return self.scanned
