"""Candlestick chart rendering using mplfinance."""

from __future__ import annotations

from decimal import Decimal

from charting.resampler import OhlcvBar


def _decimal_to_float(value: Decimal) -> float:
    return float(value)


def render_price_chart(
    *,
    symbol: str,
    timeframe: str,
    bars: list[OhlcvBar],
    include_volume: bool,
    show: bool,
    save_path: str | None,
) -> None:
    """Render a candlestick chart with optional volume."""
    if not bars:
        raise ValueError("no bars available to plot")

    import matplotlib.pyplot as plt
    import mplfinance as mpf
    import pandas as pd

    frame = pd.DataFrame(
        {
            "Date": [bar.timestamp_utc for bar in bars],
            "Open": [_decimal_to_float(bar.open) for bar in bars],
            "High": [_decimal_to_float(bar.high) for bar in bars],
            "Low": [_decimal_to_float(bar.low) for bar in bars],
            "Close": [_decimal_to_float(bar.close) for bar in bars],
            "Volume": [_decimal_to_float(bar.volume) for bar in bars],
        }
    )
    frame = frame.set_index("Date")

    kwargs: dict[str, object] = {
        "type": "candle",
        "style": "yahoo",
        "title": f"{symbol} {timeframe}",
        "ylabel": "Price",
        "volume": include_volume,
        "show_nontrading": False,
        "datetime_format": "%Y-%m-%d %H:%M",
    }

    if show:
        if save_path:
            kwargs["savefig"] = save_path
        mpf.plot(frame, **kwargs)
        return

    kwargs["returnfig"] = True
    fig, _ = mpf.plot(frame, **kwargs)
    if save_path:
        fig.savefig(save_path)
    plt.close(fig)
