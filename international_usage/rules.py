"""
Threshold Rules Engine (implements SE-5033 specifications).

Defines configurable rules for:
- Which plans/segments are in scope for international usage alerts
- How 50% thresholds are calculated (volume vs. spend)
- Alert frequency, reset rules, and opt-in/opt-out behavior
- Edge cases (multi-SIM, shared plans, roaming partners)
"""

from dataclasses import dataclass, field
from decimal import Decimal
from typing import Optional, Callable
from datetime import date

from international_usage.models import (
    UsageType,
    ThresholdType,
    CustomerSegment,
    PlanType,
    CustomerUsageState,
    EventType,
)


@dataclass
class ThresholdRule:
    """
    A rule defining threshold detection behavior for a plan/segment combination.

    Per SE-5033: Rules cover initial in-scope products and geographies,
    with documented edge cases for multi-SIM, shared plans, and roaming partners.
    """
    rule_id: str
    name: str
    description: str

    # Scope: Which customers this rule applies to
    plan_types: list[PlanType] = field(default_factory=list)
    customer_segments: list[CustomerSegment] = field(default_factory=list)
    geographies: list[str] = field(default_factory=list)  # ISO country codes

    # Threshold configuration
    threshold_type: ThresholdType = ThresholdType.VOLUME
    threshold_percentages: list[int] = field(default_factory=lambda: [50, 75, 90, 100])

    # Usage types this rule monitors
    usage_types: list[UsageType] = field(default_factory=lambda: [
        UsageType.VOICE_MINUTES,
        UsageType.SMS_COUNT,
        UsageType.DATA_MB,
    ])

    # Alert frequency rules (per SE-5033)
    max_alerts_per_period: int = 4  # One per threshold level
    cooldown_hours: int = 0  # Minimum hours between alerts for same threshold
    suppress_duplicate_alerts: bool = True

    # Reset behavior (per SE-5033)
    reset_on_billing_cycle: bool = True
    reset_on_plan_change: bool = True

    # Opt-in/opt-out behavior (per SE-5033)
    opt_in_required: bool = False
    opt_out_allowed: bool = True

    # Edge case handling (per SE-5033)
    aggregate_shared_plan_usage: bool = True  # For shared/family plans
    aggregate_multi_sim_usage: bool = True    # For multi-SIM accounts
    include_roaming_partner_usage: bool = True

    # Rule priority (higher = evaluated first)
    priority: int = 0

    # Active status
    is_active: bool = True

    def matches_customer_state(self, state: CustomerUsageState) -> bool:
        """Check if this rule applies to the given customer state."""
        if not self.is_active:
            return False

        # Check plan type
        if self.plan_types and state.allowance.plan_type not in self.plan_types:
            return False

        # Check usage type
        if self.usage_types and state.allowance.usage_type not in self.usage_types:
            return False

        return True

    def get_next_threshold(self, current_percentage: Decimal) -> Optional[int]:
        """
        Get the next threshold percentage that hasn't been crossed.

        Returns None if all thresholds have been crossed.
        """
        for threshold in sorted(self.threshold_percentages):
            if current_percentage >= threshold:
                continue
            return threshold
        return None

    def should_emit_event(
        self,
        state: CustomerUsageState,
        threshold: int,
    ) -> bool:
        """
        Determine if an event should be emitted for the given threshold.

        Considers:
        - Whether threshold has already been notified
        - Duplicate suppression settings
        - Max alerts per period
        """
        # Map threshold percentage to event type
        event_type = self._threshold_to_event_type(threshold)
        if event_type is None:
            return False

        # Check duplicate suppression
        if self.suppress_duplicate_alerts and state.has_crossed_threshold(event_type):
            return False

        # Check max alerts
        if len(state.thresholds_notified) >= self.max_alerts_per_period:
            return False

        return True

    def _threshold_to_event_type(self, threshold: int) -> Optional[EventType]:
        """Map a threshold percentage to an event type."""
        mapping = {
            50: EventType.THRESHOLD_50_PERCENT,
            75: EventType.THRESHOLD_75_PERCENT,
            90: EventType.THRESHOLD_90_PERCENT,
            100: EventType.THRESHOLD_100_PERCENT,
        }
        return mapping.get(threshold)


@dataclass
class GeographyRule:
    """
    Geography-specific rules for international usage thresholds.

    Per SE-5033: Rules for initial in-scope geographies.
    """
    country_code: str  # ISO 3166-1 alpha-2
    country_name: str

    # Override default threshold percentages for this geography
    custom_thresholds: Optional[list[int]] = None

    # Regulatory requirements
    regulatory_alert_required: bool = False
    regulatory_timing_hours: Optional[int] = None  # Max hours to deliver alert

    # Roaming partner considerations
    roaming_partners: list[str] = field(default_factory=list)
    exclude_from_aggregation: bool = False


class ThresholdRulesEngine:
    """
    Engine for evaluating threshold rules against customer usage states.

    Implements the business logic defined in SE-5033 for determining
    when to emit threshold events.
    """

    def __init__(self):
        self._rules: list[ThresholdRule] = []
        self._geography_rules: dict[str, GeographyRule] = {}
        self._customer_opt_outs: set[str] = set()

    def add_rule(self, rule: ThresholdRule) -> None:
        """Add a threshold rule to the engine."""
        self._rules.append(rule)
        # Keep rules sorted by priority (descending)
        self._rules.sort(key=lambda r: r.priority, reverse=True)

    def add_geography_rule(self, rule: GeographyRule) -> None:
        """Add a geography-specific rule."""
        self._geography_rules[rule.country_code] = rule

    def set_customer_opt_out(self, customer_id: str, opt_out: bool = True) -> None:
        """Set opt-out status for a customer."""
        if opt_out:
            self._customer_opt_outs.add(customer_id)
        else:
            self._customer_opt_outs.discard(customer_id)

    def is_customer_opted_out(self, customer_id: str) -> bool:
        """Check if customer has opted out of threshold alerts."""
        return customer_id in self._customer_opt_outs

    def get_applicable_rule(self, state: CustomerUsageState) -> Optional[ThresholdRule]:
        """
        Find the highest-priority rule that applies to the customer state.

        Returns None if no rules apply.
        """
        for rule in self._rules:
            if rule.matches_customer_state(state):
                return rule
        return None

    def evaluate_thresholds(
        self,
        state: CustomerUsageState,
    ) -> list[tuple[int, EventType]]:
        """
        Evaluate which thresholds have been crossed and should trigger events.

        Returns a list of (threshold_percentage, event_type) tuples for
        thresholds that:
        1. Have been crossed based on current usage
        2. Haven't already been notified
        3. Match active rules
        4. Customer hasn't opted out

        This is the core detection logic for SE-5034.
        """
        # Check opt-out
        if self.is_customer_opted_out(state.customer_id):
            return []

        # Find applicable rule
        rule = self.get_applicable_rule(state)
        if rule is None:
            return []

        # Calculate current percentage
        current_percentage = state.get_usage_percentage()

        # Find crossed thresholds
        crossed = []
        for threshold in rule.threshold_percentages:
            if current_percentage >= threshold:
                event_type = rule._threshold_to_event_type(threshold)
                if event_type and rule.should_emit_event(state, threshold):
                    crossed.append((threshold, event_type))

        return crossed

    def should_alert_for_geography(
        self,
        country_code: str,
    ) -> tuple[bool, Optional[int]]:
        """
        Check if alerts are required for a specific geography.

        Returns (required, timing_hours) tuple.
        """
        geo_rule = self._geography_rules.get(country_code)
        if geo_rule and geo_rule.regulatory_alert_required:
            return True, geo_rule.regulatory_timing_hours
        return False, None


def create_default_rules() -> list[ThresholdRule]:
    """
    Create the default set of threshold rules per SE-5033 specifications.

    These rules cover the initial in-scope products and are designed
    to be configurable for different MNO deployments.
    """
    rules = []

    # Rule 1: Consumer postpaid plans with international packages
    rules.append(ThresholdRule(
        rule_id="rule_consumer_intl_package",
        name="Consumer International Package",
        description="50% alerts for consumer postpaid customers with international calling packages",
        plan_types=[PlanType.INTERNATIONAL_PACKAGE, PlanType.UNLIMITED_INTERNATIONAL],
        customer_segments=[CustomerSegment.CONSUMER, CustomerSegment.POSTPAID],
        threshold_type=ThresholdType.VOLUME,
        threshold_percentages=[50, 75, 90, 100],
        priority=100,
    ))

    # Rule 2: Business/Enterprise plans - spend-based thresholds
    rules.append(ThresholdRule(
        rule_id="rule_business_spend",
        name="Business International Spend",
        description="50% alerts for business customers based on spend thresholds",
        plan_types=[PlanType.INTERNATIONAL_PACKAGE, PlanType.PAY_AS_YOU_GO],
        customer_segments=[CustomerSegment.BUSINESS, CustomerSegment.ENTERPRISE],
        threshold_type=ThresholdType.SPEND,
        threshold_percentages=[50, 75, 90, 100],
        priority=90,
    ))

    # Rule 3: Roaming bundles
    rules.append(ThresholdRule(
        rule_id="rule_roaming_bundle",
        name="Roaming Bundle Usage",
        description="50% alerts for roaming bundle usage (data focus)",
        plan_types=[PlanType.ROAMING_BUNDLE],
        customer_segments=[],  # All segments
        threshold_type=ThresholdType.VOLUME,
        usage_types=[UsageType.DATA_MB],
        threshold_percentages=[50, 75, 90, 100],
        priority=80,
    ))

    # Rule 4: Shared/Family plans - aggregated usage
    rules.append(ThresholdRule(
        rule_id="rule_shared_plan",
        name="Shared Plan International",
        description="50% alerts for shared plans with aggregated family usage",
        plan_types=[PlanType.SHARED_PLAN],
        threshold_type=ThresholdType.VOLUME,
        aggregate_shared_plan_usage=True,
        threshold_percentages=[50, 75, 90, 100],
        priority=70,
    ))

    # Rule 5: Multi-SIM accounts
    rules.append(ThresholdRule(
        rule_id="rule_multi_sim",
        name="Multi-SIM International",
        description="50% alerts for multi-SIM accounts with aggregated usage",
        plan_types=[PlanType.MULTI_SIM],
        threshold_type=ThresholdType.VOLUME,
        aggregate_multi_sim_usage=True,
        threshold_percentages=[50, 75, 90, 100],
        priority=60,
    ))

    # Rule 6: Pay-as-you-go - spend thresholds only
    rules.append(ThresholdRule(
        rule_id="rule_payg_spend",
        name="Pay-As-You-Go Spend",
        description="50% alerts for PAYG customers based on spend caps",
        plan_types=[PlanType.PAY_AS_YOU_GO],
        customer_segments=[CustomerSegment.PREPAID],
        threshold_type=ThresholdType.SPEND,
        threshold_percentages=[50, 75, 90, 100],
        priority=50,
    ))

    return rules


def default_rules_engine() -> ThresholdRulesEngine:
    """Create a ThresholdRulesEngine with default rules configured."""
    engine = ThresholdRulesEngine()
    for rule in create_default_rules():
        engine.add_rule(rule)
    return engine
