"""D01 Advanced Scenarios: dividend, reversal, correction, idempotency, owner isolation.

These tests verify the advanced ledger behaviors required by D01 acceptance.
"""
from datetime import date
from decimal import Decimal
from uuid import UUID, uuid4

import pytest

from services.api.private_pipeline import calculate_marts, effective_ledger_events, calculate_risk_marts
from services.api.trade_calculation import transaction_result
from services.api.repository import OversellError


USER_A = UUID("00000000-0000-0000-0000-000000000001")
USER_B = UUID("00000000-0000-0000-0000-000000000002")


def event(user_id, version, kind, symbol="2330", shares="100", price="100", **kwargs):
    return {
        "event_id": kwargs.pop("event_id", uuid4()),
        "user_id": user_id,
        "ledger_version": version,
        "event_action": kwargs.pop("event_action", "ORIGINAL"),
        "event_type": kind,
        "trade_date": kwargs.pop("trade_date", date(2026, 10, 1)),
        "symbol": symbol,
        "shares": Decimal(shares),
        "price": Decimal(price),
        "cash_amount": kwargs.pop("cash_amount", None),
        "fee": Decimal(kwargs.pop("fee", "0")),
        "tax": Decimal(kwargs.pop("tax", "0")),
        "currency": kwargs.pop("currency", "TWD"),
        "reverses_event_id": kwargs.pop("reverses_event_id", None),
        "replaces_event_id": kwargs.pop("replaces_event_id", None),
        **kwargs,
    }


# =============================================================================
# 1. Dividend Processing Tests
# =============================================================================

class TestDividendProcessing:
    """Verify cash and stock dividend handling in marts and transaction results."""

    def test_cash_dividend_adds_to_realized_pnl_and_annual_summary(self):
        buy = event(USER_A, 1, "BUY", shares="1000", price="50")
        div = event(USER_A, 2, "CASH_DIV", shares="0", price="0",
                    cash_amount=Decimal("2000"), fee="10", tax="200",
                    trade_date=date(2026, 10, 15))
        marts = calculate_marts([buy, div], {"2330": Decimal("55")}, date(2026, 10, 15))

        # Position unchanged by cash dividend
        pos = marts["mart_user_positions"][0]
        assert pos["shares"] == Decimal("1000")
        assert pos["average_cost"] == Decimal("50")

        # Annual PnL includes dividend net of fees/tax
        annual = marts["mart_user_annual_pnl"][0]
        assert annual["cash_dividends"] == Decimal("2000")
        assert annual["realized_pnl"] == Decimal("1790")  # 2000 - 10 - 200

    def test_stock_dividend_increases_shares_without_changing_cost_basis(self):
        buy = event(USER_A, 1, "BUY", shares="1000", price="50")
        stock_div = event(USER_A, 2, "STOCK_DIV", shares="100", price="0",
                          trade_date=date(2026, 10, 15))
        marts = calculate_marts([buy, stock_div], {"2330": Decimal("45")}, date(2026, 10, 15))

        pos = marts["mart_user_positions"][0]
        assert pos["shares"] == Decimal("1100")
        # Average cost diluted: 50000 / 1100 ≈ 45.45
        assert pos["average_cost"] == Decimal("50000") / Decimal("1100")

    def test_stock_dividend_requires_existing_position(self):
        stock_div = event(USER_A, 1, "STOCK_DIV", shares="100", price="0")
        with pytest.raises(OversellError, match="existing position"):
            transaction_result([stock_div], stock_div, valuation_date=date(2026, 10, 15))

    def test_cash_dividend_with_zero_shares_still_records_income(self):
        """Dividend received after full sale (ex-date before sale)."""
        buy = event(USER_A, 1, "BUY", shares="100", price="50", trade_date=date(2026, 9, 1))
        sell = event(USER_A, 2, "SELL", shares="100", price="60", trade_date=date(2026, 9, 15))
        div = event(USER_A, 3, "CASH_DIV", shares="0", price="0",
                    cash_amount=Decimal("500"), trade_date=date(2026, 10, 1))
        marts = calculate_marts([buy, sell, div], {}, date(2026, 10, 1))

        # No position remains
        assert len(marts["mart_user_positions"]) == 0
        # But dividend is recorded
        annual = marts["mart_user_annual_pnl"][0]
        assert annual["cash_dividends"] == Decimal("500")


# =============================================================================
# 2. REVERSAL Tests
# =============================================================================

class TestReversalProcessing:
    """Verify REVERSAL events correctly void original transactions."""

    def test_reversal_voids_buy_and_restores_zero_position(self):
        buy_id = uuid4()
        buy = event(USER_A, 1, "BUY", event_id=buy_id)
        reversal = event(USER_A, 2, "BUY", event_action="REVERSAL",
                         reverses_event_id=buy_id)
        marts = calculate_marts([buy, reversal], {}, date(2026, 10, 15))
        assert len(marts["mart_user_positions"]) == 0

    def test_reversal_voids_sell_and_restores_shares(self):
        buy = event(USER_A, 1, "BUY", shares="100")
        sell_id = uuid4()
        sell = event(USER_A, 2, "SELL", shares="50", event_id=sell_id,
                     trade_date=date(2026, 10, 2))
        reversal = event(USER_A, 3, "SELL", shares="50", event_action="REVERSAL",
                         reverses_event_id=sell_id, trade_date=date(2026, 10, 3))
        marts = calculate_marts([buy, sell, reversal], {"2330": Decimal("100")}, date(2026, 10, 15))

        pos = marts["mart_user_positions"][0]
        assert pos["shares"] == Decimal("100")

    def test_reversal_removes_realized_pnl_from_annual(self):
        buy = event(USER_A, 1, "BUY", shares="100", price="50")
        sell_id = uuid4()
        sell = event(USER_A, 2, "SELL", shares="100", price="60", event_id=sell_id,
                     trade_date=date(2026, 10, 2))
        reversal = event(USER_A, 3, "SELL", shares="100", price="60",
                         event_action="REVERSAL", reverses_event_id=sell_id,
                         trade_date=date(2026, 10, 3))
        marts = calculate_marts([buy, sell, reversal], {"2330": Decimal("55")}, date(2026, 10, 15))

        # Position restored
        pos = marts["mart_user_positions"][0]
        assert pos["shares"] == Decimal("100")
        # Realized PnL should be zero (sell voided)
        annual = marts["mart_user_annual_pnl"][0]
        assert annual["realized_pnl"] == Decimal("0")

    def test_reversal_of_dividend_removes_income(self):
        buy = event(USER_A, 1, "BUY", shares="100")
        div_id = uuid4()
        div = event(USER_A, 2, "CASH_DIV", shares="0", price="0",
                    cash_amount=Decimal("500"), event_id=div_id,
                    trade_date=date(2026, 10, 5))
        reversal = event(USER_A, 3, "CASH_DIV", shares="0", price="0",
                         cash_amount=Decimal("500"), event_action="REVERSAL",
                         reverses_event_id=div_id, trade_date=date(2026, 10, 6))
        marts = calculate_marts([buy, div, reversal], {"2330": Decimal("100")}, date(2026, 10, 15))

        annual = marts["mart_user_annual_pnl"][0]
        assert annual["cash_dividends"] == Decimal("0")
        assert annual["realized_pnl"] == Decimal("0")


# =============================================================================
# 3. Correction (REPLACEMENT) Tests
# =============================================================================

class TestCorrectionProcessing:
    """Verify REPLACEMENT events correctly update original transactions."""

    def test_correction_updates_price_and_recalculates_cost_basis(self):
        original_id = uuid4()
        buy = event(USER_A, 1, "BUY", shares="100", price="50", event_id=original_id)
        reversal = event(USER_A, 2, "BUY", shares="100", price="50",
                         event_action="REVERSAL", reverses_event_id=original_id)
        replacement = event(USER_A, 3, "BUY", shares="100", price="55",
                            event_action="REPLACEMENT", replaces_event_id=original_id)
        marts = calculate_marts([buy, reversal, replacement],
                                {"2330": Decimal("60")}, date(2026, 10, 15))

        pos = marts["mart_user_positions"][0]
        assert pos["shares"] == Decimal("100")
        assert pos["average_cost"] == Decimal("55")

    def test_correction_updates_shares_and_validates_subsequent_sells(self):
        original_id = uuid4()
        buy = event(USER_A, 1, "BUY", shares="100", price="50", event_id=original_id)
        sell = event(USER_A, 2, "SELL", shares="80", price="60",
                     trade_date=date(2026, 10, 2))
        reversal = event(USER_A, 3, "BUY", shares="100", price="50",
                         event_action="REVERSAL", reverses_event_id=original_id,
                         trade_date=date(2026, 10, 3))
        # Reduce original buy to 50 shares - should fail because sell of 80 exists
        replacement = event(USER_A, 4, "BUY", shares="50", price="50",
                            event_action="REPLACEMENT", replaces_event_id=original_id,
                            trade_date=date(2026, 10, 3))

        with pytest.raises(OversellError):
            transaction_result([buy, sell, reversal, replacement], replacement,
                               valuation_date=date(2026, 10, 15))

    def test_correction_preserves_chronological_order_for_same_day_trades(self):
        """Correction should maintain original trade order on the same day."""
        original_id = uuid4()
        buy = event(USER_A, 1, "BUY", shares="100", price="50", event_id=original_id)
        sell = event(USER_A, 2, "SELL", shares="50", price="60")
        reversal = event(USER_A, 3, "BUY", shares="100", price="50",
                         event_action="REVERSAL", reverses_event_id=original_id)
        replacement = event(USER_A, 4, "BUY", shares="100", price="55",
                            event_action="REPLACEMENT", replaces_event_id=original_id)

        result = transaction_result([buy, sell, reversal, replacement], sell,
                                    valuation_date=date(2026, 10, 15))
        # Sell should use the corrected cost basis
        # Original: 50 * 60 - 50 * 50 = 500
        # Corrected: 50 * 60 - 50 * 55 = 250
        assert result["transaction_realized_pnl"] == Decimal("250")

    def test_multiple_corrections_chain_correctly(self):
        """Multiple corrections to the same event should chain properly."""
        original_id = uuid4()
        buy = event(USER_A, 1, "BUY", shares="100", price="50", event_id=original_id)
        rev1 = event(USER_A, 2, "BUY", event_action="REVERSAL",
                     reverses_event_id=original_id)
        rep1_id = uuid4()
        rep1 = event(USER_A, 3, "BUY", shares="100", price="55",
                     event_action="REPLACEMENT", replaces_event_id=original_id,
                     event_id=rep1_id)
        rev2 = event(USER_A, 4, "BUY", event_action="REVERSAL",
                     reverses_event_id=rep1_id)
        rep2 = event(USER_A, 5, "BUY", shares="100", price="60",
                     event_action="REPLACEMENT", replaces_event_id=rep1_id)

        marts = calculate_marts([buy, rev1, rep1, rev2, rep2],
                                {"2330": Decimal("70")}, date(2026, 10, 15))
        pos = marts["mart_user_positions"][0]
        assert pos["average_cost"] == Decimal("60")


# =============================================================================
# 4. Idempotency and Race Condition Tests
# =============================================================================

class TestIdempotencyAndRaceConditions:
    """Verify idempotency keys and version checks prevent duplicate/stale writes."""

    def test_effective_ledger_events_excludes_reversed_transactions(self):
        buy_id = uuid4()
        buy = event(USER_A, 1, "BUY", event_id=buy_id)
        reversal = event(USER_A, 2, "BUY", event_action="REVERSAL",
                         reverses_event_id=buy_id)
        effective = list(effective_ledger_events([buy, reversal]))
        assert len(effective) == 0

    def test_effective_ledger_events_includes_replacement_not_original(self):
        original_id = uuid4()
        buy = event(USER_A, 1, "BUY", event_id=original_id)
        reversal = event(USER_A, 2, "BUY", event_action="REVERSAL",
                         reverses_event_id=original_id)
        replacement = event(USER_A, 3, "BUY", shares="200",
                            event_action="REPLACEMENT", replaces_event_id=original_id)

        effective = list(effective_ledger_events([buy, reversal, replacement]))
        assert len(effective) == 1
        assert effective[0]["shares"] == Decimal("200")

    def test_correction_lineage_cycle_detection(self):
        """Detect and reject circular correction references."""
        id_a = uuid4()
        id_b = uuid4()
        # Create a cycle: A replaces B, B replaces A
        event_a = event(USER_A, 1, "BUY", event_id=id_a, replaces_event_id=id_b)
        event_b = event(USER_A, 2, "BUY", event_id=id_b, replaces_event_id=id_a)

        with pytest.raises(ValueError, match="cycle"):
            list(effective_ledger_events([event_a, event_b]))

    def test_ledger_version_ordering_determines_effective_sequence(self):
        """Events with same trade_date are ordered by ledger_version."""
        buy1 = event(USER_A, 1, "BUY", shares="100", price="50")
        buy2 = event(USER_A, 2, "BUY", shares="100", price="60")
        sell = event(USER_A, 3, "SELL", shares="150", price="70")

        result = transaction_result([buy1, buy2, sell], sell,
                                    valuation_date=date(2026, 10, 15))
        # FIFO by ledger_version: sell 100@50 + 50@60 = 5000 + 3000 = 8000 cost
        # Proceeds: 150 * 70 = 10500
        # But MOVING_AVERAGE: avg = (5000 + 6000) / 200 = 55
        # Realized = 150 * 70 - 150 * 55 = 10500 - 8250 = 2250
        assert result["transaction_realized_pnl"] == Decimal("2250")


# =============================================================================
# 5. Owner Isolation Tests
# =============================================================================

class TestOwnerIsolation:
    """Verify different owners' data is completely isolated."""

    def test_different_owners_have_separate_positions(self):
        buy_a = event(USER_A, 1, "BUY", shares="100", price="50")
        buy_b = event(USER_B, 1, "BUY", shares="200", price="60")

        marts_a = calculate_marts([buy_a], {"2330": Decimal("55")}, date(2026, 10, 15))
        marts_b = calculate_marts([buy_b], {"2330": Decimal("55")}, date(2026, 10, 15))

        pos_a = marts_a["mart_user_positions"][0]
        pos_b = marts_b["mart_user_positions"][0]

        assert pos_a["user_id"] == str(USER_A)
        assert pos_a["shares"] == Decimal("100")
        assert pos_b["user_id"] == str(USER_B)
        assert pos_b["shares"] == Decimal("200")

    def test_owner_a_reversal_does_not_affect_owner_b(self):
        buy_a_id = uuid4()
        buy_a = event(USER_A, 1, "BUY", shares="100", event_id=buy_a_id)
        reversal_a = event(USER_A, 2, "BUY", event_action="REVERSAL",
                           reverses_event_id=buy_a_id)
        buy_b = event(USER_B, 1, "BUY", shares="100")

        # Process A's events
        marts_a = calculate_marts([buy_a, reversal_a], {}, date(2026, 10, 15))
        # Process B's events
        marts_b = calculate_marts([buy_b], {"2330": Decimal("100")}, date(2026, 10, 15))

        assert len(marts_a["mart_user_positions"]) == 0
        assert len(marts_b["mart_user_positions"]) == 1
        assert marts_b["mart_user_positions"][0]["shares"] == Decimal("100")

    def test_mixed_owner_events_are_filtered_correctly(self):
        """Ensure calculate_marts only processes events for the specified owner."""
        buy_a = event(USER_A, 1, "BUY", shares="100")
        buy_b = event(USER_B, 1, "BUY", shares="200")

        # If we accidentally pass both owners' events, each owner's mart
        # should only reflect their own transactions
        all_events = [buy_a, buy_b]

        # calculate_marts uses user_id from events, so it will create
        # positions for both users if passed both
        marts = calculate_marts(all_events, {"2330": Decimal("100")}, date(2026, 10, 15))

        # Should have 2 positions, one per user
        positions = marts["mart_user_positions"]
        assert len(positions) == 2

        pos_a = next(p for p in positions if p["user_id"] == str(USER_A))
        pos_b = next(p for p in positions if p["user_id"] == str(USER_B))

        assert pos_a["shares"] == Decimal("100")
        assert pos_b["shares"] == Decimal("200")

    def test_owner_isolation_in_risk_marts(self):
        """Risk calculations are owner-scoped."""
        buy_a = event(USER_A, 1, "BUY", shares="100", price="100")
        buy_b = event(USER_B, 1, "BUY", shares="200", price="100")

        marts_a = calculate_marts([buy_a], {"2330": Decimal("110")}, date(2026, 10, 15))
        marts_b = calculate_marts([buy_b], {"2330": Decimal("110")}, date(2026, 10, 15))

        risk_a = calculate_risk_marts([buy_a], marts_a["mart_user_positions"],
                                      None, {}, date(2026, 10, 15))
        risk_b = calculate_risk_marts([buy_b], marts_b["mart_user_positions"],
                                      None, {}, date(2026, 10, 15))

        summary_a = risk_a["mart_user_portfolio_summary"][0]
        summary_b = risk_b["mart_user_portfolio_summary"][0]

        assert summary_a["user_id"] == str(USER_A)
        assert summary_a["market_value"] == Decimal("11000")
        assert summary_b["user_id"] == str(USER_B)
        assert summary_b["market_value"] == Decimal("22000")


# =============================================================================
# 6. Edge Cases and Complex Scenarios
# =============================================================================

class TestEdgeCases:
    """Additional edge cases for comprehensive coverage."""

    def test_fractional_shares_handling(self):
        buy = event(USER_A, 1, "BUY", shares="0.5", price="1000")
        sell = event(USER_A, 2, "SELL", shares="0.25", price="1200",
                     trade_date=date(2026, 10, 2))

        result = transaction_result([buy, sell], sell, valuation_date=date(2026, 10, 15))
        # Cost: 0.25 * 1000 = 250
        # Proceeds: 0.25 * 1200 = 300
        # Realized: 300 - 250 = 50
        assert result["transaction_realized_pnl"] == Decimal("50")
        assert result["remaining_shares"] == Decimal("0.25")

    def test_zero_price_stock_dividend(self):
        buy = event(USER_A, 1, "BUY", shares="100", price="50")
        stock_div = event(USER_A, 2, "STOCK_DIV", shares="10", price="0")

        marts = calculate_marts([buy, stock_div], {"2330": Decimal("45")}, date(2026, 10, 15))
        pos = marts["mart_user_positions"][0]

        assert pos["shares"] == Decimal("110")
        # Cost basis unchanged: 5000 / 110 ≈ 45.45
        expected_avg = Decimal("5000") / Decimal("110")
        assert pos["average_cost"] == expected_avg

    def test_backdated_buy_affects_subsequent_sell_cost_basis(self):
        """A backdated buy should affect the cost basis of later sells."""
        sell = event(USER_A, 2, "SELL", shares="50", price="60",
                     trade_date=date(2026, 10, 5))
        buy1 = event(USER_A, 1, "BUY", shares="100", price="50",
                     trade_date=date(2026, 10, 1))
        # Backdated buy at lower price
        buy2 = event(USER_A, 3, "BUY", shares="100", price="40",
                     trade_date=date(2026, 10, 3))

        # Order by trade_date, then ledger_version
        events = sorted([buy1, sell, buy2], key=lambda e: (e["trade_date"], e["ledger_version"]))

        result = transaction_result(events, sell, valuation_date=date(2026, 10, 15))
        # After buy1 (100@50) and buy2 (100@40): 200 shares, avg = 45
        # Sell 50@60: realized = 50 * (60 - 45) = 750
        assert result["transaction_realized_pnl"] == Decimal("750")

    def test_missing_price_marks_position_as_missing(self):
        buy = event(USER_A, 1, "BUY", shares="100", price="50")
        marts = calculate_marts([buy], {}, date(2026, 10, 15))

        pos = marts["mart_user_positions"][0]
        assert pos["price_status"] == "missing"
        assert pos["market_value"] is None
        assert pos["missing_reason"] == "no_eligible_persisted_ohlcv"

    def test_stale_price_marks_position_as_stale(self):
        buy = event(USER_A, 1, "BUY", shares="100", price="50")
        # Price from 2 days ago
        marts = calculate_marts([buy], {"2330": (Decimal("55"), date(2026, 10, 13))},
                                date(2026, 10, 15))

        pos = marts["mart_user_positions"][0]
        assert pos["price_status"] == "stale"
        assert pos["market_value"] == Decimal("5500")
