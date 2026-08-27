import json

import pytest

from rhbt.data.rh_import import PayloadError, normalize_robinhood_payload

BARS = [
    {"begins_at": "2024-02-01T00:00:00Z", "open_price": "185.00", "close_price": "186.50",
     "high_price": "187.00", "low_price": "184.20", "volume": 51_000_000, "interpolated": False},
    {"begins_at": "2024-02-02T00:00:00Z", "open_price": "186.60", "close_price": "185.10",
     "high_price": "188.00", "low_price": "184.90", "volume": 47_000_000, "interpolated": False},
]


def test_robinhood_shape_with_symbol():
    frames = normalize_robinhood_payload({"results": [{"symbol": "AAPL", "historicals": BARS}]})
    assert list(frames) == ["AAPL"]
    frame = frames["AAPL"]
    assert len(frame) == 2
    assert frame["close"].iloc[0] == 186.50
    assert list(frame.columns) == ["open", "high", "low", "close", "volume"]


def test_bare_list_of_bars():
    frames = normalize_robinhood_payload(BARS)
    assert list(frames) == ["UNKNOWN"] and len(frames["UNKNOWN"]) == 2


def test_json_string_input():
    frames = normalize_robinhood_payload(json.dumps({"AAPL": BARS}))
    assert "AAPL" in frames


def test_several_symbols_in_one_payload():
    payload = {"results": [{"symbol": "AAPL", "historicals": BARS},
                           {"symbol": "MSFT", "historicals": BARS}]}
    assert sorted(normalize_robinhood_payload(payload)) == ["AAPL", "MSFT"]


def test_epoch_timestamps_are_understood():
    bars = [{"timestamp": 1706745600, "close": 100.0, "open": 99.0, "high": 101.0, "low": 98.0}]
    frame = normalize_robinhood_payload(bars)["UNKNOWN"]
    assert str(frame.index[0].date()) == "2024-02-01"


def test_missing_ohlc_falls_back_to_close():
    frame = normalize_robinhood_payload([{"date": "2024-02-01", "close_price": "100"}])["UNKNOWN"]
    assert frame["open"].iloc[0] == frame["close"].iloc[0] == 100.0


def test_duplicate_timestamps_keep_the_last():
    frame = normalize_robinhood_payload(BARS + [dict(BARS[0], close_price="999")])["UNKNOWN"]
    assert len(frame) == 2 and frame["close"].iloc[0] == 999.0


def test_garbage_raises_a_clear_error():
    with pytest.raises(PayloadError, match="not valid JSON"):
        normalize_robinhood_payload("nonsense")
    with pytest.raises(PayloadError, match="could not find"):
        normalize_robinhood_payload({"foo": "bar"})
