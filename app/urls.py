from django.http import Http404
from django.urls import path


def root_not_found(_request):
    raise Http404("Not Found")


urlpatterns = [
    path("", root_not_found),
]
