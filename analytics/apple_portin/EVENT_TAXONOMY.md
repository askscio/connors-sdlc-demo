# Apple Port-In Funnel Event Taxonomy

## Overview

This document defines the event taxonomy for tracking the Apple port-in purchase journey on web.
Events are designed to measure funnel conversion and identify fallout points across the journey.

**Jira Reference:** SE-5027 (Analytics & Reporting for Apple Port-In Funnel)

**Dependencies:**
- SE-5026 (Implement Web Flow for Apple Port-In Offers) - Web flow implementation
- Web tracking framework and analytics platform

---

## Event Category

All Apple port-in funnel events use the category: `ApplePortInFunnel`

This category groups all related events for downstream analysis in BigQuery/dashboards.

---

## Funnel Steps

The Apple port-in journey consists of the following sequential steps:

| Step | Name | Description |
|------|------|-------------|
| 1 | `landing_page` | User lands on Apple port-in offer page |
| 2 | `offer_view` | User views a specific offer |
| 3 | `eligibility_check` | System checks user eligibility for port-in |
| 4 | `device_selection` | User selects an Apple device |
| 5 | `plan_selection` | User selects a plan |
| 6 | `cart_add` | User adds device/plan to cart |
| 7 | `checkout_start` | User initiates checkout |
| 8 | `checkout_complete` | User completes purchase |

---

## Event Definitions

### 1. Funnel Step View Events

Track when users view each step in the funnel.

**Event Name:** `View`

| Property | Type | Required | Description |
|----------|------|----------|-------------|
| `funnel_step` | string | Yes | One of the funnel step names above |
| `channel` | string | Yes | Channel identifier (e.g., "web", "mobile_web") |
| `apple_sku` | string | No | Apple device SKU if applicable |
| `offer_id` | string | No | Offer identifier if applicable |
| `session_id` | string | Yes | Unique session identifier |
| `timestamp` | datetime | Yes | Event timestamp (ISO 8601) |

**Example:**
```json
{
  "category": "ApplePortInFunnel",
  "action": "View",
  "params": {
    "funnel_step": "offer_view",
    "channel": "web",
    "apple_sku": "IPHONE15PRO256",
    "offer_id": "PORTIN_PROMO_2024Q1",
    "session_id": "abc123"
  }
}
```

---

### 2. Eligibility Evaluation Events

Track eligibility check outcomes.

**Event Name:** `EligibilityCheck`

| Property | Type | Required | Description |
|----------|------|----------|-------------|
| `result` | string | Yes | "pass" or "fail" |
| `failure_reason` | string | No | Reason code if result is "fail" |
| `carrier_from` | string | No | Source carrier for port-in |
| `channel` | string | Yes | Channel identifier |
| `apple_sku` | string | No | Apple device SKU if applicable |
| `offer_id` | string | No | Offer identifier |
| `session_id` | string | Yes | Unique session identifier |
| `check_duration_ms` | number | No | Time taken for eligibility check |

**Failure Reason Codes:**
- `INVALID_CARRIER` - Source carrier not eligible
- `ACCOUNT_TYPE_INELIGIBLE` - Account type doesn't qualify
- `CREDIT_CHECK_FAILED` - Credit requirements not met
- `EXISTING_CUSTOMER` - Already a customer (if new-only offer)
- `DEVICE_INELIGIBLE` - Device SKU not eligible for offer
- `REGION_INELIGIBLE` - User's region not supported
- `TENURE_REQUIREMENT` - Tenure requirement not met

**Example:**
```json
{
  "category": "ApplePortInFunnel",
  "action": "EligibilityCheck",
  "params": {
    "result": "fail",
    "failure_reason": "INVALID_CARRIER",
    "carrier_from": "regional_carrier",
    "channel": "web",
    "offer_id": "PORTIN_PROMO_2024Q1",
    "session_id": "abc123",
    "check_duration_ms": 245
  }
}
```

---

### 3. Add to Cart Events

Track when users add items to cart.

**Event Name:** `AddToCart`

| Property | Type | Required | Description |
|----------|------|----------|-------------|
| `apple_sku` | string | Yes | Apple device SKU |
| `device_name` | string | Yes | Human-readable device name |
| `device_category` | string | Yes | Device category (e.g., "iPhone", "iPad") |
| `offer_id` | string | No | Applied offer identifier |
| `offer_value` | number | No | Offer discount value in cents |
| `plan_id` | string | No | Selected plan identifier |
| `channel` | string | Yes | Channel identifier |
| `session_id` | string | Yes | Unique session identifier |
| `cart_total_cents` | number | No | Cart total in cents |

**Example:**
```json
{
  "category": "ApplePortInFunnel",
  "action": "AddToCart",
  "params": {
    "apple_sku": "IPHONE15PRO256",
    "device_name": "iPhone 15 Pro 256GB",
    "device_category": "iPhone",
    "offer_id": "PORTIN_PROMO_2024Q1",
    "offer_value": 80000,
    "plan_id": "UNLIMITED_PLUS",
    "channel": "web",
    "session_id": "abc123",
    "cart_total_cents": 99900
  }
}
```

---

### 4. Checkout Events

Track checkout initiation and completion.

**Event Name:** `CheckoutStart` / `CheckoutComplete`

| Property | Type | Required | Description |
|----------|------|----------|-------------|
| `apple_sku` | string | Yes | Apple device SKU |
| `offer_id` | string | No | Applied offer identifier |
| `offer_value` | number | No | Offer discount value in cents |
| `plan_id` | string | No | Selected plan identifier |
| `channel` | string | Yes | Channel identifier |
| `session_id` | string | Yes | Unique session identifier |
| `order_id` | string | No | Order ID (for CheckoutComplete only) |
| `order_total_cents` | number | No | Order total in cents |
| `payment_method` | string | No | Payment method used |

**Example (CheckoutComplete):**
```json
{
  "category": "ApplePortInFunnel",
  "action": "CheckoutComplete",
  "params": {
    "apple_sku": "IPHONE15PRO256",
    "offer_id": "PORTIN_PROMO_2024Q1",
    "offer_value": 80000,
    "plan_id": "UNLIMITED_PLUS",
    "channel": "web",
    "session_id": "abc123",
    "order_id": "ORD-2024-123456",
    "order_total_cents": 99900,
    "payment_method": "credit_card"
  }
}
```

---

### 5. Funnel Abandonment Events

Track when users leave the funnel.

**Event Name:** `FunnelAbandon`

| Property | Type | Required | Description |
|----------|------|----------|-------------|
| `abandon_step` | string | Yes | Step where user abandoned |
| `time_in_funnel_ms` | number | No | Total time spent in funnel |
| `channel` | string | Yes | Channel identifier |
| `apple_sku` | string | No | Apple device SKU if selected |
| `offer_id` | string | No | Offer identifier if viewed |
| `session_id` | string | Yes | Unique session identifier |

---

## Required Breakdowns / Filters

All events support the following breakdown dimensions for dashboard filtering:

| Dimension | Description | Example Values |
|-----------|-------------|----------------|
| `channel` | Marketing/sales channel | "web", "mobile_web", "app" |
| `offer_id` | Specific promotion/offer | "PORTIN_PROMO_2024Q1" |
| `apple_sku` | Apple device SKU | "IPHONE15PRO256", "IPHONE15128" |
| `device_category` | Device type | "iPhone", "iPad", "Apple Watch" |
| `funnel_step` | Current funnel step | See Funnel Steps table |
| `eligibility_result` | Pass/fail status | "pass", "fail" |

---

## Dashboard Metrics

### Primary KPIs

1. **Funnel Conversion Rate**
   - Landing → Checkout Complete
   - Step-by-step conversion rates

2. **Eligibility Pass Rate**
   - Total eligibility checks
   - Pass rate by channel, offer, device

3. **Cart Conversion**
   - Add to cart rate
   - Cart to checkout rate
   - Checkout completion rate

4. **Fallout Analysis**
   - Drop-off by funnel step
   - Abandonment reasons
   - Time to abandonment

### Breakdown Dimensions
- By Channel
- By Offer ID
- By Apple SKU
- By Device Category
- By Time Period (daily, weekly, monthly)

---

## Validation Requirements

### Lower Environment Validation
- [ ] All events fire correctly in staging
- [ ] Event payloads match schema
- [ ] Session tracking works across steps
- [ ] Funnel step sequencing is correct

### Production Validation
- [ ] Events visible in analytics platform
- [ ] Dashboard data populating correctly
- [ ] Filters working as expected
- [ ] No PII in event payloads

---

## Implementation Notes

1. **Session Management**: Each user journey should have a unique `session_id` that persists across all funnel steps.

2. **Timestamp Handling**: All timestamps should be in ISO 8601 format in UTC.

3. **Currency**: All monetary values should be in cents (integer) to avoid floating-point issues.

4. **Privacy**: No PII should be included in events. Use opaque identifiers only.

5. **Sampling**: Production events may be sampled. Ensure critical conversion events are not sampled.
