"""Generate a lightweight HTML report for FVG signals using Plotly."""

from __future__ import annotations

from dataclasses import asdict
from datetime import datetime
from decimal import Decimal
from html import escape
from typing import Any

from charting.resampler import OhlcvBar
from indicators.fvg import FvgConfig, FvgSignal


def build_fvg_report_html(
    *,
    symbol: str,
    timeframe: str,
    candles: int,
    end_utc: datetime | None,
    config: FvgConfig,
    bars: list[OhlcvBar],
    signals: list[FvgSignal],
    title: str | None = None,
) -> str:
    """Return full HTML (single file) for the report.

    Uses Plotly with CDN JS to keep the HTML lightweight (requires internet when opening).
    """
    fig_html = _build_plotly_chart_html(
        symbol=symbol,
        timeframe=timeframe,
        bars=bars,
        signals=signals,
        title=title or f"FVG report: {symbol} {timeframe}",
    )

    params_html = _build_params_block_html(
        symbol=symbol,
        timeframe=timeframe,
        candles=candles,
        end_utc=end_utc,
        config=config,
        total_signals=len(signals),
    )
    table_html = _build_signals_table_html(signals)

    return f"""<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width,initial-scale=1" />
    <title>{escape(title or f"FVG report: {symbol} {timeframe}")}</title>
    <style>
      body {{ font-family: ui-sans-serif, system-ui, -apple-system, Segoe UI, Roboto, Arial, sans-serif; margin: 16px; color: #111; }}
      .container {{ max-width: 1200px; margin: 0 auto; }}
      .meta {{ display: grid; grid-template-columns: 1fr; gap: 8px; margin-bottom: 12px; }}
      .meta pre {{ background: #f6f8fa; padding: 10px; border-radius: 8px; overflow: auto; }}
      table {{ border-collapse: collapse; width: 100%; margin-top: 16px; }}
      th, td {{ border: 1px solid #e5e7eb; padding: 8px; font-size: 13px; }}
      th {{ background: #f9fafb; text-align: left; }}
      .pill {{ display: inline-block; padding: 2px 8px; border-radius: 999px; font-size: 12px; }}
      .bull {{ background: rgba(16, 185, 129, 0.15); color: #065f46; }}
      .bear {{ background: rgba(239, 68, 68, 0.15); color: #7f1d1d; }}
    </style>
  </head>
  <body>
    <div class="container">
      {params_html}
      {fig_html}
      {table_html}
    </div>
  </body>
</html>
"""


def _build_plotly_chart_html(
    *,
    symbol: str,
    timeframe: str,
    bars: list[OhlcvBar],
    signals: list[FvgSignal],
    title: str,
) -> str:
    if not bars:
        raise ValueError("no bars provided for plotting")

    import plotly.graph_objects as go

    # Use a categorical x-axis to avoid blank gaps for non-trading periods (e.g., weekends).
    # This keeps candles visually contiguous while preserving order.
    x = [_fmt_ts(bar.timestamp_utc) for bar in bars]
    opens = [float(bar.open) for bar in bars]
    highs = [float(bar.high) for bar in bars]
    lows = [float(bar.low) for bar in bars]
    closes = [float(bar.close) for bar in bars]

    fig = go.Figure(
        data=[
            go.Candlestick(
                x=x,
                open=opens,
                high=highs,
                low=lows,
                close=closes,
                name=f"{symbol} {timeframe}",
            )
        ]
    )

    last_ts = _fmt_ts(bars[-1].timestamp_utc)
    for s in signals:
        x0 = _fmt_ts(s.formed_at)
        x1 = _fmt_ts(s.mitigation.mitigated_at) if s.mitigation.mitigated_at else last_ts

        if s.direction == "bull":
            fill = "rgba(16, 185, 129, 0.20)"
            line = "rgba(16, 185, 129, 0.65)"
        else:
            fill = "rgba(239, 68, 68, 0.20)"
            line = "rgba(239, 68, 68, 0.65)"

        fig.add_shape(
            type="rect",
            xref="x",
            yref="y",
            x0=x0,
            x1=x1,
            y0=float(s.gap_low),
            y1=float(s.gap_high),
            fillcolor=fill,
            line={"color": line, "width": 1},
            layer="below",
        )

    fig.update_layout(
        title=title,
        xaxis_title="Time (UTC)",
        yaxis_title="Price",
        xaxis_rangeslider_visible=False,
        xaxis={
            "type": "category",
            "categoryorder": "array",
            "categoryarray": x,
        },
        template="plotly_white",
        margin={"l": 40, "r": 20, "t": 60, "b": 40},
        height=650,
    )

    return fig.to_html(full_html=False, include_plotlyjs="cdn")


def _build_params_block_html(
    *,
    symbol: str,
    timeframe: str,
    candles: int,
    end_utc: datetime | None,
    config: FvgConfig,
    total_signals: int,
) -> str:
    payload: dict[str, Any] = {
        "symbol": symbol,
        "timeframe": timeframe,
        "candles": candles,
        "end_utc": end_utc.isoformat() if end_utc else None,
        "fvg_config": asdict(config),
        "signals": total_signals,
    }
    pretty = _json_like(payload)
    return f"""
      <div class="meta">
        <h2>FVG report</h2>
        <pre>{escape(pretty)}</pre>
      </div>
    """


def _build_signals_table_html(signals: list[FvgSignal]) -> str:
    headers = [
        "formed_at",
        "direction",
        "gap_low",
        "gap_high",
        "gap_size",
        "mitigated",
        "mitigated_at",
        "index_start",
        "index_end",
    ]

    rows = []
    for s in signals:
        rows.append(
            {
                "formed_at": s.formed_at.isoformat(),
                "direction": s.direction,
                "gap_low": _fmt_decimal(s.gap_low),
                "gap_high": _fmt_decimal(s.gap_high),
                "gap_size": _fmt_decimal(s.gap_size),
                "mitigated": str(s.mitigation.mitigated).lower(),
                "mitigated_at": s.mitigation.mitigated_at.isoformat() if s.mitigation.mitigated_at else "",
                "index_start": str(s.index_start),
                "index_end": str(s.index_end),
            }
        )

    head_html = "".join(f"<th>{escape(h)}</th>" for h in headers)
    body_cells: list[str] = []
    for r in rows:
        direction = r["direction"]
        pill = f'<span class="pill {escape(direction)}">{escape(direction)}</span>'
        body_cells.append(
            "<tr>"
            + "".join(
                [
                    f"<td>{escape(r['formed_at'])}</td>",
                    f"<td>{pill}</td>",
                    f"<td>{escape(r['gap_low'])}</td>",
                    f"<td>{escape(r['gap_high'])}</td>",
                    f"<td>{escape(r['gap_size'])}</td>",
                    f"<td>{escape(r['mitigated'])}</td>",
                    f"<td>{escape(r['mitigated_at'])}</td>",
                    f"<td>{escape(r['index_start'])}</td>",
                    f"<td>{escape(r['index_end'])}</td>",
                ]
            )
            + "</tr>"
        )

    body_html = "\n".join(body_cells) if body_cells else "<tr><td colspan='9'>(no signals)</td></tr>"
    return f"""
      <h3>Signals</h3>
      <table>
        <thead><tr>{head_html}</tr></thead>
        <tbody>
          {body_html}
        </tbody>
      </table>
    """


def _fmt_decimal(value: Decimal) -> str:
    # Keep stable, human-friendly formatting for reports.
    return format(value.normalize(), "f")


def _fmt_ts(ts: datetime) -> str:
    # Keep a stable label for categorical x-axis and hover display.
    # Report assumes input timestamps are UTC-aware already.
    return ts.strftime("%Y-%m-%d %H:%M")


def _json_like(payload: dict[str, Any]) -> str:
    # Small helper to keep the report deterministic and dependency-free.
    lines: list[str] = ["{"]
    for k, v in payload.items():
        if isinstance(v, dict):
            lines.append(f'  "{k}": {{')
            for kk, vv in v.items():
                lines.append(f'    "{kk}": {vv!r},')
            lines.append("  },")
        else:
            lines.append(f'  "{k}": {v!r},')
    lines.append("}")
    return "\n".join(lines)
