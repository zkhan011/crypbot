from app.services.trading_platform import BingXLiveExchangeAdapter, MockScenario, StrategyName, TradingApplication


def test_mock_balance_and_dashboard_snapshot():
    app = TradingApplication()
    snapshot = app.dashboard_snapshot()
    assert snapshot["balance"]["asset"] == "USDT"
    assert "scenario_options" in snapshot
    assert "reports" in snapshot


def test_mock_volume_spike_opens_volume_signal():
    app = TradingApplication()
    snapshot = app.apply_scenario(MockScenario.BULLISH_VOLUME_BREAKOUT)
    assert any(signal["strategy"] == StrategyName.VOLUME.value for signal in snapshot["signals"])
    assert any(order["strategy"] == StrategyName.VOLUME.value for order in snapshot["orders"])


def test_mock_copy_signal_opens_order():
    app = TradingApplication()
    snapshot = app.apply_scenario(MockScenario.LEAD_TRADER_OPENS_LONG)
    assert any(signal["strategy"] == StrategyName.COPY.value for signal in snapshot["signals"])


def test_emergency_stop_closes_positions_and_blocks_live_disabled():
    app = TradingApplication()
    app.apply_scenario(MockScenario.LEAD_TRADER_OPENS_LONG)
    stopped = app.emergency_stop()
    assert stopped["bot_state"] == "EMERGENCY_STOPPED"
    assert stopped["open_positions"] == []
    try:
        BingXLiveExchangeAdapter(enable_live_trading=False)
    except RuntimeError as exc:
        assert "ENABLE_LIVE_TRADING=true" in str(exc)
    else:
        raise AssertionError("live adapter must be blocked by default")


def test_notification_preview_and_reports_exist():
    app = TradingApplication()
    snapshot = app.apply_scenario(MockScenario.ORDER_REJECTION)
    assert snapshot["notifications"]
    assert "daily_pnl_report" in snapshot["reports"]
