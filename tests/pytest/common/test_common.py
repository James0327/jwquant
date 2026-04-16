"""
common 层单元测试

覆盖 types / config / log / event / notifier 五个模块。
"""
import json
import logging
import os
import tempfile
import time
from datetime import datetime
from pathlib import Path
from unittest import mock

import pytest


# =========================================================================
# 1. types
# =========================================================================

class TestTypes:
    """测试公共数据类型的实例化和字段默认值。"""

    def test_bar(self):
        from jwquant.common.types import Bar
        bar = Bar(code="600519.SH", dt=datetime.now(),
                  open=1800, high=1850, low=1790, close=1840, volume=10000)
        assert bar.amount == 0.0

    def test_tick(self):
        from jwquant.common.types import Tick
        tick = Tick(code="600519.SH", dt=datetime.now(),
                    last_price=1840.0, volume=5000,
                    bid_price=1839.9, bid_volume=100,
                    ask_price=1840.1, ask_volume=200)
        assert tick.open_interest == 0.0

    def test_signal(self):
        from jwquant.common.types import Signal, SignalType
        sig = Signal(code="600519.SH", dt=datetime.now(),
                     signal_type=SignalType.BUY, price=1840.0)
        assert sig.strength == 1.0
        assert sig.reason == ""

    def test_order(self):
        from jwquant.common.types import Order, Direction, OrderStatus
        order = Order(code="600519.SH", direction=Direction.BUY,
                      price=1840.0, volume=100)
        assert order.status == OrderStatus.PENDING
        assert order.order_id == ""

    def test_trade(self):
        from jwquant.common.types import Trade, Direction
        trade = Trade(trade_id="T001", order_id="O001",
                      code="600519.SH", direction=Direction.BUY,
                      price=1840.0, volume=100, dt=datetime.now())
        assert trade.commission == 0.0
        assert trade.slippage == 0.0

    def test_position(self):
        from jwquant.common.types import Position
        pos = Position(code="600519.SH", volume=200, available=200,
                       cost_price=1800.0)
        assert pos.market_value == 0.0

    def test_asset(self):
        from jwquant.common.types import Asset
        asset = Asset(cash=100000.0)
        assert asset.total_asset == 0.0

    def test_risk_event(self):
        from jwquant.common.types import RiskEvent
        evt = RiskEvent(risk_type="MAX_POSITION", severity="WARNING",
                        code="600519.SH", message="Position exceeds limit",
                        dt=datetime.now())
        assert evt.action_taken == ""
        assert evt.metadata == {}

    def test_strategy_meta(self):
        from jwquant.common.types import StrategyMeta
        meta = StrategyMeta(name="turtle", version="1.0",
                            params={"entry_window": 20})
        assert meta.status == "INITIALIZED"
        assert meta.created_at is None


# =========================================================================
# 2. config
# =========================================================================

class TestConfig:
    """测试配置管理功能。"""

    def _write_toml(self, tmp: Path, name: str, content: str) -> Path:
        p = tmp / name
        p.write_text(content, encoding="utf-8")
        return p

    def test_load_and_get(self, tmp_path):
        from jwquant.common import config
        f = self._write_toml(tmp_path, "test.toml", """
[broker.xtquant]
path = "/tmp/test"
account_id = "12345"
""")
        config.load_config(f)
        assert config.get("broker.xtquant.path") == "/tmp/test"
        assert config.get("broker.xtquant.account_id") == "12345"
        assert config.get("nonexistent", "default") == "default"

    def test_multi_file_merge(self, tmp_path):
        from jwquant.common import config
        primary = self._write_toml(tmp_path, "a.toml", """
[risk]
max_position_pct = 0.2
max_order_amount = 100000
""")
        extra = self._write_toml(tmp_path, "b.toml", """
[risk]
max_position_pct = 0.3

[turtle]
entry_window = 20
""")
        config.load_config(primary, extra=[extra])
        # extra 覆盖 primary 的叶子节点
        assert config.get("risk.max_position_pct") == 0.3
        # primary 的其他字段保留
        assert config.get("risk.max_order_amount") == 100000
        # extra 新增的字段
        assert config.get("turtle.entry_window") == 20

    def test_env_override(self, tmp_path):
        from jwquant.common import config
        f = self._write_toml(tmp_path, "c.toml", """
[llm]
api_key = "original"
""")
        with mock.patch.dict(os.environ, {"JWQUANT_LLM__API_KEY": "from_env"}):
            config.load_config(f)
        assert config.get("llm.api_key") == "from_env"

    def test_env_type_coercion(self, tmp_path):
        from jwquant.common import config
        f = self._write_toml(tmp_path, "d.toml", "[project]\nname = 'test'")
        with mock.patch.dict(os.environ, {
            "JWQUANT_NOTIFICATION__ENABLED": "true",
            "JWQUANT_RISK__MAX_ORDER_AMOUNT": "50000",
            "JWQUANT_RISK__MAX_POSITION_PCT": "0.15",
        }):
            config.load_config(f)
        assert config.get("notification.enabled") is True
        assert config.get("risk.max_order_amount") == 50000
        assert config.get("risk.max_position_pct") == 0.15

    def test_typed_getters(self, tmp_path):
        from jwquant.common import config
        f = self._write_toml(tmp_path, "e.toml", """
[project]
name = "jwquant"
version = 1
ratio = 0.5
enabled = true
""")
        config.load_config(f)
        assert config.get_str("project.name") == "jwquant"
        assert config.get_int("project.version") == 1
        assert config.get_float("project.ratio") == 0.5
        assert config.get_bool("project.enabled") is True
        # defaults
        assert config.get_str("missing") == ""
        assert config.get_int("missing") == 0
        assert config.get_float("missing") == 0.0
        assert config.get_bool("missing") is False

    def test_masked_config(self, tmp_path):
        from jwquant.common import config
        f = self._write_toml(tmp_path, "f.toml", """
[llm]
api_key = "sk-secret123"
model = "gpt-4o"
""")
        config.load_config(f)
        masked = config.get_masked_config()
        assert masked["llm"]["api_key"] == "***"
        assert masked["llm"]["model"] == "gpt-4o"

    def test_validate_good_config(self, tmp_path):
        from jwquant.common import config
        f = self._write_toml(tmp_path, "g.toml", """
[risk]
max_position_pct = 0.2
max_daily_drawdown = 0.05
max_order_amount = 100000
""")
        config.load_config(f)
        errors = config.validate()
        assert errors == []

    def test_validate_bad_config(self, tmp_path):
        from jwquant.common import config
        f = self._write_toml(tmp_path, "h.toml", """
[risk]
max_position_pct = 1.5
max_daily_drawdown = -0.1
max_order_amount = -100
""")
        config.load_config(f)
        errors = config.validate()
        assert len(errors) == 3


# =========================================================================
# 3. log
# =========================================================================

class TestLog:
    """测试日志系统功能。"""

    def _clear_loggers(self):
        """清理已创建的日志器避免测试间干扰。"""
        for name in list(logging.Logger.manager.loggerDict):
            if name.startswith("jwquant."):
                logger = logging.getLogger(name)
                logger.handlers.clear()

    def test_get_logger_console(self):
        self._clear_loggers()
        from jwquant.common.log import get_logger
        logger = get_logger("jwquant.test.console", level=logging.DEBUG)
        assert logger.name == "jwquant.test.console"
        assert len(logger.handlers) >= 1

    def test_get_logger_file(self, tmp_path):
        self._clear_loggers()
        from jwquant.common.log import get_logger
        logger = get_logger("jwquant.test.file", enable_file=True,
                            log_dir=str(tmp_path))
        assert len(logger.handlers) == 2  # console + file
        logger.info("test file log")
        # 检查文件是否创建
        log_files = list(tmp_path.glob("*.log"))
        assert len(log_files) == 1

    def test_json_formatter(self, tmp_path):
        self._clear_loggers()
        from jwquant.common.log import get_logger
        logger = get_logger("jwquant.test.json", enable_file=True,
                            json_format=True, log_dir=str(tmp_path))
        logger.info("json test message")
        log_file = list(tmp_path.glob("*.log"))[0]
        content = log_file.read_text(encoding="utf-8").strip()
        data = json.loads(content)
        assert data["level"] == "INFO"
        assert data["msg"] == "json test message"
        assert "ts" in data

    def test_log_elapsed_decorator(self, capsys):
        self._clear_loggers()
        from jwquant.common.log import log_elapsed, get_logger

        test_logger = get_logger("jwquant.test.elapsed")

        @log_elapsed(test_logger)
        def slow_fn():
            time.sleep(0.05)
            return 42

        result = slow_fn()
        assert result == 42
        captured = capsys.readouterr()
        assert "slow_fn" in captured.out
        assert "completed in" in captured.out

    def test_set_log_level(self):
        self._clear_loggers()
        from jwquant.common.log import get_logger, set_log_level
        logger = get_logger("jwquant.test.level")
        assert logger.level == logging.INFO
        set_log_level("jwquant.test.level", logging.DEBUG)
        assert logger.level == logging.DEBUG

    def test_category_loggers(self):
        self._clear_loggers()
        from jwquant.common.log import (
            get_trade_logger, get_strategy_logger,
            get_agent_logger, get_system_logger,
        )
        assert get_trade_logger().name == "jwquant.trade"
        assert get_strategy_logger().name == "jwquant.strategy"
        assert get_agent_logger().name == "jwquant.agent"
        assert get_system_logger().name == "jwquant.system"


# =========================================================================
# 4. event
# =========================================================================

class TestEvent:
    """测试事件总线功能。"""

    def test_basic_pub_sub(self):
        from jwquant.common.event import EventBus
        bus = EventBus()
        received = []
        bus.subscribe("test", lambda d: received.append(d))
        bus.publish("test", "hello", log_event=False)
        assert received == ["hello"]

    def test_priority_ordering(self):
        from jwquant.common.event import EventBus
        bus = EventBus()
        order = []
        bus.subscribe("test", lambda d: order.append("low"), priority=0)
        bus.subscribe("test", lambda d: order.append("high"), priority=100)
        bus.subscribe("test", lambda d: order.append("mid"), priority=50)
        bus.publish("test", log_event=False)
        assert order == ["high", "mid", "low"]

    def test_filtered_subscribe(self):
        from jwquant.common.event import EventBus
        bus = EventBus()
        received = []
        bus.subscribe_filtered(
            "order", lambda d: received.append(d),
            filter_fn=lambda d: d.get("code") == "600519.SH",
        )
        bus.publish("order", {"code": "600519.SH", "vol": 100}, log_event=False)
        bus.publish("order", {"code": "000001.SZ", "vol": 200}, log_event=False)
        assert len(received) == 1
        assert received[0]["code"] == "600519.SH"

    def test_unsubscribe(self):
        from jwquant.common.event import EventBus
        bus = EventBus()
        received = []
        handler = lambda d: received.append(d)
        bus.subscribe("test", handler)
        bus.publish("test", 1, log_event=False)
        bus.unsubscribe("test", handler)
        bus.publish("test", 2, log_event=False)
        assert received == [1]

    def test_unsubscribe_filtered(self):
        from jwquant.common.event import EventBus
        bus = EventBus()
        received = []
        handler = lambda d: received.append(d)
        bus.subscribe_filtered("test", handler, filter_fn=lambda d: True)
        bus.publish("test", "a", log_event=False)
        bus.unsubscribe("test", handler)
        bus.publish("test", "b", log_event=False)
        assert received == ["a"]

    def test_event_type_constants(self):
        from jwquant.common.event import EventType
        assert EventType.BAR == "event.market.bar"
        assert EventType.ORDER_FILLED == "event.order.filled"
        assert EventType.RISK_VIOLATION == "event.risk.violation"

    def test_handler_error_isolation(self):
        from jwquant.common.event import EventBus
        bus = EventBus()
        received = []

        def bad_handler(d):
            raise RuntimeError("boom")

        bus.subscribe("test", bad_handler, priority=100)
        bus.subscribe("test", lambda d: received.append(d), priority=0)
        bus.publish("test", "ok", log_event=False)
        # 第二个 handler 不受影响
        assert received == ["ok"]

    def test_utility_methods(self):
        from jwquant.common.event import EventBus
        bus = EventBus()
        bus.subscribe("a", lambda d: None)
        bus.subscribe("a", lambda d: None)
        bus.subscribe("b", lambda d: None)
        assert bus.get_subscriber_count("a") == 2
        assert set(bus.get_all_event_types()) == {"a", "b"}
        bus.clear("a")
        assert bus.get_subscriber_count("a") == 0
        bus.clear()
        assert bus.get_all_event_types() == []


# =========================================================================
# 5. notifier
# =========================================================================

class TestNotifier:
    """测试通知系统功能。"""

    def test_rate_limiter_allow(self):
        from jwquant.common.notifier import RateLimiter
        limiter = RateLimiter(max_per_minute=3)
        assert limiter.allow() is True
        assert limiter.allow() is True
        assert limiter.allow() is True
        assert limiter.allow() is False  # 第 4 次被拒绝

    def test_render_template(self):
        from jwquant.common.notifier import render_template
        body = render_template(
            "order_filled",
            code="600519.SH", direction="买入",
            price=1840.0, volume=100, timestamp="2026-02-11 10:30:00",
        )
        assert "600519.SH" in body
        assert "1840.0" in body
        assert "委托成交" in body

    def test_render_template_unknown(self):
        from jwquant.common.notifier import render_template
        with pytest.raises(KeyError, match="Unknown template"):
            render_template("nonexistent")

    def test_wechat_notifier_no_token(self):
        from jwquant.common.notifier import WeChatNotifier
        n = WeChatNotifier(provider="serverchan", token="")
        assert n.send("test", "body") is False

    def test_dingtalk_notifier_no_webhook(self):
        from jwquant.common.notifier import DingTalkNotifier
        n = DingTalkNotifier(webhook="", secret="")
        assert n.send("test", "body") is False

    def test_email_notifier_no_server(self):
        from jwquant.common.notifier import EmailNotifier
        n = EmailNotifier(smtp_server="", to_addrs=[])
        assert n.send("test", "body") is False

    def test_wechat_notifier_send_success(self):
        from jwquant.common.notifier import WeChatNotifier
        n = WeChatNotifier(provider="serverchan", token="test_token")

        response = json.dumps({"code": 0, "message": "ok"}).encode()
        mock_resp = mock.MagicMock()
        mock_resp.read.return_value = response
        mock_resp.__enter__ = mock.MagicMock(return_value=mock_resp)
        mock_resp.__exit__ = mock.MagicMock(return_value=False)

        with mock.patch("urllib.request.urlopen", return_value=mock_resp):
            assert n.send("title", "body") is True

    def test_dingtalk_notifier_send_success(self):
        from jwquant.common.notifier import DingTalkNotifier
        n = DingTalkNotifier(
            webhook="https://oapi.dingtalk.com/robot/send?access_token=test",
        )
        response = json.dumps({"errcode": 0, "errmsg": "ok"}).encode()
        mock_resp = mock.MagicMock()
        mock_resp.read.return_value = response
        mock_resp.__enter__ = mock.MagicMock(return_value=mock_resp)
        mock_resp.__exit__ = mock.MagicMock(return_value=False)

        with mock.patch("urllib.request.urlopen", return_value=mock_resp):
            assert n.send("title", "body") is True

    def test_dingtalk_sign_url(self):
        from jwquant.common.notifier import DingTalkNotifier
        n = DingTalkNotifier(
            webhook="https://oapi.dingtalk.com/robot/send?access_token=test",
            secret="SEC123",
        )
        url = n._sign_url()
        assert "timestamp=" in url
        assert "sign=" in url

    def test_notification_router_routing(self):
        from jwquant.common.notifier import NotificationRouter, WeChatNotifier
        router = NotificationRouter()
        router._initialized = True
        mock_wechat = mock.MagicMock(spec=WeChatNotifier)
        mock_wechat.send.return_value = True
        router._channels = {"wechat": mock_wechat}
        router._routing = {"INFO": ["wechat"], "ERROR": ["wechat", "email"]}

        result = router.send("test", "body", level="INFO")
        assert result == {"wechat": True}
        mock_wechat.send.assert_called_once_with("test", "body")

    def test_send_notification_disabled(self, tmp_path):
        """notification.enabled = false 时不发送。"""
        from jwquant.common import config, notifier
        # 重置路由器
        notifier._router = None

        f = tmp_path / "test.toml"
        f.write_text("[notification]\nenabled = false\n")
        config.load_config(f)

        result = notifier.send_notification("title", "body")
        assert result == {}
