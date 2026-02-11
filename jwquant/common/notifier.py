"""
消息通知

多渠道消息推送系统，支持：
- 微信通知（Server酱 / PushPlus）
- 钉钉机器人（Webhook + HMAC-SHA256 签名）
- 邮件通知（SMTP + TLS）
- 通知分级路由（INFO/WARNING/ERROR/CRITICAL → 不同渠道组合）
- 速率限制（滑动窗口防刷屏）
- 失败重试（指数退避）
- 预置消息模板
"""
import base64
import hashlib
import hmac
import json
import logging
import smtplib
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from abc import ABC, abstractmethod
from collections import deque
from email.mime.text import MIMEText
from typing import Any

logger = logging.getLogger("jwquant.notifier")


# ---------------------------------------------------------------------------
# Message templates
# ---------------------------------------------------------------------------

_TEMPLATES: dict[str, str] = {
    "order_filled": (
        "### 委托成交\n"
        "- **股票**: {code}\n"
        "- **方向**: {direction}\n"
        "- **价格**: {price}\n"
        "- **数量**: {volume}\n"
        "- **时间**: {timestamp}"
    ),
    "risk_alert": (
        "### 风控预警\n"
        "- **类型**: {risk_type}\n"
        "- **级别**: {severity}\n"
        "- **详情**: {message}\n"
        "- **时间**: {timestamp}"
    ),
    "daily_briefing": (
        "### 每日投资晨报 ({date})\n\n{summary}"
    ),
    "system_error": (
        "### 系统异常\n"
        "- **错误**: {error}\n"
        "- **堆栈**: {traceback}\n"
        "- **时间**: {timestamp}"
    ),
}


def render_template(template_name: str, **kwargs: Any) -> str:
    """渲染消息模板。

    Args:
        template_name: 模板名称（如 "order_filled"）。
        **kwargs: 模板变量。

    Returns:
        渲染后的消息文本。

    Raises:
        KeyError: 模板不存在或缺少必需变量。
    """
    tpl = _TEMPLATES.get(template_name)
    if tpl is None:
        raise KeyError(f"Unknown template: {template_name}")
    return tpl.format(**kwargs)


# ---------------------------------------------------------------------------
# Rate limiter
# ---------------------------------------------------------------------------

class RateLimiter:
    """滑动窗口速率限制器。

    Args:
        max_per_minute: 每分钟允许的最大消息数。
    """

    def __init__(self, max_per_minute: int = 10) -> None:
        self._max = max_per_minute
        self._timestamps: deque[float] = deque()
        self._lock = threading.Lock()

    def allow(self) -> bool:
        """检查是否允许发送（True = 允许）。"""
        now = time.time()
        with self._lock:
            # 移除超过 60 秒的记录
            while self._timestamps and now - self._timestamps[0] > 60:
                self._timestamps.popleft()
            if len(self._timestamps) >= self._max:
                return False
            self._timestamps.append(now)
            return True


# ---------------------------------------------------------------------------
# Retry decorator
# ---------------------------------------------------------------------------

def _retry(max_retries: int = 3, backoff: float = 1.0):
    """失败重试装饰器（指数退避）。"""
    def decorator(fn):
        def wrapper(*args, **kwargs) -> bool:
            for attempt in range(1, max_retries + 1):
                try:
                    result = fn(*args, **kwargs)
                    if result:
                        return True
                except Exception as exc:
                    logger.warning(
                        "%s attempt %d/%d failed: %s",
                        fn.__qualname__, attempt, max_retries, exc,
                    )
                if attempt < max_retries:
                    time.sleep(backoff * (2 ** (attempt - 1)))
            logger.error("%s failed after %d retries", fn.__qualname__, max_retries)
            return False
        return wrapper
    return decorator


# ---------------------------------------------------------------------------
# Abstract base
# ---------------------------------------------------------------------------

class Notifier(ABC):
    """通知渠道抽象基类。"""

    @abstractmethod
    def send(self, title: str, body: str) -> bool:
        """发送通知。

        Args:
            title: 通知标题。
            body: 通知正文（支持 Markdown）。

        Returns:
            True 表示发送成功。
        """
        ...


# ---------------------------------------------------------------------------
# WeChat (Server酱 / PushPlus)
# ---------------------------------------------------------------------------

class WeChatNotifier(Notifier):
    """微信通知，支持 Server酱 和 PushPlus 两种服务商。"""

    _PROVIDERS = {
        "serverchan": "https://sctapi.ftqq.com/{token}.send",
        "pushplus": "https://www.pushplus.plus/send",
    }

    def __init__(self, provider: str = "serverchan", token: str = "") -> None:
        self._provider = provider.lower()
        self._token = token
        if self._provider not in self._PROVIDERS:
            raise ValueError(f"Unknown WeChat provider: {provider}")

    @_retry(max_retries=3, backoff=1.0)
    def send(self, title: str, body: str) -> bool:
        if not self._token:
            logger.warning("WeChat token not configured, skip sending")
            return False

        if self._provider == "serverchan":
            url = self._PROVIDERS["serverchan"].format(token=self._token)
            payload = urllib.parse.urlencode({"title": title, "desp": body}).encode()
        else:  # pushplus
            url = self._PROVIDERS["pushplus"]
            data = {"token": self._token, "title": title, "content": body, "template": "markdown"}
            payload = json.dumps(data).encode("utf-8")

        req = urllib.request.Request(url, data=payload, method="POST")
        if self._provider == "pushplus":
            req.add_header("Content-Type", "application/json")

        with urllib.request.urlopen(req, timeout=10) as resp:
            result = json.loads(resp.read().decode())
            # Server酱 code=0 成功，PushPlus code=200 成功
            success_codes = {0, 200}
            ok = result.get("code") in success_codes
            if not ok:
                logger.warning("WeChat send failed: %s", result)
            return ok


# ---------------------------------------------------------------------------
# DingTalk
# ---------------------------------------------------------------------------

class DingTalkNotifier(Notifier):
    """钉钉机器人通知（Webhook + 可选签名验证）。"""

    def __init__(self, webhook: str = "", secret: str = "") -> None:
        self._webhook = webhook
        self._secret = secret

    def _sign_url(self) -> str:
        """对 webhook URL 追加签名参数。"""
        if not self._secret:
            return self._webhook
        timestamp = str(int(time.time() * 1000))
        string_to_sign = f"{timestamp}\n{self._secret}"
        hmac_code = hmac.new(
            self._secret.encode("utf-8"),
            string_to_sign.encode("utf-8"),
            digestmod=hashlib.sha256,
        ).digest()
        sign = urllib.parse.quote_plus(base64.b64encode(hmac_code).decode())
        sep = "&" if "?" in self._webhook else "?"
        return f"{self._webhook}{sep}timestamp={timestamp}&sign={sign}"

    @_retry(max_retries=3, backoff=1.0)
    def send(self, title: str, body: str) -> bool:
        if not self._webhook:
            logger.warning("DingTalk webhook not configured, skip sending")
            return False

        url = self._sign_url()
        payload = json.dumps({
            "msgtype": "markdown",
            "markdown": {"title": title, "text": f"## {title}\n\n{body}"},
        }).encode("utf-8")

        req = urllib.request.Request(url, data=payload, method="POST")
        req.add_header("Content-Type", "application/json")

        with urllib.request.urlopen(req, timeout=10) as resp:
            result = json.loads(resp.read().decode())
            ok = result.get("errcode") == 0
            if not ok:
                logger.warning("DingTalk send failed: %s", result)
            return ok


# ---------------------------------------------------------------------------
# Email
# ---------------------------------------------------------------------------

class EmailNotifier(Notifier):
    """邮件通知（SMTP + TLS）。"""

    def __init__(
        self,
        smtp_server: str = "",
        smtp_port: int = 587,
        username: str = "",
        password: str = "",
        from_addr: str = "",
        to_addrs: list[str] | None = None,
        use_tls: bool = True,
    ) -> None:
        self._server = smtp_server
        self._port = smtp_port
        self._username = username
        self._password = password
        self._from = from_addr
        self._to = to_addrs or []
        self._tls = use_tls

    @_retry(max_retries=3, backoff=2.0)
    def send(self, title: str, body: str) -> bool:
        if not self._server or not self._to:
            logger.warning("Email not configured, skip sending")
            return False

        msg = MIMEText(body, "plain", "utf-8")
        msg["Subject"] = f"[JWQuant] {title}"
        msg["From"] = self._from
        msg["To"] = ", ".join(self._to)

        with smtplib.SMTP(self._server, self._port, timeout=15) as srv:
            if self._tls:
                srv.starttls()
            if self._username and self._password:
                srv.login(self._username, self._password)
            srv.sendmail(self._from, self._to, msg.as_string())
        return True


# ---------------------------------------------------------------------------
# Notification Router
# ---------------------------------------------------------------------------

class NotificationRouter:
    """通知路由器：按消息级别分发到不同渠道。"""

    def __init__(self) -> None:
        self._channels: dict[str, Notifier] = {}
        self._routing: dict[str, list[str]] = {}
        self._rate_limiter: RateLimiter | None = None
        self._initialized = False

    def _init_from_config(self) -> None:
        """从配置文件初始化渠道和路由规则。"""
        if self._initialized:
            return
        try:
            from jwquant.common import config

            # 速率限制
            if config.get_bool("notification.rate_limit_enabled", True):
                limit = config.get_int("notification.max_messages_per_minute", 10)
                self._rate_limiter = RateLimiter(limit)

            # 路由规则
            self._routing = {
                "INFO": config.get("notification.routing.INFO") or ["wechat"],
                "WARNING": config.get("notification.routing.WARNING") or ["wechat", "dingtalk"],
                "ERROR": config.get("notification.routing.ERROR") or ["wechat", "dingtalk", "email"],
                "CRITICAL": config.get("notification.routing.CRITICAL") or ["wechat", "dingtalk", "email"],
            }

            # 初始化各渠道
            enabled = config.get("notification.channels") or []

            if "wechat" in enabled:
                self._channels["wechat"] = WeChatNotifier(
                    provider=config.get_str("notification.wechat.provider", "serverchan"),
                    token=config.get_str("notification.wechat.token"),
                )

            if "dingtalk" in enabled:
                self._channels["dingtalk"] = DingTalkNotifier(
                    webhook=config.get_str("notification.dingtalk.webhook"),
                    secret=config.get_str("notification.dingtalk.secret"),
                )

            if "email" in enabled:
                self._channels["email"] = EmailNotifier(
                    smtp_server=config.get_str("notification.email.smtp_server"),
                    smtp_port=config.get_int("notification.email.smtp_port", 587),
                    username=config.get_str("notification.email.username"),
                    password=config.get_str("notification.email.password"),
                    from_addr=config.get_str("notification.email.from_addr"),
                    to_addrs=config.get("notification.email.to_addrs") or [],
                    use_tls=config.get_bool("notification.email.use_tls", True),
                )
        except Exception as exc:
            logger.error("Failed to initialize notification router: %s", exc)

        self._initialized = True

    def send(
        self, title: str, body: str, level: str = "INFO"
    ) -> dict[str, bool]:
        """按级别路由发送通知。

        Returns:
            各渠道发送结果 ``{"wechat": True, "dingtalk": False, ...}``。
        """
        self._init_from_config()

        if self._rate_limiter and not self._rate_limiter.allow():
            logger.warning("Notification rate limited, message dropped: %s", title)
            return {}

        results: dict[str, bool] = {}
        target_channels = self._routing.get(level.upper(), ["wechat"])

        for ch_name in target_channels:
            notifier = self._channels.get(ch_name)
            if notifier is None:
                continue
            try:
                results[ch_name] = notifier.send(title, body)
            except Exception as exc:
                logger.error("Channel %s send error: %s", ch_name, exc)
                results[ch_name] = False

        return results


# ---------------------------------------------------------------------------
# Module-level facade
# ---------------------------------------------------------------------------

_router: NotificationRouter | None = None
_router_lock = threading.Lock()


def send_notification(
    title: str,
    body: str,
    level: str = "INFO",
    template: str | None = None,
    **kwargs: Any,
) -> dict[str, bool]:
    """发送通知（模块级便捷函数）。

    Args:
        title: 通知标题。
        body: 通知正文。如果指定了 template，则 body 被忽略。
        level: 通知级别 ("INFO" / "WARNING" / "ERROR" / "CRITICAL")。
        template: 可选模板名称（如 "order_filled"）。
        **kwargs: 模板变量。

    Returns:
        各渠道发送结果。

    Example::

        send_notification("成交通知", template="order_filled",
                          code="600519.SH", direction="买入",
                          price=1850.00, volume=100,
                          timestamp="2026-02-11 10:30:00")
    """
    global _router

    # 检查通知是否启用
    try:
        from jwquant.common import config
        if not config.get_bool("notification.enabled", False):
            return {}
    except Exception:
        pass

    # 渲染模板
    if template:
        body = render_template(template, **kwargs)

    # 延迟初始化路由器
    with _router_lock:
        if _router is None:
            _router = NotificationRouter()

    return _router.send(title, body, level)
