"""Explicit, bookmaker-price-derived probabilities for research display ONLY.

Never label a two-sided price-implied or no-vig normalized market percentage
as a native model forecast, independently verified outcome probability, sharp
bettor participation, expected value, or a betting recommendation.
"""
from __future__ import annotations

import math

from challenger_moneyline_market_baseline import MAX_OVERROUND


def price_pair_probabilities(first_implied, second_implied):
    """Return price mathematics as percentages, retaining the price overround."""
    if (type(first_implied) not in (int, float)
            or type(second_implied) not in (int, float)
            or not math.isfinite(first_implied)
            or not math.isfinite(second_implied)
            or not 0 < first_implied < 1
            or not 0 < second_implied < 1):
        raise ValueError("invalid_pair_implied_prices")
    vig_sum = first_implied + second_implied
    if not 1 <= vig_sum <= MAX_OVERROUND:
        raise ValueError("implausible_market_overround")
    return {
        "first_side_break_even_percent": round(100 * first_implied, 2),
        "second_side_break_even_percent": round(100 * second_implied, 2),
        "first_side_no_vig_market_percent": round(100 * first_implied / vig_sum, 2),
        "second_side_no_vig_market_percent": round(100 * second_implied / vig_sum, 2),
        "bookmaker_price_overround_percent": round(100 * (vig_sum - 1), 2),
        "native_model_probability_percent": None,
        "verified_sharp_bettor_probability_percent": None,
        "verified_model_edge_percentage_points": None,
        "certified_ev_roi_percent": None,
        "probability_source": "source_book_label_market_price_only_not_model",
        "direct_executable_sportsbook_checkout_verified": False,
    }
