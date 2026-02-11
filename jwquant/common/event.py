"""
事件总线

模块间解耦通信机制，支持发布/订阅模式。
事件类型包括：行情事件、信号事件、成交事件、风控事件等。
"""
from collections import defaultdict
from typing import Any, Callable


class EventBus:
    """简单的发布/订阅事件总线"""

    def __init__(self):
        self._handlers: dict[str, list[Callable]] = defaultdict(list)

    def subscribe(self, event_type: str, handler: Callable) -> None:
        """订阅事件"""
        self._handlers[event_type].append(handler)

    def unsubscribe(self, event_type: str, handler: Callable) -> None:
        """取消订阅"""
        self._handlers[event_type].remove(handler)

    def publish(self, event_type: str, data: Any = None) -> None:
        """发布事件"""
        for handler in self._handlers.get(event_type, []):
            handler(data)


# 全局事件总线实例
bus = EventBus()
