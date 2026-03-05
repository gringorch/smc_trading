"""Generate a lightweight HTML report for market structure using Plotly."""

from __future__ import annotations

from dataclasses import asdict
from datetime import datetime
from decimal import Decimal
from html import escape
from typing import Any

from charting.resampler import OhlcvBar
from indicators.structure import BosEvent, StructureConfig, StructureState, SwingPoint


def build_structure_report_html(
    *,
    symbol: str,
    timeframe: str,
    candles: int,
    end_utc: datetime | None,
    config: StructureConfig,
    bars: list[OhlcvBar],
    swings: list[SwingPoint],
    bos_events: list[BosEvent],
    state: StructureState,
    title: str | None = None,
) -> str:
    """Return full HTML (single file) for market structure report."""
    fig_html = _build_plotly_chart_html(
        symbol=symbol,
        timeframe=timeframe,
        bars=bars,
        swings=swings,
        bos_events=bos_events,
        state=state,
        title=title or f"Structure report: {symbol} {timeframe}",
    )
    params_html = _build_params_block_html(
        symbol=symbol,
        timeframe=timeframe,
        candles=candles,
        end_utc=end_utc,
        config=config,
        swings_total=len(swings),
        bos_total=len(bos_events),
        state=state,
    )
    swings_table = _build_swings_table_html(swings)
    bos_table = _build_bos_table_html(bos_events)

    return f"""<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width,initial-scale=1" />
    <title>{escape(title or f"Structure report: {symbol} {timeframe}")}</title>
    <style>
      body {{ font-family: ui-sans-serif, system-ui, -apple-system, Segoe UI, Roboto, Arial, sans-serif;
              margin: 16px; color: #111; }}
      .container {{ max-width: 1200px; margin: 0 auto; }}
      .meta {{ display: grid; grid-template-columns: 1fr; gap: 8px; margin-bottom: 12px; }}
      .meta pre {{ background: #f6f8fa; padding: 10px; border-radius: 8px; overflow: auto; }}
      table {{ border-collapse: collapse; width: 100%; margin-top: 16px; }}
      th, td {{ border: 1px solid #e5e7eb; padding: 8px; font-size: 13px; }}
      th {{ background: #f9fafb; text-align: left; }}
      .pill {{ display: inline-block; padding: 2px 8px; border-radius: 999px; font-size: 12px; }}
      .bull, .high {{ background: rgba(16, 185, 129, 0.15); color: #065f46; }}
      .bear, .low {{ background: rgba(239, 68, 68, 0.15); color: #7f1d1d; }}
      .neutral {{ background: rgba(107, 114, 128, 0.15); color: #374151; }}
    </style>
  </head>
  <body>
    <div class="container">
      {params_html}
      {fig_html}
      {swings_table}
      {bos_table}
    </div>
  </body>
</html>
"""


def _build_plotly_chart_html(
    *,
    symbol: str,
    timeframe: str,
    bars: list[OhlcvBar],
    swings: list[SwingPoint],
    bos_events: list[BosEvent],
    state: StructureState,
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

    high_x = [_fmt_ts(sw.timestamp_utc) for sw in swings if sw.kind == "high"]
    high_y = [float(sw.price) for sw in swings if sw.kind == "high"]
    low_x = [_fmt_ts(sw.timestamp_utc) for sw in swings if sw.kind == "low"]
    low_y = [float(sw.price) for sw in swings if sw.kind == "low"]
    unconfirmed_x = [_fmt_ts(sw.timestamp_utc) for sw in swings if not sw.confirmed]
    unconfirmed_y = [float(sw.price) for sw in swings if not sw.confirmed]

    if high_x:
        fig.add_trace(
            go.Scatter(
                x=high_x,
                y=high_y,
                mode="markers",
                marker={"size": 10, "symbol": "triangle-down", "color": "rgba(16, 185, 129, 0.95)"},
                name="swing high",
            )
        )
    if low_x:
        fig.add_trace(
            go.Scatter(
                x=low_x,
                y=low_y,
                mode="markers",
                marker={"size": 10, "symbol": "triangle-up", "color": "rgba(239, 68, 68, 0.95)"},
                name="swing low",
            )
        )
    if unconfirmed_x:
        fig.add_trace(
            go.Scatter(
                x=unconfirmed_x,
                y=unconfirmed_y,
                mode="markers",
                marker={"size": 11, "symbol": "circle-open", "color": "rgba(59, 130, 246, 0.95)"},
                name="unconfirmed swing",
            )
        )

    for event in bos_events:
        x0 = x[event.bar_index]
        color = "rgba(16, 185, 129, 0.9)" if event.side == "bull" else "rgba(239, 68, 68, 0.9)"
        symbol_name = "arrow-up" if event.side == "bull" else "arrow-down"
        if 0 <= event.broken_swing_index < len(swings):
            broken = swings[event.broken_swing_index]
            fig.add_shape(
                type="line",
                xref="x",
                yref="y",
                x0=_fmt_ts(broken.timestamp_utc),
                x1=x0,
                y0=float(broken.price),
                y1=float(broken.price),
                line={"color": color, "width": 1, "dash": "dot"},
            )
        fig.add_trace(
            go.Scatter(
                x=[x0],
                y=[float(event.close)],
                mode="markers+text",
                marker={"size": 12, "symbol": symbol_name, "color": color},
                text=[f"BOS {event.side}"],
                textposition="top center",
                name=f"bos {event.side}",
                showlegend=True,
            )
        )

    dr = state.current_dealing_range
    if dr is not None:
        from_bos = bos_events[dr.derived_from_bos]
        x0 = _fmt_ts(from_bos.triggered_at)
        x1 = _fmt_ts(bars[-1].timestamp_utc)
        fig.add_shape(
            type="rect",
            xref="x",
            yref="y",
            x0=x0,
            x1=x1,
            y0=float(dr.low),
            y1=float(dr.high),
            fillcolor="rgba(59, 130, 246, 0.12)",
            line={"color": "rgba(59, 130, 246, 0.65)", "width": 1},
            layer="below",
        )
        fig.add_shape(
            type="line",
            xref="x",
            yref="y",
            x0=x0,
            x1=x1,
            y0=float(dr.mid),
            y1=float(dr.mid),
            line={"color": "rgba(37, 99, 235, 0.8)", "width": 1, "dash": "dash"},
        )
        fig.add_annotation(
            x=x1,
            y=float(dr.high),
            text=f"DR.high ({escape(dr.high_source)})",
            showarrow=False,
            xanchor="right",
            yanchor="bottom",
        )
        fig.add_annotation(
            x=x1,
            y=float(dr.low),
            text=f"DR.low ({escape(dr.low_source)})",
            showarrow=False,
            xanchor="right",
            yanchor="top",
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
        height=700,
    )
    return fig.to_html(full_html=False, include_plotlyjs="cdn")


def _build_params_block_html(
    *,
    symbol: str,
    timeframe: str,
    candles: int,
    end_utc: datetime | None,
    config: StructureConfig,
    swings_total: int,
    bos_total: int,
    state: StructureState,
) -> str:
    dealing_range = None
    if state.current_dealing_range is not None:
        dealing_range = {
            "low": _fmt_decimal(state.current_dealing_range.low),
            "high": _fmt_decimal(state.current_dealing_range.high),
            "mid": _fmt_decimal(state.current_dealing_range.mid),
            "discount_zone": (
                _fmt_decimal(state.current_dealing_range.discount_zone[0]),
                _fmt_decimal(state.current_dealing_range.discount_zone[1]),
            ),
            "premium_zone": (
                _fmt_decimal(state.current_dealing_range.premium_zone[0]),
                _fmt_decimal(state.current_dealing_range.premium_zone[1]),
            ),
            "low_source": state.current_dealing_range.low_source,
            "high_source": state.current_dealing_range.high_source,
        }

    payload: dict[str, Any] = {
        "symbol": symbol,
        "timeframe": timeframe,
        "candles": candles,
        "end_utc": end_utc.isoformat() if end_utc else None,
        "structure_config": asdict(config),
        "swings": swings_total,
        "bos_events": bos_total,
        "current_bias": state.current_bias,
        "current_bias_since": (
            state.current_bias_since.isoformat() if state.current_bias_since else None
        ),
        "current_dealing_range": dealing_range,
        "reason": state.reason,
    }
    pretty = _json_like(payload)
    bias_pill = (
        f'<span class="pill {escape(state.current_bias)}">{escape(state.current_bias)}</span>'
    )
    return f"""
      <div class="meta">
        <h2>Market structure report</h2>
        <div>Current bias: {bias_pill}</div>
        <pre>{escape(pretty)}</pre>
      </div>
    """


def _build_swings_table_html(swings: list[SwingPoint]) -> str:
    headers = ["timestamp_utc", "kind", "price", "bar_index", "left", "right", "confirmed"]
    rows: list[str] = []
    for sw in swings:
        kind_pill = f'<span class="pill {escape(sw.kind)}">{escape(sw.kind)}</span>'
        rows.append(
            "<tr>"
            + f"<td>{escape(sw.timestamp_utc.isoformat())}</td>"
            + f"<td>{kind_pill}</td>"
            + f"<td>{escape(_fmt_decimal(sw.price))}</td>"
            + f"<td>{sw.bar_index}</td>"
            + f"<td>{sw.left}</td>"
            + f"<td>{sw.right}</td>"
            + f"<td>{str(sw.confirmed).lower()}</td>"
            + "</tr>"
        )

    head_html = "".join(f"<th>{escape(h)}</th>" for h in headers)
    body_html = "\n".join(rows) if rows else "<tr><td colspan='7'>(no swings)</td></tr>"
    return f"""
      <h3>Swings</h3>
      <table>
        <thead><tr>{head_html}</tr></thead>
        <tbody>
          {body_html}
        </tbody>
      </table>
    """


def _build_bos_table_html(events: list[BosEvent]) -> str:
    headers = ["triggered_at", "side", "bar_index", "broken_swing_index", "close", "buffer"]
    rows: list[str] = []
    for event in events:
        side_pill = f'<span class="pill {escape(event.side)}">{escape(event.side)}</span>'
        rows.append(
            "<tr>"
            + f"<td>{escape(event.triggered_at.isoformat())}</td>"
            + f"<td>{side_pill}</td>"
            + f"<td>{event.bar_index}</td>"
            + f"<td>{event.broken_swing_index}</td>"
            + f"<td>{escape(_fmt_decimal(event.close))}</td>"
            + f"<td>{escape(_fmt_decimal(event.buffer))}</td>"
            + "</tr>"
        )

    head_html = "".join(f"<th>{escape(h)}</th>" for h in headers)
    body_html = "\n".join(rows) if rows else "<tr><td colspan='6'>(no bos events)</td></tr>"
    return f"""
      <h3>BOS events</h3>
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
        lines.append(f'  "{k}": {v!r},')
    lines.append("}")
    return "\n".join(lines)
