"""HTF POI detection utilities combining structure + FVG context."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from typing import Literal

from charting.resampler import OhlcvBar
from indicators.fvg import FvgConfig, FvgDirection, FvgMitigationRule, FvgSignal, detect_fvgs
from indicators.structure import (
    Bias,
    DealingRange,
    StructureConfig,
    analyze_structure,
)

PoiSide = Literal["buy", "sell"]
PoiStatus = Literal["pending", "active", "invalidated"]
PoiActivationRule = Literal["touch", "wick_inside", "close_inside"]
PoiExpirationRule = Literal["none", "bars_since_activation", "bars_since_creation"]
FvgDirectionFilter = Literal["with_bias", "both"]
DiscountPremiumContext = Literal["discount", "premium", "mid", "outside_range"]
DynamicWidthSource = Literal["wick", "body"]


@dataclass(frozen=True, slots=True)
class HtfPoiConfig:
    fvg_direction_filter: FvgDirectionFilter = "with_bias"
    require_discount_premium_alignment: bool = True
    poi_activation_rule: PoiActivationRule = "touch"
    max_active_pois: int = 50
    only_unmitigated_fvg: bool = True
    poi_validity_bars: int | None = None
    poi_expiration_rule: PoiExpirationRule = "bars_since_activation"
    poi_dynamic_width_enabled: bool = True
    max_dynamic_extension_bars: int | None = None
    dynamic_width_source: DynamicWidthSource = "wick"
    replay_context: bool = True
    swing_left: int = 2
    swing_right: int = 2
    bos_buffer: Decimal = Decimal("0")
    min_gap_size: Decimal = Decimal("0")
    mitigation_rule: FvgMitigationRule = "wick"


@dataclass(frozen=True, slots=True)
class HtfPoiCandidate:
    side: PoiSide
    status: PoiStatus
    source_fvg_direction: FvgDirection
    fvg_formed_at: datetime
    poi_low: Decimal
    poi_high: Decimal
    dynamic_poi_low: Decimal
    dynamic_poi_high: Decimal
    discount_premium_context: DiscountPremiumContext
    activated_at: datetime | None
    invalidated_at: datetime | None
    expires_at: datetime | None
    activation_reason: list[str] = field(default_factory=list)
    expiration_reason: list[str] = field(default_factory=list)
    reason: list[str] = field(default_factory=list)


@dataclass(frozen=True, slots=True)
class HtfPoiContext:
    current_bias: Bias
    dealing_range: DealingRange | None
    poi_candidates: list[HtfPoiCandidate]
    active_poi: HtfPoiCandidate | None


def detect_htf_pois(
    *, bars: list[OhlcvBar], config: HtfPoiConfig | None = None
) -> HtfPoiContext:
    """Build HTF POI context from bars using structure + FVG."""
    cfg = config or HtfPoiConfig()
    _validate_config(cfg)

    structure_cfg = StructureConfig(
        swing_left=cfg.swing_left,
        swing_right=cfg.swing_right,
        allow_unconfirmed_last_swing=True,
        bos_buffer=cfg.bos_buffer,
    )
    structure = analyze_structure(bars=bars, config=structure_cfg)
    bias = structure.state.current_bias
    dealing_range = structure.state.current_dealing_range

    if not bars:
        return HtfPoiContext(
            current_bias=bias,
            dealing_range=dealing_range,
            poi_candidates=[],
            active_poi=None,
        )

    fvgs = detect_fvgs(
        bars=bars,
        config=FvgConfig(
            direction="both",
            min_gap_size=cfg.min_gap_size,
            mitigation_enabled=True,
            mitigation_rule=cfg.mitigation_rule,
        ),
    )

    candidates: list[HtfPoiCandidate] = []
    for fvg in fvgs:
        candidate_bias = bias
        candidate_dr = dealing_range
        if cfg.replay_context:
            formed_slice_end = fvg.index_end + 1
            formed_structure = analyze_structure(
                bars=bars[:formed_slice_end],
                config=structure_cfg,
            )
            candidate_bias = formed_structure.state.current_bias
            candidate_dr = formed_structure.state.current_dealing_range

        side = "buy" if fvg.direction == "bull" else "sell"
        if not _direction_allowed(cfg=cfg, bias=candidate_bias, side=side):
            continue

        if candidate_bias == "neutral":
            continue

        context = _classify_context(
            fvg_low=fvg.gap_low,
            fvg_high=fvg.gap_high,
            dealing_range=candidate_dr,
        )
        if not _alignment_ok(
            bias=candidate_bias,
            context=context,
            require_alignment=cfg.require_discount_premium_alignment,
        ):
            continue

        candidate = _build_candidate(
            bars=bars,
            fvg=fvg,
            side=side,
            context=context,
            cfg=cfg,
            bias=bias,
        )
        candidates.append(candidate)

    # Prioritize most recent FVGs to keep output deterministic and practical.
    candidates.sort(key=lambda c: c.fvg_formed_at, reverse=True)
    candidates = candidates[: cfg.max_active_pois]

    active_poi = next((c for c in candidates if c.status == "active"), None)
    return HtfPoiContext(
        current_bias=bias,
        dealing_range=dealing_range,
        poi_candidates=candidates,
        active_poi=active_poi,
    )


def _build_candidate(
    *,
    bars: list[OhlcvBar],
    fvg: FvgSignal,
    side: PoiSide,
    context: DiscountPremiumContext,
    cfg: HtfPoiConfig,
    bias: Bias,
) -> HtfPoiCandidate:
    last_index = len(bars) - 1
    scan_from = fvg.index_end + 1

    activation_idx: int | None = None
    invalidation_idx: int | None = None
    dynamic_low = fvg.gap_low
    dynamic_high = fvg.gap_high
    activation_reason: list[str] = []
    expiration_reason: list[str] = []
    reason: list[str] = ["fvg_selected", f"context_{context}", f"side_{side}"]

    expires_idx = _expiration_index(
        rule=cfg.poi_expiration_rule,
        validity_bars=cfg.poi_validity_bars,
        activation_idx=None,
        creation_idx=fvg.index_end,
    )

    for idx in range(scan_from, len(bars)):
        bar = bars[idx]
        is_activation = _is_activation(bar=bar, poi_low=fvg.gap_low, poi_high=fvg.gap_high, cfg=cfg)

        if activation_idx is None:
            if cfg.only_unmitigated_fvg:
                mitigated = _is_mitigated(
                    bar=bar,
                    direction=fvg.direction,
                    gap_low=fvg.gap_low,
                    gap_high=fvg.gap_high,
                    rule=cfg.mitigation_rule,
                )
                if mitigated and not is_activation:
                    invalidation_idx = idx
                    expiration_reason.append("pre_activation_mitigation")
                    break

            if is_activation:
                activation_idx = idx
                activation_reason = [
                    f"activation_{cfg.poi_activation_rule}",
                    "bias_ok",
                    "fvg_retest",
                ]
                reason.extend(activation_reason)
                expires_idx = _expiration_index(
                    rule=cfg.poi_expiration_rule,
                    validity_bars=cfg.poi_validity_bars,
                    activation_idx=activation_idx,
                    creation_idx=fvg.index_end,
                )
                continue

            if expires_idx is not None and idx >= expires_idx:
                invalidation_idx = idx
                expiration_reason.append("expired_before_activation")
                break
            continue

        if _is_price_invalidated(side=side, close=bar.close, poi_low=fvg.gap_low, poi_high=fvg.gap_high):
            invalidation_idx = idx
            expiration_reason.append("price_invalidation_close_beyond_gap_edge")
            break

        if (
            cfg.poi_dynamic_width_enabled
            and _can_extend_dynamic_width(
                idx=idx,
                activation_idx=activation_idx,
                max_extension_bars=cfg.max_dynamic_extension_bars,
            )
        ):
            dyn_low, dyn_high = _dynamic_bar_bounds(bar=bar, source=cfg.dynamic_width_source)
            dynamic_low = min(dynamic_low, dyn_low)
            dynamic_high = max(dynamic_high, dyn_high)

        if expires_idx is not None and idx >= expires_idx:
            invalidation_idx = idx
            if cfg.poi_expiration_rule == "bars_since_activation":
                expiration_reason.append("expired_bars_since_activation")
            else:
                expiration_reason.append("expired_bars_since_creation")
            break

    if (
        invalidation_idx is None
        and activation_idx is not None
        and not _bias_still_valid(side=side, bias=bias)
    ):
        invalidation_idx = last_index
        expiration_reason.append("bias_mismatch_current")

    status: PoiStatus = "pending"
    if activation_idx is not None and invalidation_idx is None:
        status = "active"
    if invalidation_idx is not None:
        status = "invalidated"

    expires_at = bars[expires_idx].timestamp_utc if expires_idx is not None and expires_idx <= last_index else None
    return HtfPoiCandidate(
        side=side,
        status=status,
        source_fvg_direction=fvg.direction,
        fvg_formed_at=fvg.formed_at,
        poi_low=fvg.gap_low,
        poi_high=fvg.gap_high,
        dynamic_poi_low=dynamic_low,
        dynamic_poi_high=dynamic_high,
        discount_premium_context=context,
        activated_at=bars[activation_idx].timestamp_utc if activation_idx is not None else None,
        invalidated_at=bars[invalidation_idx].timestamp_utc if invalidation_idx is not None else None,
        expires_at=expires_at,
        activation_reason=activation_reason,
        expiration_reason=expiration_reason,
        reason=reason,
    )


def _expiration_index(
    *,
    rule: PoiExpirationRule,
    validity_bars: int | None,
    activation_idx: int | None,
    creation_idx: int,
) -> int | None:
    if rule == "none" or validity_bars is None:
        return None
    if rule == "bars_since_creation":
        return creation_idx + validity_bars
    if activation_idx is None:
        return None
    return activation_idx + validity_bars


def _can_extend_dynamic_width(
    *, idx: int, activation_idx: int, max_extension_bars: int | None
) -> bool:
    bars_after_activation = idx - activation_idx
    if bars_after_activation < 1:
        return False
    if max_extension_bars is None:
        return True
    return bars_after_activation <= max_extension_bars


def _dynamic_bar_bounds(*, bar: OhlcvBar, source: DynamicWidthSource) -> tuple[Decimal, Decimal]:
    if source == "body":
        return min(bar.open, bar.close), max(bar.open, bar.close)
    return bar.low, bar.high


def _is_activation(
    *, bar: OhlcvBar, poi_low: Decimal, poi_high: Decimal, cfg: HtfPoiConfig
) -> bool:
    if cfg.poi_activation_rule == "touch":
        return bar.low <= poi_high and bar.high >= poi_low
    if cfg.poi_activation_rule == "wick_inside":
        wick_enters_from_above = bar.low <= poi_high and bar.high > poi_high
        wick_enters_from_below = bar.high >= poi_low and bar.low < poi_low
        return wick_enters_from_above or wick_enters_from_below
    return poi_low <= bar.close <= poi_high


def _is_mitigated(
    *,
    bar: OhlcvBar,
    direction: FvgDirection,
    gap_low: Decimal,
    gap_high: Decimal,
    rule: FvgMitigationRule,
) -> bool:
    if rule == "wick":
        if direction == "bull":
            return bar.low <= gap_high
        return bar.high >= gap_low
    if direction == "bull":
        return bar.close <= gap_high
    return bar.close >= gap_low


def _classify_context(
    *, fvg_low: Decimal, fvg_high: Decimal, dealing_range: DealingRange | None
) -> DiscountPremiumContext:
    if dealing_range is None:
        return "outside_range"

    discount_low, discount_high = dealing_range.discount_zone
    premium_low, premium_high = dealing_range.premium_zone
    in_discount = _intersects(fvg_low, fvg_high, discount_low, discount_high)
    in_premium = _intersects(fvg_low, fvg_high, premium_low, premium_high)

    if in_discount and in_premium:
        return "mid"
    if in_discount:
        return "discount"
    if in_premium:
        return "premium"
    return "outside_range"


def _intersects(a_low: Decimal, a_high: Decimal, b_low: Decimal, b_high: Decimal) -> bool:
    return max(a_low, b_low) <= min(a_high, b_high)


def _direction_allowed(*, cfg: HtfPoiConfig, bias: Bias, side: PoiSide) -> bool:
    if cfg.fvg_direction_filter == "both":
        return True
    if bias == "neutral":
        return False
    return _bias_still_valid(side=side, bias=bias)


def _alignment_ok(
    *, bias: Bias, context: DiscountPremiumContext, require_alignment: bool
) -> bool:
    if not require_alignment:
        return True
    if bias == "bull":
        return context == "discount"
    if bias == "bear":
        return context == "premium"
    return False


def _is_price_invalidated(
    *, side: PoiSide, close: Decimal, poi_low: Decimal, poi_high: Decimal
) -> bool:
    if side == "buy":
        return close < poi_low
    return close > poi_high


def _bias_still_valid(*, side: PoiSide, bias: Bias) -> bool:
    if bias == "neutral":
        return False
    if bias == "bull":
        return side == "buy"
    return side == "sell"


def _validate_config(cfg: HtfPoiConfig) -> None:
    if cfg.fvg_direction_filter not in ("with_bias", "both"):
        raise ValueError("fvg_direction_filter must be 'with_bias' or 'both'")
    if cfg.poi_activation_rule not in ("touch", "wick_inside", "close_inside"):
        raise ValueError("invalid poi_activation_rule")
    if cfg.max_active_pois < 1:
        raise ValueError("max_active_pois must be >= 1")
    if cfg.poi_expiration_rule not in ("none", "bars_since_activation", "bars_since_creation"):
        raise ValueError("invalid poi_expiration_rule")
    if cfg.poi_validity_bars is not None and cfg.poi_validity_bars < 1:
        raise ValueError("poi_validity_bars must be >= 1")
    if cfg.max_dynamic_extension_bars is not None and cfg.max_dynamic_extension_bars < 1:
        raise ValueError("max_dynamic_extension_bars must be >= 1")
    if cfg.dynamic_width_source not in ("wick", "body"):
        raise ValueError("dynamic_width_source must be 'wick' or 'body'")
    if cfg.swing_left < 1:
        raise ValueError("swing_left must be >= 1")
    if cfg.swing_right < 1:
        raise ValueError("swing_right must be >= 1")
    if cfg.bos_buffer < 0:
        raise ValueError("bos_buffer must be >= 0")
    if cfg.min_gap_size < 0:
        raise ValueError("min_gap_size must be >= 0")
    if cfg.mitigation_rule not in ("wick", "close"):
        raise ValueError("mitigation_rule must be 'wick' or 'close'")
