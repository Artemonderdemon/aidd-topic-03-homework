from django import forms

from .models import Share


class ShareModelForm(forms.ModelForm):
    """Form for manually adding or editing a share.

    Price and trend are calculated by the background task and are therefore
    intentionally excluded from the user-editable form.
    """

    class Meta:
        model = Share
        fields = ("figi", "isin", "name", "ticker", "currency", "uid")
        widgets = {
            "figi": forms.TextInput(
                attrs={"class": "form-control", "placeholder": "BBG..."}
            ),
            "isin": forms.TextInput(
                attrs={"class": "form-control", "placeholder": "RU..."}
            ),
            "name": forms.TextInput(attrs={"class": "form-control"}),
            "ticker": forms.TextInput(
                attrs={"class": "form-control", "placeholder": "SBER"}
            ),
            "currency": forms.TextInput(
                attrs={"class": "form-control", "placeholder": "rub"}
            ),
            "uid": forms.TextInput(attrs={"class": "form-control"}),
        }

    def clean_ticker(self):
        return self.cleaned_data["ticker"].strip().upper()

    def clean_currency(self):
        return self.cleaned_data["currency"].strip().lower()

    def clean_figi(self):
        return self.cleaned_data["figi"].strip()

    def clean_uid(self):
        return self.cleaned_data["uid"].strip()


from django.contrib.auth import get_user_model

from .models import Portfolio, Strategy, Trade, WatchlistItem


class WatchlistItemForm(forms.ModelForm):
    class Meta:
        model = WatchlistItem
        fields = ("share", "target_price", "condition", "is_active")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["share"].queryset = Share.objects.order_by("ticker")
        for field in self.fields.values():
            field.widget.attrs.setdefault("class", "form-control")


class PortfolioForm(forms.ModelForm):
    class Meta:
        model = Portfolio
        fields = ("name", "description", "cash_balance")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs.setdefault("class", "form-control")


class TradeForm(forms.Form):
    share = forms.ModelChoiceField(
        queryset=Share.objects.order_by("ticker"),
        widget=forms.Select(attrs={"class": "form-select"}),
    )
    side = forms.ChoiceField(
        choices=Trade.SIDE_CHOICES, widget=forms.Select(attrs={"class": "form-select"})
    )
    quantity = forms.DecimalField(
        min_value=0.000001, widget=forms.NumberInput(attrs={"class": "form-control"})
    )
    price = forms.DecimalField(
        min_value=0.000000001,
        widget=forms.NumberInput(attrs={"class": "form-control", "step": "0.000000001"}),
    )


class StrategyForm(forms.ModelForm):
    class Meta:
        model = Strategy
        fields = (
            "portfolio",
            "share",
            "name",
            "condition",
            "threshold",
            "action",
            "quantity",
            "is_active",
        )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs.setdefault("class", "form-control")
