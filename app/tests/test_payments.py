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

    def _post_payment(self, payload: dict, idempotency_key: str | None = None):
        return self.client.post(
            self.payments_url,
            payload,
            format="json",
            HTTP_IDEMPOTENCY_KEY=idempotency_key or str(uuid.uuid4()),
        )
