"""Plotly graph rendering for a share."""

from __future__ import annotations

import plotly.graph_objects as go
import plotly.io as pio

from dashboard.services.market_data import (
    MarketDataProvider,
    get_market_data_provider,
)


def get_graph(share, provider: MarketDataProvider | None = None) -> str:
    """Return an HTML fragment with a daily price chart for ``share``."""
    owns_provider = provider is None
    provider = provider or get_market_data_provider()
    try:
        candles = provider.get_daily_candles(share.figi, days=180)
    finally:
        if owns_provider:
            provider.close()

    if not candles:
        return ""

    figure = go.Figure(
        data=[
            go.Scatter(
                x=[candle.time for candle in candles],
                y=[float(candle.close) for candle in candles],
                mode="lines",
                name=share.ticker,
                line={"color": "#0d6efd", "width": 2},
                hovertemplate="%{x|%d.%m.%Y}<br>%{y:.2f} "
                f"{share.currency}<extra></extra>",
            )
        ]
    )
    figure.update_layout(
        template="plotly_white",
        height=420,
        margin={"l": 20, "r": 20, "t": 30, "b": 20},
        xaxis_title="Дата",
        yaxis_title=f"Цена, {share.currency}",
        hovermode="x unified",
        showlegend=False,
    )
    return pio.to_html(
        figure,
        include_plotlyjs="cdn",
        full_html=False,
        config={"displayModeBar": False, "responsive": True},
    )
