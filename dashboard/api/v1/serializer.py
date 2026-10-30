from rest_framework import serializers

from dashboard.models import Share


class ShareSerializer(serializers.ModelSerializer):
    class Meta:
        model = Share
        fields = (
            "id",
            "figi",
            "isin",
            "name",
            "ticker",
            "currency",
            "uid",
            "last_price",
            "is_trend_high",
            "created_at",
            "updated_at",
        )
        read_only_fields = (
            "id",
            "last_price",
            "is_trend_high",
            "created_at",
            "updated_at",
        )

    def validate_figi(self, value: str) -> str:
        return value.strip()

    def validate_uid(self, value: str) -> str:
        return value.strip()

    def validate_ticker(self, value: str) -> str:
        return value.strip().upper()

    def validate_currency(self, value: str) -> str:
        return value.strip().lower()
