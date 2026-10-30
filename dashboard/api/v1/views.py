from django_filters import rest_framework as filters
from rest_framework import viewsets
from rest_framework.filters import OrderingFilter, SearchFilter
from rest_framework.permissions import IsAuthenticatedOrReadOnly

from dashboard.models import Share

from .serializer import ShareSerializer


class ShareFilter(filters.FilterSet):
    class Meta:
        model = Share
        fields = ("name", "ticker", "currency", "is_trend_high")


class ShareViewSet(viewsets.ModelViewSet):
    """CRUD API for shares.

    Read operations are public; write operations require authentication.
    """

    serializer_class = ShareSerializer
    queryset = Share.objects.all()
    permission_classes = (IsAuthenticatedOrReadOnly,)
    filter_backends = (OrderingFilter, filters.DjangoFilterBackend, SearchFilter)
    filterset_class = ShareFilter
    ordering_fields = ("name", "ticker", "last_price", "updated_at")
    ordering = ("name",)
    search_fields = ("$name", "$ticker")
