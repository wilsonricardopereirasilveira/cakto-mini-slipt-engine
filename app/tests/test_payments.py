import uuid
from decimal import Decimal

from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIClient

from app.models import Payment


class PaymentAPITestCase(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.payments_url = "/api/v1/payments"

    def test_pix_zero_fee_full_split(self):
        response = self._post_payment(
            {
                "amount": "100.00",
                "currency": "BRL",
                "payment_method": "pix",
                "installments": 1,
                "splits": [
                    {
                        "recipient_id": "seller_1",
                        "role": "seller",
                        "percent": "100.00",
                    }
                ],
            }
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["platform_fee_amount"], "0.00")
        self.assertEqual(response.data["net_amount"], "100.00")
        self.assertEqual(response.data["receivables"][0]["amount"], "100.00")

    def test_card_3x_split_70_30(self):
        response = self._post_payment(
            {
                "amount": "297.00",
                "currency": "BRL",
                "payment_method": "card",
                "installments": 3,
                "splits": [
                    {
                        "recipient_id": "producer_1",
                        "role": "producer",
                        "percent": "70.00",
                    },
                    {
                        "recipient_id": "affiliate_9",
                        "role": "affiliate",
                        "percent": "30.00",
                    },
                ],
            }
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["platform_fee_amount"], "26.70")
        self.assertEqual(response.data["net_amount"], "270.30")
        receivables_total = sum(
            Decimal(receivable["amount"]) for receivable in response.data["receivables"]
        )
        self.assertEqual(receivables_total, Decimal("270.30"))

    def test_rounding_residue(self):
        response = self._post_payment(
            {
                "amount": "100.00",
                "currency": "BRL",
                "payment_method": "card",
                "installments": 1,
                "splits": [
                    {
                        "recipient_id": "recipient_1",
                        "role": "producer",
                        "percent": "34.00",
                    },
                    {
                        "recipient_id": "recipient_2",
                        "role": "affiliate",
                        "percent": "33.00",
                    },
                    {
                        "recipient_id": "recipient_3",
                        "role": "coproducer",
                        "percent": "33.00",
                    },
                ],
            }
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        receivables_total = sum(
            Decimal(receivable["amount"]) for receivable in response.data["receivables"]
        )
        self.assertEqual(receivables_total, Decimal(response.data["net_amount"]))

    def test_idempotency_same_payload(self):
        idempotency_key = str(uuid.uuid4())
        payload = {
            "amount": "100.00",
            "currency": "BRL",
            "payment_method": "pix",
            "installments": 1,
            "splits": [
                {
                    "recipient_id": "seller_1",
                    "role": "seller",
                    "percent": "100.00",
                }
            ],
        }

        first_response = self._post_payment(payload, idempotency_key=idempotency_key)
        second_response = self._post_payment(payload, idempotency_key=idempotency_key)

        self.assertEqual(first_response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(second_response.status_code, status.HTTP_200_OK)
        self.assertEqual(Payment.objects.count(), 1)

    def test_idempotency_conflict(self):
        idempotency_key = str(uuid.uuid4())
        first_payload = {
            "amount": "100.00",
            "currency": "BRL",
            "payment_method": "pix",
            "installments": 1,
            "splits": [
                {
                    "recipient_id": "seller_1",
                    "role": "seller",
                    "percent": "100.00",
                }
            ],
        }
        second_payload = {
            "amount": "101.00",
            "currency": "BRL",
            "payment_method": "pix",
            "installments": 1,
            "splits": [
                {
                    "recipient_id": "seller_1",
                    "role": "seller",
                    "percent": "100.00",
                }
            ],
        }

        first_response = self._post_payment(first_payload, idempotency_key=idempotency_key)
        second_response = self._post_payment(second_payload, idempotency_key=idempotency_key)

        self.assertEqual(first_response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(second_response.status_code, status.HTTP_409_CONFLICT)
        self.assertEqual(Payment.objects.count(), 1)

    def test_quote_does_not_persist(self):
        response = self._post_quote(
            {
                "amount": "100.00",
                "currency": "BRL",
                "payment_method": "card",
                "installments": 1,
                "splits": [
                    {
                        "recipient_id": "seller_1",
                        "role": "seller",
                        "percent": "100.00",
                    }
                ],
            }
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(Payment.objects.count(), 0)
        self.assertNotIn("payment_id", response.data)

    def test_split_max_recipients(self):
        response = self._post_payment(
            {
                "amount": "1000.00",
                "currency": "BRL",
                "payment_method": "pix",
                "installments": 1,
                "splits": [
                    {"recipient_id": "r1", "role": "producer", "percent": "30.00"},
                    {"recipient_id": "r2", "role": "affiliate", "percent": "25.00"},
                    {"recipient_id": "r3", "role": "coproducer", "percent": "20.00"},
                    {"recipient_id": "r4", "role": "manager", "percent": "15.00"},
                    {"recipient_id": "r5", "role": "closer", "percent": "10.00"},
                ],
            }
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(len(response.data["receivables"]), 5)
        receivables_total = sum(
            Decimal(receivable["amount"]) for receivable in response.data["receivables"]
        )
        self.assertEqual(receivables_total, Decimal(response.data["net_amount"]))

    def test_card_1x_fee_different_from_card_2x(self):
        one_installment_response = self._post_quote(
            {
                "amount": "1000.00",
                "currency": "BRL",
                "payment_method": "card",
                "installments": 1,
                "splits": [
                    {
                        "recipient_id": "seller_1",
                        "role": "seller",
                        "percent": "100.00",
                    }
                ],
            }
        )
        two_installments_response = self._post_quote(
            {
                "amount": "1000.00",
                "currency": "BRL",
                "payment_method": "card",
                "installments": 2,
                "splits": [
                    {
                        "recipient_id": "seller_1",
                        "role": "seller",
                        "percent": "100.00",
                    }
                ],
            }
        )

        self.assertEqual(one_installment_response.status_code, status.HTTP_200_OK)
        self.assertEqual(two_installments_response.status_code, status.HTTP_200_OK)
        self.assertEqual(one_installment_response.data["platform_fee_amount"], "39.90")
        self.assertEqual(two_installments_response.data["platform_fee_amount"], "69.90")
        self.assertNotEqual(
            one_installment_response.data["platform_fee_amount"],
            two_installments_response.data["platform_fee_amount"],
        )

    def _post_payment(self, payload: dict, idempotency_key: str | None = None):
        return self.client.post(
            self.payments_url,
            payload,
            format="json",
            HTTP_IDEMPOTENCY_KEY=idempotency_key or str(uuid.uuid4()),
        )

    def _post_quote(self, payload: dict):
        return self.client.post(
            "/api/v1/checkout/quote",
            payload,
            format="json",
        )
