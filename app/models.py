import uuid

from django.db import models


class Payment(models.Model):
    STATUS_CAPTURED = "captured"
    PAYMENT_METHOD_PIX = "pix"
    PAYMENT_METHOD_CARD = "card"

    PAYMENT_METHOD_CHOICES = [
        (PAYMENT_METHOD_PIX, "PIX"),
        (PAYMENT_METHOD_CARD, "Card"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    idempotency_key = models.CharField(max_length=255, unique=True, db_index=True)
    idempotency_payload_hash = models.CharField(max_length=64)
    status = models.CharField(max_length=20, default=STATUS_CAPTURED, editable=False)
    gross_amount = models.DecimalField(max_digits=12, decimal_places=2)
    platform_fee_amount = models.DecimalField(max_digits=12, decimal_places=2)
    net_amount = models.DecimalField(max_digits=12, decimal_places=2)
    payment_method = models.CharField(max_length=10, choices=PAYMENT_METHOD_CHOICES)
    installments = models.IntegerField(default=1)
    currency = models.CharField(max_length=3, default="BRL")
    created_at = models.DateTimeField(auto_now_add=True)


class LedgerEntry(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    payment = models.ForeignKey(
        Payment,
        on_delete=models.CASCADE,
        related_name="ledger_entries",
    )
    recipient_id = models.CharField(max_length=255)
    role = models.CharField(max_length=50)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    created_at = models.DateTimeField(auto_now_add=True)


class OutboxEvent(models.Model):
    TYPE_PAYMENT_CAPTURED = "payment_captured"
    STATUS_PENDING = "pending"
    STATUS_PUBLISHED = "published"

    STATUS_CHOICES = [
        (STATUS_PENDING, "Pending"),
        (STATUS_PUBLISHED, "Published"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    payment = models.ForeignKey(
        Payment,
        on_delete=models.CASCADE,
        related_name="outbox_events",
    )
    type = models.CharField(
        max_length=100,
        default=TYPE_PAYMENT_CAPTURED,
        editable=False,
    )
    payload = models.JSONField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_PENDING)
    created_at = models.DateTimeField(auto_now_add=True)
    published_at = models.DateTimeField(null=True, blank=True)
