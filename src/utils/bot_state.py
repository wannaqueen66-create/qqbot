import time
from dataclasses import dataclass
from typing import Optional


@dataclass
class BotConnState:
    last_connect_ts: Optional[int] = None
    last_disconnect_ts: Optional[int] = None


state = BotConnState()


def mark_connect():
    state.last_connect_ts = int(time.time())


def mark_disconnect():
    state.last_disconnect_ts = int(time.time())
