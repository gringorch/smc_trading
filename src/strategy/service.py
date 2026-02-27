"""Strategy analysis services."""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from charting.plot_overlays import apply_overlays
from charting.price_data_repository import PriceDataRepository
from charting.resampler import OhlcvBar, resample_ohlcv
from charting.timeframes import normalize_utc, parse_timeframe
from db.engine import session_scope
from strategy.context import build_fib_context, compute_market_state_1h
from strategy.events import Event, MarketState, StrategyConfig
from strategy.imbalance import detect_fvg, detect_ifvg
from strategy.structure import detect_bos_choch, detect_pivots, detect_sweeps


@dataclass(frozen=True)
class AnalysisResult:
    events: list[Event]
    bars: list[OhlcvBar]
    market_state: MarketState | None = None


def _bars_to_df(bars: list[OhlcvBar]) -> pd.DataFrame:
    frame = pd.DataFrame(
        {
            "timestamp_utc": [bar.timestamp_utc for bar in bars],
            "open": [float(bar.open) for bar in bars],
            "high": [float(bar.high) for bar in bars],
            "low": [float(bar.low) for bar in bars],
            "close": [float(bar.close) for bar in bars],
            "volume": [float(bar.volume) for bar in bars],
        }
    )
    return frame.set_index("timestamp_utc", drop=False)


def _compute_atr(df: pd.DataFrame, period: int = 14) -> pd.Series:
    high = df["high"]
    low = df["low"]
    prev_close = df["close"].shift(1)
    tr = pd.concat(
        [(high - low).abs(), (high - prev_close).abs(), (low - prev_close).abs()], axis=1
    ).max(axis=1)
    return tr.rolling(period, min_periods=1).mean()


def _load_bars(
    repository: PriceDataRepository, symbol: str, timeframe: str, candles: int
) -> list[OhlcvBar]:
    duration = parse_timeframe(timeframe)
    asset_id = repository.get_asset_id_by_symbol(symbol)
    if asset_id is None:
        raise ValueError(f"symbol '{symbol}' not found or inactive")
    end = repository.get_latest_1m_timestamp(asset_id)
    if end is None:
        raise ValueError(f"no persisted 1m candles for symbol '{symbol}'")

    end_utc = normalize_utc(end)
    start_utc = end_utc - (duration * candles * 3)
    rows = repository.load_1m_rows(asset_id=asset_id, start_utc=start_utc, end_utc=end_utc)
    if not rows:
        raise ValueError("no candles available")
    return resample_ohlcv(rows, timeframe)[-candles:]


def analyze(
    symbol: str, timeframe: str, candles: int, config: StrategyConfig | None = None
) -> AnalysisResult:
    cfg = config or StrategyConfig()
    with session_scope() as session:
        repository = PriceDataRepository(session)
        bars = _load_bars(repository, symbol, timeframe, candles)

    if not bars:
        raise ValueError("no bars available")

    df = _bars_to_df(bars)
    atr = _compute_atr(df)

    pivots = detect_pivots(df, L=cfg.config_htf.pivots_L)
    break_min = cfg.config_htf.min_break_atr.get(timeframe, 0.0)
    structure_events = detect_bos_choch(df, pivots, atr=atr, min_break_atr=break_min)
    sweep_events = detect_sweeps(
        df,
        pivots,
        atr=atr,
        min_sweep_wick_atr=cfg.config_htf.min_sweep_wick_atr,
        max_reclaim_distance_atr=cfg.config_htf.max_reclaim_distance_atr,
        confirm_within_bars=cfg.config_htf.confirm_within_bars,
    )
    fvg_min = cfg.config_htf.min_fvg_atr.get(
        timeframe, cfg.config_ltf.min_fvg_atr.get(timeframe, 0.0)
    )
    fvg_events = detect_fvg(df, atr=atr, min_fvg_atr=fvg_min)
    ifvg_events = detect_ifvg(df, fvg_events, confirm_mode=cfg.config_ltf.ifvg_confirm_mode)
    fib_events = build_fib_context(df, pivots, discount_threshold=cfg.config_htf.discount_threshold)

    events = [*pivots, *structure_events, *sweep_events, *fvg_events, *ifvg_events, *fib_events]
    return AnalysisResult(events=events, bars=bars)


def analyze_multi_tf(
    symbol: str,
    htf: str,
    ltf: str,
    candles_htf: int,
    candles_ltf: int,
    config: StrategyConfig | None = None,
) -> dict:
    htf_result = analyze(symbol, htf, candles_htf, config=config)
    ltf_result = analyze(symbol, ltf, candles_ltf, config=config)

    htf_pois = [
        e
        for e in htf_result.events
        if e.kind.value in {"FVG", "SWEEP_HIGH", "SWEEP_LOW", "FIB_DISCOUNT"}
    ]
    ltf_ifvg = [e for e in ltf_result.events if e.kind.value == "IFVG"]

    linked = []
    for ifvg in ltf_ifvg:
        for poi in htf_pois:
            if ifvg.price_low is None or ifvg.price_high is None:
                continue
            poi_low = poi.price_low if poi.price_low is not None else poi.price
            poi_high = poi.price_high if poi.price_high is not None else poi.price
            if poi_low is None or poi_high is None:
                continue
            overlaps = not (ifvg.price_high < poi_low or ifvg.price_low > poi_high)
            if overlaps:
                linked.append({"ifvg": ifvg, "poi": poi})
                break

    return {
        "htf": htf,
        "ltf": ltf,
        "htf_events": htf_result.events,
        "ltf_events": ltf_result.events,
        "linked_events": linked,
        "counts": {
            "htf": len(htf_result.events),
            "ltf": len(ltf_result.events),
            "linked": len(linked),
        },
    }


def analyze_adaptive(
    symbol: str,
    htf_list: list[str] | None = None,
    ltf_default: str = "3m",
    ltf_trend: str = "1m",
    config: StrategyConfig | None = None,
) -> dict:
    htf_list = htf_list or ["15m", "1h", "4h"]
    if "1h" not in htf_list:
        raise ValueError("htf_list must include 1h")

    htf_results = {tf: analyze(symbol, tf, 250, config=config) for tf in htf_list}
    events_1h = [e for e in htf_results["1h"].events if e.kind.value in {"BOS", "CHOCH"}]
    market_state = compute_market_state_1h(events_1h)

    selected_ltf = ltf_trend if market_state.value in {"TREND_BULL", "TREND_BEAR"} else ltf_default
    report = analyze_multi_tf(symbol, "1h", selected_ltf, 250, 250, config=config)
    report["market_state"] = market_state.value
    report["selected_ltf"] = selected_ltf
    return report


def render_analysis_chart(
    result: AnalysisResult, *, symbol: str, timeframe: str, save_path: str | None = None
) -> None:
    import mplfinance as mpf

    df = _bars_to_df(result.bars)
    plot_df = df.rename(
        columns={"open": "Open", "high": "High", "low": "Low", "close": "Close", "volume": "Volume"}
    )[["Open", "High", "Low", "Close", "Volume"]]
    fig, axes = mpf.plot(
        plot_df,
        type="candle",
        style="yahoo",
        title=f"{symbol} {timeframe}",
        volume=False,
        returnfig=True,
        show_nontrading=False,
        datetime_format="%Y-%m-%d %H:%M",
    )
    ax = axes[0]
    apply_overlays(ax, result.events, plot_df)

    if save_path:
        fig.savefig(save_path)
