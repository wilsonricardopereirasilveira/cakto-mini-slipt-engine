# Cakto Mini Split Engine

Mini Split Engine built with Django REST Framework and PostgreSQL to calculate payment splits, persist captured payments, enforce idempotency, and register outbox events for downstream processing.

## Pull Request

https://github.com/wilsonricardopereirasilveira/cakto-mini-slipt-engine/pull/1

## How To Run

### Prerequisites

- Docker
- Docker Compose

### Commands

```bash
cp .env.example .env
docker compose up --build
```

### Run Tests

```bash
docker compose run --rm app python manage.py test app.tests
```

## Endpoints

### POST /api/v1/payments

Creates and persists a captured payment, its ledger entries, and one outbox event.

Request example:

```http
POST /api/v1/payments
Idempotency-Key: 0c72d7c1-7f5f-4f80-a36c-1cbad0b8c3b1
Content-Type: application/json

{
  "amount": "100.00",
  "currency": "BRL",
  "payment_method": "pix",
  "installments": 1,
  "splits": [
    {
      "recipient_id": "seller_1",
      "role": "seller",
      "percent": "100.00"
    }
  ]
}
```

Response example:

```json
{
  "payment_id": "8ead86bf-ed67-4368-95b4-37bbda758c7a",
  "status": "captured",
  "gross_amount": "100.00",
  "platform_fee_amount": "0.00",
  "net_amount": "100.00",
  "receivables": [
    {
      "recipient_id": "seller_1",
      "role": "seller",
      "amount": "100.00"
    }
  ],
  "outbox_event": {
    "type": "payment_captured",
    "status": "pending"
  }
}
```

`Idempotency-Key` is required.

- Same key with the same payload returns `200 OK` and the original stored payment.
- Same key with a different payload returns `409 Conflict`.

### POST /api/v1/checkout/quote

Calculates the payment quote without persisting any data.

Request example:

```http
POST /api/v1/checkout/quote
Content-Type: application/json

{
  "amount": "297.00",
  "currency": "BRL",
  "payment_method": "card",
  "installments": 3,
  "splits": [
    {
      "recipient_id": "producer_1",
      "role": "producer",
      "percent": "70.00"
    },
    {
      "recipient_id": "affiliate_9",
      "role": "affiliate",
      "percent": "30.00"
    }
  ]
}
```

Response example:

```json
{
  "gross_amount": "297.00",
  "platform_fee_amount": "26.70",
  "net_amount": "270.30",
  "receivables": [
    {
      "recipient_id": "producer_1",
      "role": "producer",
      "amount": "189.21"
    },
    {
      "recipient_id": "affiliate_9",
      "role": "affiliate",
      "amount": "81.09"
    }
  ]
}
```

## Technical Decisions

### 4.1 Precision And Rounding

`Decimal` is used for every monetary calculation because binary floating point introduces representation errors that are unacceptable for payment flows.

The platform fee uses `ROUND_HALF_UP` because it matches the most common financial expectation for fee rounding. Split distribution uses `ROUND_HALF_DOWN` as requested, so each receivable is derived consistently from the net amount before residual reconciliation.

### 4.2 Residual Cent Rule

The residual is the difference between the net amount and the sum of individually rounded receivables. It appears because each split line is rounded to two decimal places, while the total is calculated before that per-line rounding.

The implementation assigns the residual to the first recipient in the input list.

This choice is deterministic, simple to explain, and easy to audit. The same input always produces the same distribution and the reconciliation rule is explicit.

### 4.3 Idempotency Strategy

The API computes a SHA-256 hash of the request payload using `json.dumps(..., sort_keys=True)` and stores it together with the `Idempotency-Key`.

- Same key and same hash return `200 OK` with the original stored response data.
- Same key and different hash return `409 Conflict`.

Using a hash is more robust than manual field-by-field comparison because it gives one stable fingerprint for the full normalized payload, keeps the conflict check simple, and reduces the chance of inconsistent comparison logic across fields.

### 4.4 Metrics I Would Add In Production

- p95 and p99 latency for `POST /api/v1/payments`
- p95 and p99 latency for `POST /api/v1/checkout/quote`
- rate of `409 Conflict` responses caused by idempotency mismatches
- rate of `400 Bad Request` responses by validation error category
- count of outbox events still `pending`
- age of the oldest pending outbox event
- ratio between successful payment creations and total payment attempts

### 4.5 If I Had More Time

- implement an outbox worker to publish pending events
- add authentication and request authorization
- add structured logging and correlation IDs
- add rate limiting and abuse protection
- add more test coverage for serializer validation and failure paths
- expose health checks and readiness checks for container orchestration
- add OpenAPI documentation for the API contract

## How I Used AI

AI was used to speed up delivery of the exercise: initial project scaffolding, core implementation drafts, edge case review, and automated test generation. The work was iterated step by step, with Claude acting as a PO/Tech Lead style reviewer validating requirements, gaps, and output quality at each stage. Final behavior was verified through local execution, container runs, endpoint calls, and automated tests.
