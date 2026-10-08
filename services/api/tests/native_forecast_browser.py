"""Built forecast panel uses the same owned preview and private browser controls."""

from native_intelligence_browser import run_native_browser


def run_forecast_browser(*, items, **kwargs):
    return run_native_browser(
        cases=[{"items": items}], project="native-forecast-chromium", **kwargs
    )
