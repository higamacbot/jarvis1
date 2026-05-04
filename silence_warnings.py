"""Silence non-blocking FutureWarning/DeprecationWarning boot noise."""
import warnings
warnings.filterwarnings("ignore", category=FutureWarning)
warnings.filterwarnings("ignore", category=DeprecationWarning)
warnings.filterwarnings("ignore", category=PendingDeprecationWarning)
for mod in ("pandas","yfinance","websockets","websockets.legacy","alpaca_trade_api","httpx","urllib3","google"):
    warnings.filterwarnings("ignore", module=rf"^{mod}(\..*)?$")
try:
    from urllib3.exceptions import NotOpenSSLWarning
    warnings.filterwarnings("ignore", category=NotOpenSSLWarning)
except Exception:
    pass
