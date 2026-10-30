from django import forms

from .models import PriceAlert, Share, WatchlistItem


class ShareModelForm(forms.ModelForm):
    """Инструмент"""

    class Meta:
        model = Share
        fields = "__all__"


class WatchlistItemForm(forms.ModelForm):
    class Meta:
        model = WatchlistItem
        fields = ("share",)

    def __init__(self, *args, user, **kwargs):
        super().__init__(*args, **kwargs)
        existing_shares = WatchlistItem.objects.filter(user=user).values("share_id")
        self.fields["share"].queryset = Share.objects.exclude(
            pk__in=existing_shares
        ).order_by("name")


class PriceAlertForm(forms.ModelForm):
    class Meta:
        model = PriceAlert
        fields = ("target_price",)
        widgets = {
            "target_price": forms.NumberInput(
                attrs={"min": "0.00000001", "step": "0.00000001"}
            )
        }

    def __init__(self, *args, watchlist_item, **kwargs):
        super().__init__(*args, **kwargs)
        self.watchlist_item = watchlist_item

    def clean_target_price(self):
        target_price = self.cleaned_data["target_price"]
        if target_price <= 0:
            raise forms.ValidationError("Целевая цена должна быть больше нуля.")
        if PriceAlert.objects.filter(
            watchlist_item=self.watchlist_item, target_price=target_price
        ).exists():
            raise forms.ValidationError("Для этой целевой цены оповещение уже создано.")
        return target_price
