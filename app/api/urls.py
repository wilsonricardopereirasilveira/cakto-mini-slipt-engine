from django.urls import path

from app.api.views import CheckoutQuoteView, PaymentCreateView


urlpatterns = [
    path("checkout/quote", CheckoutQuoteView.as_view(), name="checkout-quote"),
    path("payments", PaymentCreateView.as_view(), name="payment-create"),
]
