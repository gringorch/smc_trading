"""Generate a lightweight HTML report for HTF POI detection."""

from __future__ import annotations

from dataclasses import asdict
from datetime import datetime
from decimal import Decimal
from html import escape
from typing import Any

from charting.resampler import OhlcvBar
from indicators.htf_poi import HtfPoiCandidate, HtfPoiConfig, HtfPoiContext


def build_htf_poi_report_html(
    *,
    symbol: str,
    timeframe: str,
    candles: int,
    end_utc: datetime | None,
    config: HtfPoiConfig,
    bars: list[OhlcvBar],
    context: HtfPoiContext,
    title: str | None = None,
) -> str:
    fig_html = _build_plotly_chart_html(
        symbol=symbol,
        timeframe=timeframe,
        bars=bars,
        context=context,
        title=title or f"HTF POI report: {symbol} {timeframe}",
    )
    params_html = _build_params_block_html(
        symbol=symbol,
        timeframe=timeframe,
        candles=candles,
        end_utc=end_utc,
        config=config,
        context=context,
    )
    pois_table = _build_poi_table_html(context.poi_candidates)

    return f"""<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width,initial-scale=1" />
    <title>{escape(title or f"HTF POI report: {symbol} {timeframe}")}</title>
    <style>
      body {{ font-family: ui-sans-serif, system-ui, -apple-system, Segoe UI, Roboto, Arial, sans-serif;
              margin: 16px; color: #111; }}
      .container {{ max-width: 1200px; margin: 0 auto; }}
      .meta {{ display: grid; grid-template-columns: 1fr; gap: 8px; margin-bottom: 12px; }}
      .meta pre {{ background: #f6f8fa; padding: 10px; border-radius: 8px; overflow: auto; }}
      table {{ border-collapse: collapse; width: 100%; margin-top: 16px; }}
      th, td {{ border: 1px solid #e5e7eb; padding: 8px; font-size: 13px; vertical-align: top; }}
      th {{ background: #f9fafb; text-align: left; }}
      .pill {{ display: inline-block; padding: 2px 8px; border-radius: 999px; font-size: 12px; }}
      .buy {{ background: rgba(16, 185, 129, 0.15); color: #065f46; }}
      .sell {{ background: rgba(239, 68, 68, 0.15); color: #7f1d1d; }}
      .active {{ background: rgba(59, 130, 246, 0.15); color: #1e3a8a; }}
      .pending {{ background: rgba(107, 114, 128, 0.15); color: #374151; }}
      .invalidated {{ background: rgba(245, 158, 11, 0.15); color: #92400e; }}
      .bull {{ background: rgba(16, 185, 129, 0.15); color: #065f46; }}
      .bear {{ background: rgba(239, 68, 68, 0.15); color: #7f1d1d; }}
      .neutral {{ background: rgba(107, 114, 128, 0.15); color: #374151; }}
    </style>
  </head>
  <body>
    <div class="container">
      {params_html}
      {fig_html}
      {pois_table}
    </div>
  </body>
</html>
"""


def _build_plotly_chart_html(
    *,
    symbol: str,
    timeframe: str,
    bars: list[OhlcvBar],
    context: HtfPoiContext,
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

    dr = context.dealing_range
    if dr is not None:
        x0 = x[0]
        x1 = x[-1]
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
            y=float(dr.mid),
            text="DR mid",
            showarrow=False,
            xanchor="right",
            yanchor="bottom",
        )

    first_ts = bars[0].timestamp_utc
    last_ts = bars[-1].timestamp_utc

    for idx, poi in enumerate(context.poi_candidates):
        color = "rgba(16, 185, 129, 0.20)" if poi.side == "buy" else "rgba(239, 68, 68, 0.20)"
        border = "rgba(16, 185, 129, 0.9)" if poi.side == "buy" else "rgba(239, 68, 68, 0.9)"
        if poi.status == "invalidated":
            color = "rgba(245, 158, 11, 0.20)"
            border = "rgba(245, 158, 11, 0.9)"

        start_ts = max(poi.fvg_formed_at, first_ts)
        end_ts = poi.invalidated_at or poi.expires_at or last_ts
        end_ts = min(end_ts, last_ts)
        if end_ts < start_ts:
            end_ts = start_ts

        x0 = _fmt_ts(start_ts)
        x1 = _fmt_ts(end_ts)
        label_y = float(poi.poi_high)

        if poi.activated_at is not None:
            activation_ts = min(max(poi.activated_at, start_ts), end_ts)
            xa = _fmt_ts(activation_ts)

            # Pending phase keeps original FVG width until activation.
            if activation_ts > start_ts:
                fig.add_shape(
                    type="rect",
                    xref="x",
                    yref="y",
                    x0=x0,
                    x1=xa,
                    y0=float(poi.poi_low),
                    y1=float(poi.poi_high),
                    fillcolor="rgba(107, 114, 128, 0.14)",
                    line={"color": "rgba(107, 114, 128, 0.6)", "width": 1},
                    layer="below",
                )

            # Active phase can expand width dynamically.
            fig.add_shape(
                type="rect",
                xref="x",
                yref="y",
                x0=xa,
                x1=x1,
                y0=float(poi.dynamic_poi_low),
                y1=float(poi.dynamic_poi_high),
                fillcolor=color,
                line={"color": border, "width": 1},
                layer="below",
            )
            label_y = float(poi.dynamic_poi_high)
        else:
            fig.add_shape(
                type="rect",
                xref="x",
                yref="y",
                x0=x0,
                x1=x1,
                y0=float(poi.poi_low),
                y1=float(poi.poi_high),
                fillcolor=color,
                line={"color": border, "width": 1},
                layer="below",
            )

        expiry_label = (
            _fmt_ts(poi.expires_at) if poi.expires_at is not None else "no_expiry"
        )
        fig.add_annotation(
            x=x1,
            y=label_y,
            text=f"POI#{idx + 1} {poi.side} {poi.status} exp:{expiry_label}",
            showarrow=False,
            xanchor="right",
            yanchor="bottom",
            bgcolor="rgba(255,255,255,0.8)",
        )

        if poi.activated_at is not None:
            fig.add_trace(
                go.Scatter(
                    x=[_fmt_ts(poi.activated_at)],
                    y=[label_y],
                    mode="markers+text",
                    marker={"size": 9, "symbol": "diamond", "color": border},
                    text=["ACT"],
                    textposition="top center",
                    name="poi activation",
                    showlegend=False,
                )
            )
        if poi.invalidated_at is not None:
            fig.add_trace(
                go.Scatter(
                    x=[_fmt_ts(poi.invalidated_at)],
                    y=[float(poi.dynamic_poi_low)],
                    mode="markers+text",
                    marker={"size": 9, "symbol": "x", "color": "rgba(245, 158, 11, 0.95)"},
                    text=["INV"],
                    textposition="bottom center",
                    name="poi invalidation",
                    showlegend=False,
                )
            )
        elif poi.expires_at is not None and poi.status == "invalidated":
            fig.add_trace(
                go.Scatter(
                    x=[_fmt_ts(poi.expires_at)],
                    y=[float(poi.dynamic_poi_low)],
                    mode="markers+text",
                    marker={"size": 9, "symbol": "square", "color": "rgba(37, 99, 235, 0.95)"},
                    text=["EXP"],
                    textposition="bottom center",
                    name="poi expiration",
                    showlegend=False,
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
        height=700,
    )
    return fig.to_html(full_html=False, include_plotlyjs="cdn")


def _build_params_block_html(
    *,
    symbol: str,
    timeframe: str,
    candles: int,
    end_utc: datetime | None,
    config: HtfPoiConfig,
    context: HtfPoiContext,
) -> str:
    active = None
    if context.active_poi is not None:
        active = {
            "side": context.active_poi.side,
            "status": context.active_poi.status,
            "poi_low": _fmt_decimal(context.active_poi.poi_low),
            "poi_high": _fmt_decimal(context.active_poi.poi_high),
            "activated_at": (
                context.active_poi.activated_at.isoformat()
                if context.active_poi.activated_at
                else None
            ),
            "expires_at": (
                context.active_poi.expires_at.isoformat()
                if context.active_poi.expires_at
                else None
            ),
        }

    payload: dict[str, Any] = {
        "symbol": symbol,
        "timeframe": timeframe,
        "candles": candles,
        "end_utc": end_utc.isoformat() if end_utc else None,
        "htf_poi_config": asdict(config),
        "current_bias": context.current_bias,
        "pois": len(context.poi_candidates),
        "active_poi": active,
    }
    pretty = _json_like(payload)
    bias_pill = (
        f'<span class="pill {escape(context.current_bias)}">{escape(context.current_bias)}</span>'
    )
    return f"""
      <div class="meta">
        <h2>HTF POI report</h2>
        <div>Current bias: {bias_pill}</div>
        <pre>{escape(pretty)}</pre>
      </div>
    """


def _build_poi_table_html(candidates: list[HtfPoiCandidate]) -> str:
    headers = [
        "fvg_formed_at",
        "side",
        "status",
        "poi_low",
        "poi_high",
        "dynamic_poi_low",
        "dynamic_poi_high",
        "context",
        "activated_at",
        "expires_at",
        "invalidated_at",
        "activation_reason",
        "expiration_reason",
    ]
    rows: list[str] = []
    for poi in candidates:
        side_pill = f'<span class="pill {escape(poi.side)}">{escape(poi.side)}</span>'
        status_pill = f'<span class="pill {escape(poi.status)}">{escape(poi.status)}</span>'
        rows.append(
            "<tr>"
            + f"<td>{escape(poi.fvg_formed_at.isoformat())}</td>"
            + f"<td>{side_pill}</td>"
            + f"<td>{status_pill}</td>"
            + f"<td>{escape(_fmt_decimal(poi.poi_low))}</td>"
            + f"<td>{escape(_fmt_decimal(poi.poi_high))}</td>"
            + f"<td>{escape(_fmt_decimal(poi.dynamic_poi_low))}</td>"
            + f"<td>{escape(_fmt_decimal(poi.dynamic_poi_high))}</td>"
            + f"<td>{escape(poi.discount_premium_context)}</td>"
            + f"<td>{escape(_fmt_ts_or_dash(poi.activated_at))}</td>"
            + f"<td>{escape(_fmt_ts_or_dash(poi.expires_at))}</td>"
            + f"<td>{escape(_fmt_ts_or_dash(poi.invalidated_at))}</td>"
            + f"<td>{escape(', '.join(poi.activation_reason) or '-')}</td>"
            + f"<td>{escape(', '.join(poi.expiration_reason) or '-')}</td>"
            + "</tr>"
        )

    head_html = "".join(f"<th>{escape(h)}</th>" for h in headers)
    body_html = "\n".join(rows) if rows else "<tr><td colspan='13'>(no pois)</td></tr>"
    return f"""
      <h3>POIs</h3>
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


def _fmt_ts_or_dash(ts: datetime | None) -> str:
    return ts.isoformat() if ts is not None else "-"


def _json_like(payload: dict[str, Any]) -> str:
    lines: list[str] = ["{"]
    for key, value in payload.items():
        lines.append(f'  "{key}": {value!r},')
    lines.append("}")
    return "\n".join(lines)
