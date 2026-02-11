"""
事件总线

模块间解耦通信机制，支持：
- 发布/订阅模式
- 标准化事件类型常量
- 处理器优先级（高优先级先执行）
- 条件过滤订阅
- 事件日志记录
"""
import logging
from collections import defaultdict
from typing import Any, Callable


# ---------------------------------------------------------------------------
# Event type constants
# ---------------------------------------------------------------------------

class EventType:
    """标准化事件类型常量，防止字符串拼写错误，提供 IDE 自动补全。"""

    # 行情事件
    BAR = "event.market.bar"
    TICK = "event.market.tick"

    # 信号事件
    SIGNAL = "event.signal.generated"

    # 订单事件
    ORDER_SUBMITTED = "event.order.submitted"
    ORDER_FILLED = "event.order.filled"
    ORDER_CANCELLED = "event.order.cancelled"
    ORDER_REJECTED = "event.order.rejected"

    # 成交事件
    TRADE = "event.trade.executed"

    # 风控事件
    RISK_VIOLATION = "event.risk.violation"
    RISK_WARNING = "event.risk.warning"

    # 系统事件
    STRATEGY_STARTED = "event.system.strategy.started"
    STRATEGY_STOPPED = "event.system.strategy.stopped"
    SYSTEM_ERROR = "event.system.error"


# ---------------------------------------------------------------------------
# Event Bus
# ---------------------------------------------------------------------------

class EventBus:
    """发布/订阅事件总线，支持优先级、过滤和事件日志。

    优先级规则：
      - 数值越大越先执行（如 100 > 50 > 0）
      - 风控拦截器建议设为 100，策略处理器 50，日志/通知 0
      - 默认优先级 0，保持向后兼容
    """

    def __init__(self) -> None:
        # event_type -> sorted list of (priority, handler)
        self._handlers: dict[str, list[tuple[int, Callable]]] = defaultdict(list)
        self._logger = logging.getLogger("jwquant.event")

    def subscribe(
        self, event_type: str, handler: Callable, priority: int = 0
    ) -> None:
        """订阅事件。

        Args:
            event_type: 事件类型字符串（建议使用 EventType 常量）。
            handler: 回调函数，签名 ``handler(data) -> None``。
            priority: 优先级，数值越大越先执行。
        """
        handlers = self._handlers[event_type]
        handlers.append((priority, handler))
        # 按优先级降序排列
        handlers.sort(key=lambda x: x[0], reverse=True)

    def subscribe_filtered(
        self,
        event_type: str,
        handler: Callable,
        filter_fn: Callable[[Any], bool],
        priority: int = 0,
    ) -> None:
        """条件订阅：仅当 filter_fn(data) 返回 True 时才触发 handler。"""
        def _filtered_handler(data: Any) -> None:
            if filter_fn(data):
                handler(data)

        # 保留原始 handler 引用便于取消订阅
        _filtered_handler._original = handler  # type: ignore[attr-defined]
        self.subscribe(event_type, _filtered_handler, priority)

    def unsubscribe(self, event_type: str, handler: Callable) -> None:
        """取消订阅。同时支持直接 handler 和 filtered handler 的取消。"""
        handlers = self._handlers.get(event_type, [])
        self._handlers[event_type] = [
            (p, h) for p, h in handlers
            if h is not handler and getattr(h, "_original", None) is not handler
        ]

    def publish(
        self, event_type: str, data: Any = None, log_event: bool = True
    ) -> None:
        """发布事件，按优先级顺序触发所有已注册的处理器。

        Args:
            event_type: 事件类型。
            data: 事件数据。
            log_event: 是否记录事件日志（高频事件如 BAR/TICK 建议关闭）。
        """
        if log_event:
            self._logger.debug("Event: %s | data=%s", event_type, _summarize(data))

        for _priority, handler in self._handlers.get(event_type, []):
            try:
                handler(data)
            except Exception:
                self._logger.error(
                    "Handler %s failed for event %s",
                    getattr(handler, "__name__", repr(handler)),
                    event_type,
                    exc_info=True,
                )

    # ------------------------------------------------------------------
    # Utility methods
    # ------------------------------------------------------------------

    def get_subscriber_count(self, event_type: str) -> int:
        """返回指定事件类型的订阅者数量。"""
        return len(self._handlers.get(event_type, []))

    def get_all_event_types(self) -> list[str]:
        """返回所有已注册的事件类型列表。"""
        return list(self._handlers.keys())

    def clear(self, event_type: str | None = None) -> None:
        """清除事件处理器。不传参数则清除全部。"""
        if event_type is None:
            self._handlers.clear()
        else:
            self._handlers.pop(event_type, None)


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def _summarize(data: Any, max_len: int = 200) -> str:
    """生成数据摘要用于日志输出。"""
    if data is None:
        return "None"
    text = repr(data)
    if len(text) > max_len:
        return text[:max_len] + "..."
    return text


# ---------------------------------------------------------------------------
# Global instance
# ---------------------------------------------------------------------------

bus = EventBus()
