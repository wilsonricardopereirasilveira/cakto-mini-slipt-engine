from decimal import Decimal

from rest_framework import serializers


class SplitInputSerializer(serializers.Serializer):
    recipient_id = serializers.CharField()
    role = serializers.CharField()
    percent = serializers.DecimalField(max_digits=5, decimal_places=2)

    def validate_percent(self, value: Decimal) -> Decimal:
        if value <= Decimal("0"):
            raise serializers.ValidationError("percent must be greater than 0")
        if value > Decimal("100"):
            raise serializers.ValidationError("percent must be less than or equal to 100")
        return value


class PaymentInputSerializer(serializers.Serializer):
    amount = serializers.DecimalField(max_digits=12, decimal_places=2)
    currency = serializers.CharField(default="BRL")
    payment_method = serializers.ChoiceField(choices=["pix", "card"])
    installments = serializers.IntegerField(default=1)
    splits = SplitInputSerializer(many=True)

    def validate_currency(self, value: str) -> str:
        if value != "BRL":
            raise serializers.ValidationError("currency must be BRL")
        return value

    def validate(self, attrs: dict) -> dict:
        amount = attrs["amount"]
        payment_method = attrs["payment_method"]
        installments = attrs["installments"]
        splits = attrs["splits"]

        if amount <= Decimal("0"):
            raise serializers.ValidationError({"amount": "amount must be greater than 0"})

        if payment_method == "pix" and installments != 1:
            raise serializers.ValidationError(
                {"installments": "pix payments must have exactly 1 installment"}
            )

        if payment_method == "card" and not 1 <= installments <= 12:
            raise serializers.ValidationError(
                {"installments": "card installments must be between 1 and 12"}
            )

        if not 1 <= len(splits) <= 5:
            raise serializers.ValidationError(
                {"splits": "splits must contain between 1 and 5 recipients"}
            )

        total_percent = sum((split["percent"] for split in splits), Decimal("0"))
        if total_percent != Decimal("100"):
            raise serializers.ValidationError({"splits": "split percentages must sum exactly to 100"})

        return attrs
