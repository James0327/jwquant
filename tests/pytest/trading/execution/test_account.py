from jwquant.trading.execution.account import (
    XtQuantAccountDiagnostics,
    print_account_diagnostics,
)


class FakeSession:
    """测试用会话对象。

    用途：
      - 避免依赖真实 XtQuant 运行时和真实账户；
      - 只验证公共打印函数是否按稳定顺序消费诊断结果。

    输入输出：
      - 输入：作为 print_account_diagnostics 的 session 参数传入；
      - 输出：无业务行为，仅用于断言 session 被原样传递。
    """

    class account_config:
        market = "futures"
        account_id = "test-account"
        account_type = "FUTURE"


def test_print_account_diagnostics_prints_sections_in_stable_order(monkeypatch):
    """公共打印函数必须按资产、持仓、成交、委托的顺序输出。

    关键逻辑：
      1. 用 monkeypatch 替换 build_account_diagnostics，隔离真实账户查询；
      2. 捕获 printer 收到的文本行；
      3. 断言输出顺序稳定，避免手工脚本各自维护重复循环。
    """
    printed: list[str] = []

    def fake_build_account_diagnostics(session, account_type=None):
        assert isinstance(session, FakeSession)
        assert account_type == "FUTURE"
        return XtQuantAccountDiagnostics(
            asset_lines=["asset"],
            position_lines=["position"],
            trade_lines=["trade"],
            order_lines=["order"],
        )

    monkeypatch.setattr(
        "jwquant.trading.execution.account.build_account_diagnostics",
        fake_build_account_diagnostics,
    )

    print_account_diagnostics(FakeSession(), account_type="FUTURE", printer=printed.append)

    assert printed == ["asset", "position", "trade", "order"]
