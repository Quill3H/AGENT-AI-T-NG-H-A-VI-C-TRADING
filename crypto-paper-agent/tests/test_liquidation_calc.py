"""
test_liquidation_calc.py - Unit tests for Liquidation Price Calculation
========================================================================
Kiểm thử tra cứu MMR tiers theo leverage_brackets của Binance Futures
và tính toán chính xác giá thanh lý (Estimated Liquidation Price) cho các vị thế LONG và SHORT.
"""
import pytest
from src.risk.invariant_checks import (
    get_mmr_tier,
    calculate_estimated_liquidation_price,
    DEFAULT_LEVERAGE_BRACKETS_BTC,
)


class TestLiquidationCalculation:
    def test_mmr_tier_lookup_at_least_3_distinct_tiers(self, config):
        """
        Kiểm thử tra đúng MMR tier theo từng mức position_size_usd khác nhau:
        1. Tier 1: 30,000 USD (<= 50,000) -> MMR = 0.004 (0.4%), cum = 0
        2. Tier 2: 150,000 USD (<= 250,000) -> MMR = 0.005 (0.5%), cum = 50
        3. Tier 3: 500,000 USD (<= 1,000,000) -> MMR = 0.01 (1.0%), cum = 1300
        4. Tier 4: 5,000,000 USD (<= 10,000,000) -> MMR = 0.025 (2.5%), cum = 16300
        """
        brackets = config.get("leverage_brackets", {})

        # Tier 1
        mmr1, cum1 = get_mmr_tier(30000.0, symbol="BTCUSDT", leverage_brackets=brackets)
        assert mmr1 == 0.004
        assert cum1 == 0.0

        # Tier 2
        mmr2, cum2 = get_mmr_tier(150000.0, symbol="BTCUSDT", leverage_brackets=brackets)
        assert mmr2 == 0.005
        assert cum2 == 50.0

        # Tier 3
        mmr3, cum3 = get_mmr_tier(500000.0, symbol="BTCUSDT", leverage_brackets=brackets)
        assert mmr3 == 0.01
        assert cum3 == 1300.0

        # Tier 4
        mmr4, cum4 = get_mmr_tier(5000000.0, symbol="BTCUSDT", leverage_brackets=brackets)
        assert mmr4 == 0.025
        assert cum4 == 16300.0

    def test_long_liquidation_tier1_formula(self, config):
        """
        Vị thế LONG Tier 1:
        Entry = 50,000 USD, Position size = 30,000 USD, Leverage = 5x
        Tier 1: MMR = 0.004, cum = 0
        P_liq = [50000 * (1 - 1/5) - 0] / (1 - 0.004) = 40000 / 0.996 = 40,160.6425 USD
        """
        brackets = config.get("leverage_brackets", {})
        liq = calculate_estimated_liquidation_price(
            direction="LONG",
            entry_price=50000.0,
            position_size_usd=30000.0,
            leverage=5.0,
            symbol="BTCUSDT",
            leverage_brackets=brackets,
        )
        expected = 40000.0 / 0.996
        assert pytest.approx(liq, rel=1e-5) == expected

    def test_long_liquidation_tier2_formula_with_cum_amount(self, config):
        """
        Vị thế LONG Tier 2 (có trừ cumulative maintenance amount):
        Entry = 50,000 USD, Position size = 150,000 USD, Leverage = 5x
        Quantity = 150000 / 50000 = 3.0 BTC
        Tier 2: MMR = 0.005, cum = 50
        cum_per_qty = 50 / 3.0 = 16.6667
        Numerator = 50000 * (1 - 0.2) - 16.6667 = 39983.3333
        Denominator = 1 - 0.005 = 0.995
        P_liq = 39983.3333 / 0.995 = 40,184.2546 USD
        """
        brackets = config.get("leverage_brackets", {})
        liq = calculate_estimated_liquidation_price(
            direction="LONG",
            entry_price=50000.0,
            position_size_usd=150000.0,
            leverage=5.0,
            symbol="BTCUSDT",
            leverage_brackets=brackets,
        )
        qty = 150000.0 / 50000.0
        expected = (50000.0 * 0.8 - (50.0 / qty)) / 0.995
        assert pytest.approx(liq, rel=1e-5) == expected

    def test_short_liquidation_tier1_formula(self, config):
        """
        Vị thế SHORT Tier 1:
        Entry = 50,000 USD, Position size = 30,000 USD, Leverage = 5x
        Tier 1: MMR = 0.004, cum = 0
        P_liq = [50000 * (1 + 1/5) + 0] / (1 + 0.004) = 60000 / 1.004 = 59,760.956 USD
        """
        brackets = config.get("leverage_brackets", {})
        liq = calculate_estimated_liquidation_price(
            direction="SHORT",
            entry_price=50000.0,
            position_size_usd=30000.0,
            leverage=5.0,
            symbol="BTCUSDT",
            leverage_brackets=brackets,
        )
        expected = 60000.0 / 1.004
        assert pytest.approx(liq, rel=1e-5) == expected

    def test_short_liquidation_tier2_formula_with_cum_amount(self, config):
        """
        Vị thế SHORT Tier 2:
        Entry = 50,000 USD, Position size = 150,000 USD, Leverage = 5x
        Quantity = 3.0 BTC, Tier 2: MMR = 0.005, cum = 50
        Numerator = 50000 * 1.2 + (50 / 3.0) = 60016.6667
        Denominator = 1 + 0.005 = 1.005
        P_liq = 60016.6667 / 1.005 = 59,718.076 USD
        """
        brackets = config.get("leverage_brackets", {})
        liq = calculate_estimated_liquidation_price(
            direction="SHORT",
            entry_price=50000.0,
            position_size_usd=150000.0,
            leverage=5.0,
            symbol="BTCUSDT",
            leverage_brackets=brackets,
        )
        qty = 150000.0 / 50000.0
        expected = (50000.0 * 1.2 + (50.0 / qty)) / 1.005
        assert pytest.approx(liq, rel=1e-5) == expected

    def test_invalid_arguments_raise(self):
        with pytest.raises(ValueError, match="entry_price must be positive"):
            calculate_estimated_liquidation_price("LONG", -50000, 10000, 5)
        with pytest.raises(ValueError, match="position_size_usd must be positive"):
            calculate_estimated_liquidation_price("LONG", 50000, -10000, 5)
        with pytest.raises(ValueError, match="leverage must be >= 1.0"):
            calculate_estimated_liquidation_price("LONG", 50000, 10000, 0.5)
        with pytest.raises(ValueError, match="Invalid direction"):
            calculate_estimated_liquidation_price("INVALID", 50000, 10000, 5)
