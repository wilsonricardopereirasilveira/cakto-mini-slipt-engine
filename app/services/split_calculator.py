from decimal import Decimal, ROUND_HALF_DOWN, ROUND_HALF_UP


TWOPLACES = Decimal("0.01")
ONE_HUNDRED = Decimal("100")
PIX = "pix"
CARD = "card"


def calculate(amount: Decimal, payment_method: str, installments: int, splits: list[dict]) -> dict:
    gross_amount = _to_decimal(amount, "amount")
    if gross_amount <= Decimal("0"):
        raise ValueError("amount must be greater than 0")

    method = str(payment_method).strip().lower()
    fee_rate = _get_fee_rate(method, installments)
    validated_splits = _validate_splits(splits)

    platform_fee_amount = (gross_amount * fee_rate).quantize(TWOPLACES, rounding=ROUND_HALF_UP)
    net_amount = gross_amount - platform_fee_amount

    receivables = []
    distributed_amount = Decimal("0")

    for split in validated_splits:
        receivable_amount = (
            net_amount * split["percent"] / ONE_HUNDRED
        ).quantize(TWOPLACES, rounding=ROUND_HALF_DOWN)
        distributed_amount += receivable_amount
        receivables.append(
            {
                "recipient_id": split["recipient_id"],
                "role": split["role"],
                "amount": receivable_amount,
            }
        )

    residue = net_amount - distributed_amount
    receivables[0]["amount"] += residue

    return {
        "gross_amount": gross_amount,
        "platform_fee_amount": platform_fee_amount,
        "net_amount": net_amount,
        "receivables": receivables,
    }


def _get_fee_rate(payment_method: str, installments: int) -> Decimal:
    if payment_method == PIX:
        if installments != 1:
            raise ValueError("pix payments must have exactly 1 installment")
        return Decimal("0")

    if payment_method != CARD:
        raise ValueError("payment_method must be 'pix' or 'card'")

    if installments < 1 or installments > 12:
        raise ValueError("card installments must be between 1 and 12")

    if installments == 1:
        return Decimal("0.0399")

    return Decimal("0.0499") + (Decimal("0.02") * Decimal(installments - 1))


def _validate_splits(splits: list[dict]) -> list[dict]:
    if not splits:
        raise ValueError("splits must contain at least one recipient")

    validated_splits = []
    total_percent = Decimal("0")

    for index, split in enumerate(splits):
        if not isinstance(split, dict):
            raise ValueError(f"split at index {index} must be a dict")

        recipient_id = split.get("recipient_id")
        role = split.get("role")
        if not recipient_id:
            raise ValueError(f"split at index {index} must include recipient_id")
        if not role:
            raise ValueError(f"split at index {index} must include role")
        if "percent" not in split:
            raise ValueError(f"split at index {index} must include percent")

        percent = _to_decimal(split["percent"], f"split percent at index {index}")
        if percent <= Decimal("0"):
            raise ValueError(f"split percent at index {index} must be greater than 0")

        total_percent += percent
        validated_splits.append(
            {
                "recipient_id": str(recipient_id),
                "role": str(role),
                "percent": percent,
            }
        )

    if total_percent != ONE_HUNDRED:
        raise ValueError("split percentages must sum exactly to 100")

    return validated_splits


def _to_decimal(value: Decimal, field_name: str) -> Decimal:
    if isinstance(value, Decimal):
        return value

    try:
        return Decimal(str(value))
    except Exception as exc:
        raise ValueError(f"{field_name} must be a valid decimal value") from exc
