"""
Tests for the Threshold Rules Engine (SE-5033 implementation).

Tests that rules correctly:
- Match plans/segments in scope
- Calculate thresholds (volume vs. spend)
- Handle alert frequency, reset rules, and opt-in/opt-out
- Cover edge cases (multi-SIM, shared plans, roaming partners)
"""

import pytest
from datetime import date
from decimal import Decimal

from international_usage.models import (
    UsageType,
    ThresholdType,
    CustomerSegment,
    PlanType,
    UsageAllowance,
    CustomerUsageState,
    EventType,
)
from international_usage.rules import (
    ThresholdRule,
    ThresholdRulesEngine,
    GeographyRule,
    create_default_rules,
    default_rules_engine,
)


class TestThresholdRule:
    """Tests for individual ThresholdRule behavior."""

    def test_rule_matches_plan_type(self):
        """Test that rules match correct plan types."""
        rule = ThresholdRule(
            rule_id="test_rule",
            name="Test Rule",
            description="Test",
            plan_types=[PlanType.INTERNATIONAL_PACKAGE],
        )

        allowance = UsageAllowance(
            allowance_id="allow_1",
            customer_id="cust_001",
            plan_type=PlanType.INTERNATIONAL_PACKAGE,
            usage_type=UsageType.VOICE_MINUTES,
            threshold_type=ThresholdType.VOLUME,
            volume_limit=Decimal("1000"),
        )
        state = CustomerUsageState(customer_id="cust_001", allowance=allowance)

        assert rule.matches_customer_state(state)

    def test_rule_does_not_match_different_plan(self):
        """Test that rules don't match incorrect plan types."""
        rule = ThresholdRule(
            rule_id="test_rule",
            name="Test Rule",
            description="Test",
            plan_types=[PlanType.INTERNATIONAL_PACKAGE],
        )

        allowance = UsageAllowance(
            allowance_id="allow_1",
            customer_id="cust_001",
            plan_type=PlanType.PAY_AS_YOU_GO,  # Different plan type
            usage_type=UsageType.VOICE_MINUTES,
            threshold_type=ThresholdType.VOLUME,
            volume_limit=Decimal("1000"),
        )
        state = CustomerUsageState(customer_id="cust_001", allowance=allowance)

        assert not rule.matches_customer_state(state)

    def test_rule_matches_any_plan_when_empty(self):
        """Test that empty plan_types matches any plan."""
        rule = ThresholdRule(
            rule_id="test_rule",
            name="Test Rule",
            description="Test",
            plan_types=[],  # Empty = match all
        )

        for plan_type in PlanType:
            allowance = UsageAllowance(
                allowance_id="allow_1",
                customer_id="cust_001",
                plan_type=plan_type,
                usage_type=UsageType.VOICE_MINUTES,
                threshold_type=ThresholdType.VOLUME,
                volume_limit=Decimal("1000"),
            )
            state = CustomerUsageState(customer_id="cust_001", allowance=allowance)
            assert rule.matches_customer_state(state)

    def test_inactive_rule_does_not_match(self):
        """Test that inactive rules don't match."""
        rule = ThresholdRule(
            rule_id="test_rule",
            name="Test Rule",
            description="Test",
            plan_types=[],
            is_active=False,
        )

        allowance = UsageAllowance(
            allowance_id="allow_1",
            customer_id="cust_001",
            plan_type=PlanType.INTERNATIONAL_PACKAGE,
            usage_type=UsageType.VOICE_MINUTES,
            threshold_type=ThresholdType.VOLUME,
            volume_limit=Decimal("1000"),
        )
        state = CustomerUsageState(customer_id="cust_001", allowance=allowance)

        assert not rule.matches_customer_state(state)

    def test_get_next_threshold(self):
        """Test getting the next threshold to cross."""
        rule = ThresholdRule(
            rule_id="test_rule",
            name="Test Rule",
            description="Test",
            threshold_percentages=[50, 75, 90, 100],
        )

        # At 0%, next is 50%
        assert rule.get_next_threshold(Decimal("0")) == 50

        # At 49%, next is still 50%
        assert rule.get_next_threshold(Decimal("49")) == 50

        # At 50%, next is 75%
        assert rule.get_next_threshold(Decimal("50")) == 75

        # At 99%, next is 100%
        assert rule.get_next_threshold(Decimal("99")) == 100

        # At 100%, no more thresholds
        assert rule.get_next_threshold(Decimal("100")) is None

    def test_should_emit_event_duplicate_suppression(self):
        """Test that duplicate events are suppressed."""
        rule = ThresholdRule(
            rule_id="test_rule",
            name="Test Rule",
            description="Test",
            suppress_duplicate_alerts=True,
        )

        allowance = UsageAllowance(
            allowance_id="allow_1",
            customer_id="cust_001",
            plan_type=PlanType.INTERNATIONAL_PACKAGE,
            usage_type=UsageType.VOICE_MINUTES,
            threshold_type=ThresholdType.VOLUME,
            volume_limit=Decimal("1000"),
        )
        state = CustomerUsageState(customer_id="cust_001", allowance=allowance)

        # First time should emit
        assert rule.should_emit_event(state, 50)

        # After marking as notified, should not emit again
        state.mark_threshold_notified(EventType.THRESHOLD_50_PERCENT)
        assert not rule.should_emit_event(state, 50)


class TestThresholdRulesEngine:
    """Tests for the ThresholdRulesEngine."""

    def test_add_and_get_applicable_rule(self):
        """Test adding rules and finding applicable ones."""
        engine = ThresholdRulesEngine()

        rule1 = ThresholdRule(
            rule_id="rule_1",
            name="Rule 1",
            description="First rule",
            plan_types=[PlanType.INTERNATIONAL_PACKAGE],
            priority=100,
        )
        rule2 = ThresholdRule(
            rule_id="rule_2",
            name="Rule 2",
            description="Second rule",
            plan_types=[PlanType.PAY_AS_YOU_GO],
            priority=50,
        )

        engine.add_rule(rule1)
        engine.add_rule(rule2)

        # Create state that matches rule1
        allowance = UsageAllowance(
            allowance_id="allow_1",
            customer_id="cust_001",
            plan_type=PlanType.INTERNATIONAL_PACKAGE,
            usage_type=UsageType.VOICE_MINUTES,
            threshold_type=ThresholdType.VOLUME,
            volume_limit=Decimal("1000"),
        )
        state = CustomerUsageState(customer_id="cust_001", allowance=allowance)

        applicable = engine.get_applicable_rule(state)
        assert applicable is not None
        assert applicable.rule_id == "rule_1"

    def test_higher_priority_rule_takes_precedence(self):
        """Test that higher priority rules are selected first."""
        engine = ThresholdRulesEngine()

        low_priority = ThresholdRule(
            rule_id="low",
            name="Low Priority",
            description="Test",
            plan_types=[],  # Matches all
            priority=10,
        )
        high_priority = ThresholdRule(
            rule_id="high",
            name="High Priority",
            description="Test",
            plan_types=[],  # Matches all
            priority=100,
        )

        # Add in reverse order
        engine.add_rule(low_priority)
        engine.add_rule(high_priority)

        allowance = UsageAllowance(
            allowance_id="allow_1",
            customer_id="cust_001",
            plan_type=PlanType.INTERNATIONAL_PACKAGE,
            usage_type=UsageType.VOICE_MINUTES,
            threshold_type=ThresholdType.VOLUME,
            volume_limit=Decimal("1000"),
        )
        state = CustomerUsageState(customer_id="cust_001", allowance=allowance)

        applicable = engine.get_applicable_rule(state)
        assert applicable.rule_id == "high"

    def test_evaluate_thresholds(self):
        """Test threshold evaluation."""
        engine = ThresholdRulesEngine()
        engine.add_rule(ThresholdRule(
            rule_id="test_rule",
            name="Test Rule",
            description="Test",
            plan_types=[],
            threshold_percentages=[50, 75, 90, 100],
        ))

        allowance = UsageAllowance(
            allowance_id="allow_1",
            customer_id="cust_001",
            plan_type=PlanType.INTERNATIONAL_PACKAGE,
            usage_type=UsageType.VOICE_MINUTES,
            threshold_type=ThresholdType.VOLUME,
            volume_limit=Decimal("1000"),
        )
        state = CustomerUsageState(
            customer_id="cust_001",
            allowance=allowance,
            current_volume=Decimal("500"),  # 50%
        )

        crossed = engine.evaluate_thresholds(state)

        assert len(crossed) == 1
        assert crossed[0] == (50, EventType.THRESHOLD_50_PERCENT)

    def test_evaluate_thresholds_multiple_crossed(self):
        """Test when multiple thresholds are crossed at once."""
        engine = ThresholdRulesEngine()
        engine.add_rule(ThresholdRule(
            rule_id="test_rule",
            name="Test Rule",
            description="Test",
            plan_types=[],
            threshold_percentages=[50, 75, 90, 100],
        ))

        allowance = UsageAllowance(
            allowance_id="allow_1",
            customer_id="cust_001",
            plan_type=PlanType.INTERNATIONAL_PACKAGE,
            usage_type=UsageType.VOICE_MINUTES,
            threshold_type=ThresholdType.VOLUME,
            volume_limit=Decimal("1000"),
        )
        state = CustomerUsageState(
            customer_id="cust_001",
            allowance=allowance,
            current_volume=Decimal("800"),  # 80% - crosses 50% and 75%
        )

        crossed = engine.evaluate_thresholds(state)

        assert len(crossed) == 2
        percentages = [c[0] for c in crossed]
        assert 50 in percentages
        assert 75 in percentages

    def test_customer_opt_out(self):
        """Test customer opt-out functionality (per SE-5033)."""
        engine = ThresholdRulesEngine()
        engine.add_rule(ThresholdRule(
            rule_id="test_rule",
            name="Test Rule",
            description="Test",
            plan_types=[],
            opt_out_allowed=True,
        ))

        allowance = UsageAllowance(
            allowance_id="allow_1",
            customer_id="cust_001",
            plan_type=PlanType.INTERNATIONAL_PACKAGE,
            usage_type=UsageType.VOICE_MINUTES,
            threshold_type=ThresholdType.VOLUME,
            volume_limit=Decimal("1000"),
        )
        state = CustomerUsageState(
            customer_id="cust_001",
            allowance=allowance,
            current_volume=Decimal("500"),
        )

        # Before opt-out, threshold should be detected
        crossed = engine.evaluate_thresholds(state)
        assert len(crossed) == 1

        # After opt-out, no thresholds should be returned
        engine.set_customer_opt_out("cust_001", True)
        crossed = engine.evaluate_thresholds(state)
        assert len(crossed) == 0

        # Re-enable
        engine.set_customer_opt_out("cust_001", False)
        crossed = engine.evaluate_thresholds(state)
        assert len(crossed) == 1


class TestGeographyRules:
    """Tests for geography-specific rules (per SE-5033)."""

    def test_geography_rule_regulatory_requirement(self):
        """Test geography-specific regulatory requirements."""
        engine = ThresholdRulesEngine()

        # EU countries have regulatory requirements
        eu_rule = GeographyRule(
            country_code="DE",
            country_name="Germany",
            regulatory_alert_required=True,
            regulatory_timing_hours=1,  # Must alert within 1 hour
        )
        engine.add_geography_rule(eu_rule)

        required, timing = engine.should_alert_for_geography("DE")
        assert required is True
        assert timing == 1

        # Non-regulated country
        required, timing = engine.should_alert_for_geography("US")
        assert required is False
        assert timing is None


class TestDefaultRules:
    """Tests for the default rules configuration (per SE-5033)."""

    def test_default_rules_created(self):
        """Test that default rules are created."""
        rules = create_default_rules()
        assert len(rules) > 0

    def test_default_rules_engine_configured(self):
        """Test that default rules engine is properly configured."""
        engine = default_rules_engine()

        # Test that consumer international package matches
        allowance = UsageAllowance(
            allowance_id="allow_1",
            customer_id="cust_001",
            plan_type=PlanType.INTERNATIONAL_PACKAGE,
            usage_type=UsageType.VOICE_MINUTES,
            threshold_type=ThresholdType.VOLUME,
            volume_limit=Decimal("1000"),
        )
        state = CustomerUsageState(customer_id="cust_001", allowance=allowance)

        rule = engine.get_applicable_rule(state)
        assert rule is not None

    def test_roaming_bundle_rule(self):
        """Test that roaming bundle rule is configured."""
        engine = default_rules_engine()

        allowance = UsageAllowance(
            allowance_id="allow_1",
            customer_id="cust_001",
            plan_type=PlanType.ROAMING_BUNDLE,
            usage_type=UsageType.DATA_MB,
            threshold_type=ThresholdType.VOLUME,
            volume_limit=Decimal("5000"),
        )
        state = CustomerUsageState(customer_id="cust_001", allowance=allowance)

        rule = engine.get_applicable_rule(state)
        assert rule is not None
        assert rule.rule_id == "rule_roaming_bundle"

    def test_shared_plan_rule(self):
        """Test that shared plan rule handles aggregation (per SE-5033 edge cases)."""
        engine = default_rules_engine()

        allowance = UsageAllowance(
            allowance_id="allow_1",
            customer_id="cust_001",
            plan_type=PlanType.SHARED_PLAN,
            usage_type=UsageType.VOICE_MINUTES,
            threshold_type=ThresholdType.VOLUME,
            volume_limit=Decimal("2000"),
        )
        state = CustomerUsageState(
            customer_id="cust_001",
            allowance=allowance,
            is_shared_plan=True,
            shared_plan_members=["cust_002", "cust_003"],
        )

        rule = engine.get_applicable_rule(state)
        assert rule is not None
        assert rule.aggregate_shared_plan_usage is True

    def test_multi_sim_rule(self):
        """Test that multi-SIM rule handles aggregation (per SE-5033 edge cases)."""
        engine = default_rules_engine()

        allowance = UsageAllowance(
            allowance_id="allow_1",
            customer_id="cust_001",
            plan_type=PlanType.MULTI_SIM,
            usage_type=UsageType.VOICE_MINUTES,
            threshold_type=ThresholdType.VOLUME,
            volume_limit=Decimal("1500"),
        )
        state = CustomerUsageState(customer_id="cust_001", allowance=allowance)

        rule = engine.get_applicable_rule(state)
        assert rule is not None
        assert rule.aggregate_multi_sim_usage is True


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
