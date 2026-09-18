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

    def test_gpt_benchmark_long_tier_crossing(self, config):
        """
        GPT Review Benchmark - LONG:
        Entry = 50,000 USD, Position size = 60,000 USD, Leverage = 3x (Quantity = 1.2 BTC).
        Notional at entry: 60,000 USD -> Tier 1 (MMR=0.005, cum=50).
        Nhưng tại giá thanh lý candidate P_cand, notional q * P_cand <= 50,000 USD -> rơi vào Tier 0!
        Tier-Consistent Solver giải ra:
        P_liq = [50000 * (1 - 1/3) - 0] / (1 - 0.004) = 33333.3333 / 0.996 = 33,467.202142 USD.
        """
        brackets = config.get("leverage_brackets", {})
        liq = calculate_estimated_liquidation_price(
            direction="LONG",
            entry_price=50000.0,
            position_size_usd=60000.0,
            leverage=3.0,
            symbol="BTCUSDT",
            leverage_brackets=brackets,
        )
        assert pytest.approx(liq, abs=0.01) == 33467.20
        # Notional at liq price: 1.2 * 33467.202142 = 40,160.64 USD <= 50,000 (chính xác Tier 0)
        assert (60000.0 / 50000.0) * liq <= 50000.0

    def test_gpt_benchmark_short_tier_crossing(self, config):
        """
        GPT Review Benchmark - SHORT:
        Entry = 50,000 USD, Position size = 45,000 USD, Leverage = 3x (Quantity = 0.9 BTC).
        Notional at entry: 45,000 USD -> Tier 0 (MMR=0.004, cum=0).
        Nhưng tại giá thanh lý candidate P_cand, notional q * P_cand > 50,000 USD -> rơi vào Tier 1!
        Tier-Consistent Solver giải ra:
        P_liq = [50000 * (1 + 1/3) + (50 / 0.9)] / (1 + 0.005)
              = (66666.6667 + 55.5556) / 1.005 = 66,390.270868 USD.
        """
        brackets = config.get("leverage_brackets", {})
        liq = calculate_estimated_liquidation_price(
            direction="SHORT",
            entry_price=50000.0,
            position_size_usd=45000.0,
            leverage=3.0,
            symbol="BTCUSDT",
            leverage_brackets=brackets,
        )
        assert pytest.approx(liq, abs=0.01) == 66390.27
        # Notional at liq price: 0.9 * 66390.270868 = 59,751.24 USD > 50,000 (chính xác Tier 1)
        assert (45000.0 / 50000.0) * liq > 50000.0

    def test_unknown_symbol_raises(self, config):
        """Nếu cấu hình leverage_brackets có sẵn nhưng không chứa symbol yêu cầu -> Raise ValueError."""
        brackets = config.get("leverage_brackets", {})
        with pytest.raises(ValueError, match="not found in provided leverage brackets configuration"):
            calculate_estimated_liquidation_price(
                "LONG", 50000.0, 30000.0, 5.0, symbol="SOLUSDT", leverage_brackets=brackets
            )

    def test_invalid_bracket_structure_raises(self):
        """Leverage brackets không hợp lệ (cap không tăng dần, rỗng) phải bị từ chối."""
        bad_brackets = {"BTCUSDT": [[50000, 0.004, 0], [40000, 0.005, 50]]}
        with pytest.raises(ValueError, match="Bracket cap must be strictly increasing"):
            calculate_estimated_liquidation_price(
                "LONG", 50000.0, 30000.0, 5.0, symbol="BTCUSDT", leverage_brackets=bad_brackets
            )

    def test_invalid_arguments_raise(self):
        with pytest.raises(ValueError, match="entry_price must be positive"):
            calculate_estimated_liquidation_price("LONG", -50000, 10000, 5)
        with pytest.raises(ValueError, match="position_size_usd must be positive"):
            calculate_estimated_liquidation_price("LONG", 50000, -10000, 5)
        with pytest.raises(ValueError, match="leverage must be >= 1.0"):
            calculate_estimated_liquidation_price("LONG", 50000, 10000, 0.5)
        with pytest.raises(ValueError, match="Invalid direction"):
            calculate_estimated_liquidation_price("INVALID", 50000, 10000, 5)
        with pytest.raises(TypeError, match="entry_price must be numeric"):
            calculate_estimated_liquidation_price("LONG", True, 10000, 5)
        with pytest.raises(ValueError, match="entry_price must be finite"):
            calculate_estimated_liquidation_price("LONG", float("nan"), 10000, 5)

    # -------------------------------------------------------------
    # F5 Regression Tests: Bracket Rigor, Bounds & Margin Balance
    # -------------------------------------------------------------
    def test_f5_notional_exceeds_max_cap_rejected(self, config):
        """
        F5: Vị thế vượt trần bracket tối đa (max cap = 500,000,000 USD)
        phải bị từ chối với ValueError, tuyệt đối không âm thầm suy diễn ngoại suy.
        """
        brackets = config.get("leverage_brackets", {})
        with pytest.raises(ValueError, match="exceeds maximum supported leverage bracket cap"):
            get_mmr_tier(600000000.0, symbol="BTCUSDT", leverage_brackets=brackets)

        with pytest.raises(ValueError, match="exceeds maximum supported leverage bracket cap"):
            calculate_estimated_liquidation_price(
                "LONG", 50000.0, 600000000.0, 5.0, symbol="BTCUSDT", leverage_brackets=brackets
            )

    def test_f5_initial_margin_le_maintenance_margin_at_entry_rejected(self, config):
        """
        F5: Ký quỹ ban đầu không đủ bù maintenance margin ngay tại thời điểm mở vị thế
        (1/leverage <= MMR_entry -> đã vi phạm điều kiện thanh lý ngay từ đầu).
        """
        brackets = config.get("leverage_brackets", {})
        # Leverage = 300x -> 1/300 = 0.00333 < MMR = 0.004
        with pytest.raises(ValueError, match="already liquidatable"):
            calculate_estimated_liquidation_price(
                "LONG", 50000.0, 30000.0, 300.0, symbol="BTCUSDT", leverage_brackets=brackets
            )

    def test_f5_independent_margin_balance_equation_verification(self, config):
        """
        F5: Kiểm chứng toán học độc lập:
        Nghiệm P_liq giải ra phải thỏa mãn chính xác phương trình cân bằng ký quỹ:
        Long:  M_initial + q * (P_liq - P_entry) = q * P_liq * MMR - cum
        Short: M_initial + q * (P_entry - P_liq) = q * P_liq * MMR - cum
        """
        brackets = config.get("leverage_brackets", {})
        test_cases = [
            ("LONG", 50000.0, 60000.0, 3.0),
            ("LONG", 65000.0, 150000.0, 5.0),
            ("SHORT", 50000.0, 45000.0, 3.0),
            ("SHORT", 55000.0, 300000.0, 4.0),
        ]

        for direction, entry, size, lev in test_cases:
            liq = calculate_estimated_liquidation_price(
                direction=direction,
                entry_price=entry,
                position_size_usd=size,
                leverage=lev,
                symbol="BTCUSDT",
                leverage_brackets=brackets,
            )
            q = size / entry
            initial_margin = size / lev
            notional_at_liq = q * liq
            mmr, cum = get_mmr_tier(notional_at_liq, symbol="BTCUSDT", leverage_brackets=brackets)
            maintenance_margin_at_liq = notional_at_liq * mmr - cum

            if direction == "LONG":
                equity_at_liq = initial_margin + q * (liq - entry)
            else:
                equity_at_liq = initial_margin + q * (entry - liq)

            assert pytest.approx(equity_at_liq, abs=1e-3) == maintenance_margin_at_liq

    def test_f5_long_1x_leverage_zero_liquidation(self, config):
        """
        F5: Vị thế LONG đòn bẩy 1x (không vay nợ ký quỹ, tương đương Spot).
        P_liq = [Entry * (1 - 1/1) - 0] / (1 - MMR) = 0.
        Không thể bị thanh lý khi giá > 0.
        """
        brackets = config.get("leverage_brackets", {})
        liq = calculate_estimated_liquidation_price(
            direction="LONG",
            entry_price=50000.0,
            position_size_usd=10000.0,
            leverage=1.0,
            symbol="BTCUSDT",
            leverage_brackets=brackets,
        )
        assert liq == 0.0

    def test_f5_bracket_maintenance_discontinuity_rejected(self):
        """
        F5: Cấu hình bracket có bước nhảy (discontinuity) trong maintenance margin
        tại ranh giới giữa 2 tier phải bị từ chối ngay từ khâu validation.
        Tier 1 cap 50k, MMR 0.004, cum 0 -> maint = 200.
        Tier 2 cap 100k, MMR 0.006, cum 0 -> maint tại 50k = 300 != 200 -> Discontinuous!
        """
        discontinuous_brackets = {
            "BTCUSDT": [
                [50000.0, 0.004, 0.0],
                [100000.0, 0.006, 0.0],  # Không có cum phù hợp bù chênh lệch
            ]
        }
        with pytest.raises(ValueError, match="maintenance margin discontinuity"):
            calculate_estimated_liquidation_price(
                "LONG", 50000.0, 10000.0, 3.0, symbol="BTCUSDT", leverage_brackets=discontinuous_brackets
            )
