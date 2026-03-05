"""Generate a lightweight HTML report for IFVG signals using Plotly."""

from __future__ import annotations

from dataclasses import asdict
from datetime import datetime
from decimal import Decimal
from html import escape
from typing import Any

from charting.resampler import OhlcvBar
from indicators.ifvg import IfvgConfig, IfvgSignal


def build_ifvg_report_html(
    *,
    symbol: str,
    timeframe: str,
    candles: int,
    end_utc: datetime | None,
    config: IfvgConfig,
    bars: list[OhlcvBar],
    signals: list[IfvgSignal],
    title: str | None = None,
) -> str:
    """Return full HTML (single file) for IFVG report."""
    fig_html = _build_plotly_chart_html(
        symbol=symbol,
        timeframe=timeframe,
        bars=bars,
        signals=signals,
        title=title or f"IFVG report: {symbol} {timeframe}",
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
    <title>{escape(title or f"IFVG report: {symbol} {timeframe}")}</title>
    <style>
      body {{ font-family: ui-sans-serif, system-ui, -apple-system, Segoe UI, Roboto, Arial, sans-serif; margin: 16px; color: #111; }}
      .container {{ max-width: 1200px; margin: 0 auto; }}
      .meta {{ display: grid; grid-template-columns: 1fr; gap: 8px; margin-bottom: 12px; }}
      .meta pre {{ background: #f6f8fa; padding: 10px; border-radius: 8px; overflow: auto; }}
      table {{ border-collapse: collapse; width: 100%; margin-top: 16px; }}
      th, td {{ border: 1px solid #e5e7eb; padding: 8px; font-size: 13px; }}
      th {{ background: #f9fafb; text-align: left; }}
      .pill {{ display: inline-block; padding: 2px 8px; border-radius: 999px; font-size: 12px; }}
      .buy {{ background: rgba(16, 185, 129, 0.15); color: #065f46; }}
      .sell {{ background: rgba(239, 68, 68, 0.15); color: #7f1d1d; }}
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
    signals: list[IfvgSignal],
    title: str,
) -> str:
    if not bars:
        raise ValueError("no bars provided for plotting")

    import plotly.graph_objects as go

    x = [_fmt_ts(bar.timestamp_utc) for bar in bars]
    fig = go.Figure(
        data=[
            go.Candlestick(
                x=x,
                open=[float(bar.open) for bar in bars],
                high=[float(bar.high) for bar in bars],
                low=[float(bar.low) for bar in bars],
                close=[float(bar.close) for bar in bars],
                name=f"{symbol} {timeframe}",
            )
        ]
    )

    for s in signals:
        x0 = _fmt_ts(s.origin_fvg.formed_at)
        x1 = _fmt_ts(s.triggered_at)
        if s.side == "buy":
            fill = "rgba(16, 185, 129, 0.20)"
            line = "rgba(16, 185, 129, 0.65)"
            marker_color = "rgba(16, 185, 129, 0.95)"
            marker_symbol = "triangle-up"
        else:
            fill = "rgba(239, 68, 68, 0.20)"
            line = "rgba(239, 68, 68, 0.65)"
            marker_color = "rgba(239, 68, 68, 0.95)"
            marker_symbol = "triangle-down"

        fig.add_shape(
            type="rect",
            xref="x",
            yref="y",
            x0=x0,
            x1=x1,
            y0=float(s.origin_fvg.gap_low),
            y1=float(s.origin_fvg.gap_high),
            fillcolor=fill,
            line={"color": line, "width": 1},
            layer="below",
        )
        fig.add_trace(
            go.Scatter(
                x=[_fmt_ts(s.triggered_at)],
                y=[float(s.entry)],
                mode="markers",
                marker={"size": 11, "symbol": marker_symbol, "color": marker_color},
                name=f"ifvg {s.side}",
                showlegend=True,
            )
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
    config: IfvgConfig,
    total_signals: int,
) -> str:
    payload: dict[str, Any] = {
        "symbol": symbol,
        "timeframe": timeframe,
        "candles": candles,
        "end_utc": end_utc.isoformat() if end_utc else None,
        "ifvg_config": asdict(config),
        "signals": total_signals,
    }
    pretty = _json_like(payload)
    return f"""
      <div class="meta">
        <h2>IFVG report</h2>
        <pre>{escape(pretty)}</pre>
      </div>
    """


def _build_signals_table_html(signals: list[IfvgSignal]) -> str:
    headers = [
        "triggered_at",
        "side",
        "entry",
        "stop",
        "tp",
        "origin_fvg_direction",
        "origin_gap_low",
        "origin_gap_high",
        "reason",
    ]

    rows = []
    for s in signals:
        rows.append(
            {
                "triggered_at": s.triggered_at.isoformat(),
                "side": s.side,
                "entry": _fmt_decimal(s.entry),
                "stop": _fmt_decimal(s.stop),
                "tp": _fmt_decimal(s.tp),
                "origin_fvg_direction": s.origin_fvg.direction,
                "origin_gap_low": _fmt_decimal(s.origin_fvg.gap_low),
                "origin_gap_high": _fmt_decimal(s.origin_fvg.gap_high),
                "reason": ", ".join(s.reason),
            }
        )

    head_html = "".join(f"<th>{escape(h)}</th>" for h in headers)
    body_cells: list[str] = []
    for r in rows:
        side = r["side"]
        pill = f'<span class="pill {escape(side)}">{escape(side)}</span>'
        body_cells.append(
            "<tr>"
            + "".join(
                [
                    f"<td>{escape(r['triggered_at'])}</td>",
                    f"<td>{pill}</td>",
                    f"<td>{escape(r['entry'])}</td>",
                    f"<td>{escape(r['stop'])}</td>",
                    f"<td>{escape(r['tp'])}</td>",
                    f"<td>{escape(r['origin_fvg_direction'])}</td>",
                    f"<td>{escape(r['origin_gap_low'])}</td>",
                    f"<td>{escape(r['origin_gap_high'])}</td>",
                    f"<td>{escape(r['reason'])}</td>",
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
    return format(value.normalize(), "f")


def _fmt_ts(ts: datetime) -> str:
    return ts.strftime("%Y-%m-%d %H:%M")


def _json_like(payload: dict[str, Any]) -> str:
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
