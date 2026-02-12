"""
Constants for Apple Port-In Funnel Analytics

Defines the event taxonomy constants including categories, actions, funnel steps,
and other enumerations used for tracking the Apple port-in purchase journey.

See EVENT_TAXONOMY.md for full documentation.
"""

from enum import Enum


class Category(str, Enum):
    """
    Event category for Apple port-in funnel events.

    All events in this funnel use the same category for easy grouping
    and downstream analysis in BigQuery/dashboards.
    """
    APPLE_PORTIN_FUNNEL = "ApplePortInFunnel"


class Action(str, Enum):
    """
    Event actions representing user interactions and system events
    in the Apple port-in funnel.
    """
    # View events
    VIEW = "View"

    # Eligibility events
    ELIGIBILITY_CHECK = "EligibilityCheck"

    # Cart events
    ADD_TO_CART = "AddToCart"
    REMOVE_FROM_CART = "RemoveFromCart"

    # Checkout events
    CHECKOUT_START = "CheckoutStart"
    CHECKOUT_COMPLETE = "CheckoutComplete"

    # Abandonment events
    FUNNEL_ABANDON = "FunnelAbandon"

    # Error events
    ERROR = "Error"


class FunnelStep(str, Enum):
    """
    Sequential steps in the Apple port-in purchase funnel.

    Steps are ordered from landing to completion. Each step represents
    a distinct point in the user journey where conversion can be measured.
    """
    LANDING_PAGE = "landing_page"
    OFFER_VIEW = "offer_view"
    ELIGIBILITY_CHECK = "eligibility_check"
    DEVICE_SELECTION = "device_selection"
    PLAN_SELECTION = "plan_selection"
    CART_ADD = "cart_add"
    CHECKOUT_START = "checkout_start"
    CHECKOUT_COMPLETE = "checkout_complete"

    @classmethod
    def get_step_order(cls) -> dict[str, int]:
        """Returns a mapping of step names to their sequential order (1-indexed)."""
        return {
            cls.LANDING_PAGE.value: 1,
            cls.OFFER_VIEW.value: 2,
            cls.ELIGIBILITY_CHECK.value: 3,
            cls.DEVICE_SELECTION.value: 4,
            cls.PLAN_SELECTION.value: 5,
            cls.CART_ADD.value: 6,
            cls.CHECKOUT_START.value: 7,
            cls.CHECKOUT_COMPLETE.value: 8,
        }

    @classmethod
    def get_step_number(cls, step: "FunnelStep") -> int:
        """Returns the sequential order number for a given step."""
        return cls.get_step_order().get(step.value, 0)


class EligibilityResult(str, Enum):
    """Result of an eligibility check for port-in offers."""
    PASS = "pass"
    FAIL = "fail"


class EligibilityFailureReason(str, Enum):
    """
    Reason codes for eligibility check failures.

    These codes help identify why users are falling out of the funnel
    during the eligibility check step.
    """
    INVALID_CARRIER = "INVALID_CARRIER"
    ACCOUNT_TYPE_INELIGIBLE = "ACCOUNT_TYPE_INELIGIBLE"
    CREDIT_CHECK_FAILED = "CREDIT_CHECK_FAILED"
    EXISTING_CUSTOMER = "EXISTING_CUSTOMER"
    DEVICE_INELIGIBLE = "DEVICE_INELIGIBLE"
    REGION_INELIGIBLE = "REGION_INELIGIBLE"
    TENURE_REQUIREMENT = "TENURE_REQUIREMENT"
    OFFER_EXPIRED = "OFFER_EXPIRED"
    OFFER_LIMIT_REACHED = "OFFER_LIMIT_REACHED"
    SYSTEM_ERROR = "SYSTEM_ERROR"


class Channel(str, Enum):
    """
    Marketing/sales channels where the port-in funnel can be accessed.

    Used for filtering and breaking down funnel metrics by channel.
    """
    WEB = "web"
    MOBILE_WEB = "mobile_web"
    APP = "app"
    STORE = "store"
    CALL_CENTER = "call_center"


class DeviceCategory(str, Enum):
    """
    Categories of Apple devices available for port-in offers.

    Used for filtering funnel metrics by device type.
    """
    IPHONE = "iPhone"
    IPAD = "iPad"
    APPLE_WATCH = "Apple Watch"
    MAC = "Mac"


class PaymentMethod(str, Enum):
    """Payment methods accepted at checkout."""
    CREDIT_CARD = "credit_card"
    DEBIT_CARD = "debit_card"
    APPLE_PAY = "apple_pay"
    PAYPAL = "paypal"
    FINANCING = "financing"
    CARRIER_BILLING = "carrier_billing"


# Event property keys for consistent naming
class EventProperty:
    """Standard property keys used across all events."""
    # Common properties
    SESSION_ID = "session_id"
    TIMESTAMP = "timestamp"
    CHANNEL = "channel"

    # Funnel properties
    FUNNEL_STEP = "funnel_step"
    STEP_NUMBER = "step_number"

    # Device properties
    APPLE_SKU = "apple_sku"
    DEVICE_NAME = "device_name"
    DEVICE_CATEGORY = "device_category"

    # Offer properties
    OFFER_ID = "offer_id"
    OFFER_VALUE = "offer_value"

    # Plan properties
    PLAN_ID = "plan_id"

    # Eligibility properties
    RESULT = "result"
    FAILURE_REASON = "failure_reason"
    CARRIER_FROM = "carrier_from"
    CHECK_DURATION_MS = "check_duration_ms"

    # Cart properties
    CART_TOTAL_CENTS = "cart_total_cents"

    # Checkout properties
    ORDER_ID = "order_id"
    ORDER_TOTAL_CENTS = "order_total_cents"
    PAYMENT_METHOD = "payment_method"

    # Abandonment properties
    ABANDON_STEP = "abandon_step"
    TIME_IN_FUNNEL_MS = "time_in_funnel_ms"

    # Error properties
    ERROR_CODE = "error_code"
    ERROR_MESSAGE = "error_message"
