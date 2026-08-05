import hashlib, hmac, time
from decimal import Decimal
from urllib.parse import urlencode
import httpx
from app.exchanges.interfaces import OrderRequest, OrderResult, SymbolMetadata


class BingXSigner:
    @staticmethod
    def canonical_query(params: dict[str, object]) -> str:
        return urlencode(sorted((k, str(v)) for k, v in params.items() if v is not None))

    @staticmethod
    def sign(secret: str, canonical_query: str) -> str:
        return hmac.new(secret.encode(), canonical_query.encode(), hashlib.sha256).hexdigest()


class BingXClient:
    # Official docs referenced: https://bingx-api.github.io/docs/#/swapV2/authentication.html#Signature
    def __init__(self, base_url: str, api_key: str, api_secret: str, timeout: float = 10) -> None:
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.api_secret = api_secret
        self.http = httpx.AsyncClient(timeout=timeout)

    async def _signed(self, method: str, path: str, params: dict[str, object]) -> dict[str, object]:
        params = {**params, "timestamp": int(time.time() * 1000)}
        qs = BingXSigner.canonical_query(params)
        sig = BingXSigner.sign(self.api_secret, qs)
        r = await self.http.request(
            method, f"{self.base_url}{path}", params={**params, "signature": sig}, headers={"X-BX-APIKEY": self.api_key}
        )
        r.raise_for_status()
        return r.json()

    async def symbol_metadata(self, symbol: str) -> SymbolMetadata:
        data = await self._signed("GET", "/openApi/swap/v2/quote/contracts", {})
        for item in data.get("data", []):
            if item.get("symbol") == symbol:
                return SymbolMetadata(
                    symbol=symbol,
                    min_quantity=Decimal(str(item.get("minQty", "0.001"))),
                    quantity_step=Decimal(str(item.get("quantityPrecision", "0.001"))),
                    tick_size=Decimal(str(item.get("pricePrecision", "0.1"))),
                    min_notional=Decimal(str(item.get("minNotional", "5"))),
                )
        raise ValueError("symbol metadata not found")

    async def submit_order(self, request: OrderRequest) -> OrderResult:
        raise NotImplementedError("BingX live order submission is intentionally gated pending certification")
