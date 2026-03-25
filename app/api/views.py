import hashlib
import json

from django.db import transaction
from django.db.utils import IntegrityError
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from app.api.serializers import PaymentInputSerializer
from app.models import LedgerEntry, OutboxEvent, Payment
from app.services.split_calculator import calculate


class CheckoutQuoteView(APIView):
    def post(self, request):
        serializer = PaymentInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            result = calculate(**_build_calculation_input(serializer.validated_data))
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        return Response(_serialize_calculation(result), status=status.HTTP_200_OK)


class PaymentCreateView(APIView):
    def post(self, request):
        idempotency_key = request.headers.get("Idempotency-Key")
        if not idempotency_key:
            return Response(
                {"detail": "Idempotency-Key header is required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        payload_hash = hashlib.sha256(
            json.dumps(request.data, sort_keys=True).encode("utf-8")
        ).hexdigest()

        serializer = PaymentInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        payment = (
            Payment.objects.filter(idempotency_key=idempotency_key)
            .prefetch_related("ledger_entries", "outbox_events")
            .first()
        )
        if payment:
            if payment.idempotency_payload_hash != payload_hash:
                return Response(
                    {"detail": "Idempotency-Key conflict: payload differs from original request"},
                    status=status.HTTP_409_CONFLICT,
                )
            return Response(_serialize_payment(payment), status=status.HTTP_200_OK)

        try:
            calculation = calculate(**_build_calculation_input(serializer.validated_data))
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        try:
            with transaction.atomic():
                payment = (
                    Payment.objects.select_for_update()
                    .filter(idempotency_key=idempotency_key)
                    .prefetch_related("ledger_entries", "outbox_events")
                    .first()
                )
                if payment:
                    if payment.idempotency_payload_hash != payload_hash:
                        return Response(
                            {"detail": "Idempotency-Key conflict: payload differs from original request"},
                            status=status.HTTP_409_CONFLICT,
                        )
                    return Response(_serialize_payment(payment), status=status.HTTP_200_OK)

                payment = Payment.objects.create(
                    idempotency_key=idempotency_key,
                    idempotency_payload_hash=payload_hash,
                    gross_amount=calculation["gross_amount"],
                    platform_fee_amount=calculation["platform_fee_amount"],
                    net_amount=calculation["net_amount"],
                    payment_method=serializer.validated_data["payment_method"],
                    installments=serializer.validated_data["installments"],
                    currency=serializer.validated_data["currency"],
                )

                LedgerEntry.objects.bulk_create(
                    [
                        LedgerEntry(
                            payment=payment,
                            recipient_id=receivable["recipient_id"],
                            role=receivable["role"],
                            amount=receivable["amount"],
                        )
                        for receivable in calculation["receivables"]
                    ]
                )

                outbox_event = OutboxEvent.objects.create(
                    payment=payment,
                    payload={
                        "payment_id": str(payment.id),
                        "receivables": [
                            {
                                "recipient_id": receivable["recipient_id"],
                                "role": receivable["role"],
                                "amount": str(receivable["amount"]),
                            }
                            for receivable in calculation["receivables"]
                        ],
                    },
                )
        except IntegrityError:
            payment = (
                Payment.objects.filter(idempotency_key=idempotency_key)
                .prefetch_related("ledger_entries", "outbox_events")
                .first()
            )
            if payment and payment.idempotency_payload_hash == payload_hash:
                return Response(_serialize_payment(payment), status=status.HTTP_200_OK)
            return Response(
                {"detail": "Idempotency-Key conflict: payload differs from original request"},
                status=status.HTTP_409_CONFLICT,
            )

        return Response(
            _serialize_payment(
                payment,
                receivables=calculation["receivables"],
                outbox_event=outbox_event,
            ),
            status=status.HTTP_201_CREATED,
        )


def _build_calculation_input(validated_data: dict) -> dict:
    return {
        "amount": validated_data["amount"],
        "payment_method": validated_data["payment_method"],
        "installments": validated_data["installments"],
        "splits": validated_data["splits"],
    }


def _serialize_calculation(calculation: dict) -> dict:
    return {
        "gross_amount": _format_money(calculation["gross_amount"]),
        "platform_fee_amount": _format_money(calculation["platform_fee_amount"]),
        "net_amount": _format_money(calculation["net_amount"]),
        "receivables": [
            {
                "recipient_id": receivable["recipient_id"],
                "role": receivable["role"],
                "amount": _format_money(receivable["amount"]),
            }
            for receivable in calculation["receivables"]
        ],
    }


def _serialize_payment(payment: Payment, receivables=None, outbox_event: OutboxEvent | None = None) -> dict:
    if receivables is None:
        receivables = [
            {
                "recipient_id": entry.recipient_id,
                "role": entry.role,
                "amount": entry.amount,
            }
            for entry in payment.ledger_entries.order_by("created_at", "id")
        ]

    if outbox_event is None:
        outbox_event = payment.outbox_events.order_by("created_at", "id").first()

    return {
        "payment_id": str(payment.id),
        "status": payment.status,
        "gross_amount": _format_money(payment.gross_amount),
        "platform_fee_amount": _format_money(payment.platform_fee_amount),
        "net_amount": _format_money(payment.net_amount),
        "receivables": [
            {
                "recipient_id": receivable["recipient_id"],
                "role": receivable["role"],
                "amount": _format_money(receivable["amount"]),
            }
            for receivable in receivables
        ],
        "outbox_event": {
            "type": outbox_event.type,
            "status": outbox_event.status,
        }
        if outbox_event
        else None,
    }


def _format_money(value) -> str:
    return f"{value:.2f}"
