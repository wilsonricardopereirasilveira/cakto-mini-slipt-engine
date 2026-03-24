from django.http import Http404
from django.urls import include, path


def root_not_found(_request):
    raise Http404("Not Found")


urlpatterns = [
    path("api/v1/", include("app.api.urls")),
    path("", root_not_found),
]
