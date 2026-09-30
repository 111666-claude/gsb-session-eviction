# session-eviction

会话管理：会话上限、按最近活跃驱逐、断线保留窗口内可重连，只用 Python 标准库。

```
python3 -m sessions.cli --sample limit
python3 -m sessions.cli --sample keep
python3 -m unittest discover -s tests -v
```

## 口径（README 为准）

- **会话上限**：在线会话数不超过 `max_sessions`；超出时驱逐**最近活跃时间最旧**的会话，
  `evicted` 加一。
- **活跃时间**：`touch` 必须刷新该会话的最近活跃时间（LRU 依据）。
- **重连窗口**：关闭的会话在 `keep_ms` 内允许无代价重连（`reconnect` 返回 `True`），
  超过窗口才算新会话。
- **不变量**：在线会话数永远不大于 `max_sessions`；同一串操作重复执行结果相同。
- **查询代价**：`size` 不许每次全扫会话表，`scanned_count` 不随会话数线性增长。
- **规模**：单大区 100 万会话、每秒 10 万次开关与查询，单次摊还 O(1)。

## 输出契约（不改格式）

```
size=2 evicted=1
reconnected=true
scanned<=3000
```

## 目录

```
sessions/core.py   上限、LRU 与重连窗口
sessions/cli.py    命令行入口
tests/             unittest 用例
```
