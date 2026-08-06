# BingX API coverage ledger

Registry schema: `2`<br>
Contract source: `user-provided BingX endpoint contract in task prompt`<br>
Recorded: `2026-08-06`

This document is generated from `config/bingx-endpoints.yaml`. Run `python scripts/validate_bingx_registry.py --write` after registry changes. Rate-limit values are configurable application safety caps because the supplied contract does not provide exchange numeric limits. LIVE remains disabled.

## Totals

Total contracts: **47**. `DISABLED_SCHEMA`: **6**, `IMPLEMENTED`: **27**, `IMPLEMENTED_CONFIRMATION_GATED`: **1**, `IMPLEMENTED_DEMO_ONLY`: **1**, `IMPLEMENTED_GATED`: **6**, `IMPLEMENTED_REDUCTION_GATED`: **5**, `INTERNAL_ONLY`: **1**.

## Endpoint matrix

| Product | Module | Operation | Method | Path | Auth | Required | Optional | Rate scope/value | Status | Tests |
|---|---|---|---:|---|---|---|---|---|---|---|
| USDT_M_PERPETUAL | market_data | `server_time` | GET | `/openApi/swap/v2/server/time` | PUBLIC | — | — | market_data / configurable_application_limit | IMPLEMENTED | UNIT |
| USDT_M_PERPETUAL | market_data | `contracts` | GET | `/openApi/swap/v2/quote/contracts` | PUBLIC | — | `symbol` | market_data / configurable_application_limit | IMPLEMENTED | UNIT |
| USDT_M_PERPETUAL | market_data | `trading_rules` | GET | `/openApi/swap/v1/tradingRules` | SIGNED | `symbol`, `timestamp` | `recvWindow` | market_data / configurable_application_limit | IMPLEMENTED | UNIT_PENDING |
| USDT_M_PERPETUAL | market_data | `latest_price` | GET | `/openApi/swap/v2/quote/price` | PUBLIC | `timestamp` | `symbol` | market_data / configurable_application_limit | IMPLEMENTED | UNIT |
| USDT_M_PERPETUAL | market_data | `depth` | GET | `/openApi/swap/v2/quote/depth` | PUBLIC | `symbol`, `timestamp` | `limit` | market_data / configurable_application_limit | IMPLEMENTED | UNIT |
| USDT_M_PERPETUAL | market_data | `recent_trades` | GET | `/openApi/swap/v2/quote/trades` | PUBLIC | `symbol`, `timestamp` | `limit` | market_data / configurable_application_limit | IMPLEMENTED | UNIT_PENDING |
| USDT_M_PERPETUAL | market_data | `historical_trades` | GET | `/openApi/swap/v1/market/historicalTrades` | PUBLIC | `symbol`, `timestamp` | `limit`, `fromId` | market_data / configurable_application_limit | IMPLEMENTED | UNIT_PENDING |
| USDT_M_PERPETUAL | market_data | `klines` | GET | `/openApi/swap/v3/quote/klines` | PUBLIC | `symbol`, `interval`, `timestamp` | `startTime`, `endTime`, `limit` | market_data / configurable_application_limit | IMPLEMENTED | UNIT |
| USDT_M_PERPETUAL | market_data | `mark_price_klines` | GET | `/openApi/swap/v1/market/markPriceKlines` | PUBLIC | `symbol`, `interval`, `timestamp` | `startTime`, `endTime`, `limit` | market_data / configurable_application_limit | IMPLEMENTED | UNIT_PENDING |
| USDT_M_PERPETUAL | market_data | `premium_index` | GET | `/openApi/swap/v2/quote/premiumIndex` | PUBLIC | `timestamp` | `symbol` | market_data / configurable_application_limit | IMPLEMENTED | UNIT |
| USDT_M_PERPETUAL | market_data | `funding_rate_history` | GET | `/openApi/swap/v2/quote/fundingRate` | PUBLIC | `timestamp` | `symbol`, `startTime`, `endTime`, `limit` | market_data / configurable_application_limit | IMPLEMENTED | UNIT |
| USDT_M_PERPETUAL | market_data | `open_interest` | GET | `/openApi/swap/v2/quote/openInterest` | PUBLIC | `symbol`, `timestamp` | — | market_data / configurable_application_limit | IMPLEMENTED | UNIT |
| USDT_M_PERPETUAL | market_data | `ticker_24h` | GET | `/openApi/swap/v2/quote/ticker` | PUBLIC | `timestamp` | `symbol` | market_data / configurable_application_limit | IMPLEMENTED | UNIT_PENDING |
| USDT_M_PERPETUAL | market_data | `ticker_price` | GET | `/openApi/swap/v1/ticker/price` | PUBLIC | `timestamp` | `symbol` | market_data / configurable_application_limit | IMPLEMENTED | UNIT_PENDING |
| USDT_M_PERPETUAL | market_data | `book_ticker` | GET | `/openApi/swap/v2/quote/bookTicker` | PUBLIC | `symbol`, `timestamp` | — | market_data / configurable_application_limit | IMPLEMENTED | UNIT |
| USDT_M_PERPETUAL | account | `balance` | GET | `/openApi/swap/v2/user/balance` | SIGNED | `timestamp` | `recvWindow` | account / configurable_application_limit | IMPLEMENTED | UNIT |
| USDT_M_PERPETUAL | position | `positions` | GET | `/openApi/swap/v2/user/positions` | SIGNED | `timestamp` | `symbol`, `recvWindow` | position / configurable_application_limit | IMPLEMENTED | UNIT |
| USDT_M_PERPETUAL | account | `income` | GET | `/openApi/swap/v2/user/income` | SIGNED | `timestamp` | `symbol`, `incomeType`, `startTime`, `endTime`, `limit`, `recvWindow` | account / configurable_application_limit | IMPLEMENTED | UNIT_PENDING |
| USDT_M_PERPETUAL | account | `income_export` | GET | `/openApi/swap/v2/user/income/export` | SIGNED | `timestamp` | `recvWindow` | account / configurable_application_limit | INTERNAL_ONLY | UNIT_PENDING |
| USDT_M_PERPETUAL | account | `commission_rate` | GET | `/openApi/swap/v2/user/commissionRate` | SIGNED | `symbol`, `timestamp` | `recvWindow` | account / configurable_application_limit | IMPLEMENTED | UNIT |
| USDT_M_PERPETUAL | position_control | `get_position_mode` | GET | `/openApi/swap/v1/positionSide/dual` | SIGNED | `timestamp` | `recvWindow` | position_control / configurable_application_limit | IMPLEMENTED | UNIT_PENDING |
| USDT_M_PERPETUAL | position_control | `set_position_mode` | POST | `/openApi/swap/v1/positionSide/dual` | SIGNED_TRADE | `dualSidePosition`, `timestamp` | `recvWindow` | position_control / configurable_application_limit | IMPLEMENTED_GATED | UNIT_PENDING |
| USDT_M_PERPETUAL | position_control | `get_margin_type` | GET | `/openApi/swap/v2/trade/marginType` | SIGNED | `symbol`, `timestamp` | `recvWindow` | position_control / configurable_application_limit | IMPLEMENTED | UNIT_PENDING |
| USDT_M_PERPETUAL | position_control | `set_margin_type` | POST | `/openApi/swap/v2/trade/marginType` | SIGNED_TRADE | `symbol`, `marginType`, `timestamp` | `recvWindow` | position_control / configurable_application_limit | IMPLEMENTED_GATED | UNIT_PENDING |
| USDT_M_PERPETUAL | position_control | `get_leverage` | GET | `/openApi/swap/v2/trade/leverage` | SIGNED | `symbol`, `timestamp` | `recvWindow` | position_control / configurable_application_limit | IMPLEMENTED | UNIT_PENDING |
| USDT_M_PERPETUAL | position_control | `set_leverage` | POST | `/openApi/swap/v2/trade/leverage` | SIGNED_TRADE | `symbol`, `side`, `leverage`, `timestamp` | `recvWindow` | position_control / configurable_application_limit | IMPLEMENTED_GATED | UNIT_PENDING |
| USDT_M_PERPETUAL | order | `test_order` | POST | `/openApi/swap/v2/trade/order/test` | SIGNED_TRADE | `symbol`, `side`, `positionSide`, `type`, `timestamp` | `quantity`, `price`, `stopPrice`, `timeInForce`, `reduceOnly`, `clientOrderID`, `workingType`, `priceProtect`, `closePosition`, `takeProfit`, `stopLoss`, `recvWindow` | order / configurable_application_limit | IMPLEMENTED_DEMO_ONLY | MOCK_TEST_ENDPOINT |
| USDT_M_PERPETUAL | order | `place_order` | POST | `/openApi/swap/v2/trade/order` | SIGNED_TRADE | `symbol`, `side`, `positionSide`, `type`, `timestamp` | `quantity`, `price`, `stopPrice`, `timeInForce`, `reduceOnly`, `clientOrderID`, `workingType`, `priceProtect`, `closePosition`, `takeProfit`, `stopLoss`, `recvWindow` | order / configurable_application_limit | IMPLEMENTED_GATED | MOCK_TRANSPORT_NO_LIVE |
| USDT_M_PERPETUAL | order | `query_order` | GET | `/openApi/swap/v2/trade/order` | SIGNED | `timestamp` | `symbol`, `orderId`, `clientOrderID`, `recvWindow` | order / configurable_application_limit | IMPLEMENTED | UNIT |
| USDT_M_PERPETUAL | cancellation | `cancel_order` | DELETE | `/openApi/swap/v2/trade/order` | SIGNED_TRADE | `symbol`, `timestamp` | `orderId`, `clientOrderID`, `recvWindow` | cancellation / configurable_application_limit | IMPLEMENTED_REDUCTION_GATED | UNIT |
| USDT_M_PERPETUAL | order | `batch_place` | POST | `/openApi/swap/v2/trade/batchOrders` | SIGNED_TRADE | `batchOrders`, `timestamp` | `recvWindow` | order / configurable_application_limit | IMPLEMENTED_GATED | UNIT |
| USDT_M_PERPETUAL | cancellation | `batch_cancel` | DELETE | `/openApi/swap/v2/trade/batchOrders` | SIGNED_TRADE | `symbol`, `timestamp` | `orderIdList`, `clientOrderIdList`, `recvWindow` | cancellation / configurable_application_limit | IMPLEMENTED_REDUCTION_GATED | UNIT_PENDING |
| USDT_M_PERPETUAL | order | `open_orders` | GET | `/openApi/swap/v2/trade/openOrders` | SIGNED | `timestamp` | `symbol`, `recvWindow` | order / configurable_application_limit | IMPLEMENTED | UNIT |
| USDT_M_PERPETUAL | order | `order_history` | GET | `/openApi/swap/v2/trade/allOrders` | SIGNED | `timestamp` | `symbol`, `orderId`, `startTime`, `endTime`, `limit`, `recvWindow` | order / configurable_application_limit | IMPLEMENTED | UNIT |
| USDT_M_PERPETUAL | order | `fills` | GET | `/openApi/swap/v2/trade/allFillOrders` | SIGNED | `timestamp` | `symbol`, `orderId`, `startTime`, `endTime`, `limit`, `recvWindow` | order / configurable_application_limit | IMPLEMENTED | UNIT |
| USDT_M_PERPETUAL | cancellation | `cancel_all` | DELETE | `/openApi/swap/v2/trade/allOpenOrders` | SIGNED_TRADE | `timestamp` | `symbol`, `recvWindow` | cancellation / configurable_application_limit | IMPLEMENTED_REDUCTION_GATED | UNIT_PENDING |
| USDT_M_PERPETUAL | position_control | `close_all_positions` | POST | `/openApi/swap/v2/trade/closeAllPositions` | SIGNED_TRADE | `timestamp` | `recvWindow` | position_control / configurable_application_limit | IMPLEMENTED_CONFIRMATION_GATED | UNIT_PENDING |
| USDT_M_PERPETUAL | position_control | `close_position` | POST | `/openApi/swap/v1/trade/closePosition` | SIGNED_TRADE | `positionId`, `timestamp` | `recvWindow` | position_control / configurable_application_limit | IMPLEMENTED_REDUCTION_GATED | UNIT_PENDING |
| USDT_M_PERPETUAL | order | `cancel_replace` | POST | `/openApi/swap/v1/trade/cancelReplace` | SIGNED_TRADE | `timestamp` | `schema_not_supplied` | order / configurable_application_limit | DISABLED_SCHEMA | NONE |
| USDT_M_PERPETUAL | order | `batch_cancel_replace` | POST | `/openApi/swap/v1/trade/batchCancelReplace` | SIGNED_TRADE | `timestamp` | `schema_not_supplied` | order / configurable_application_limit | DISABLED_SCHEMA | NONE |
| USDT_M_PERPETUAL | cancellation | `cancel_all_after` | POST | `/openApi/swap/v2/trade/cancelAllAfter` | SIGNED_TRADE | `countdownTime`, `timestamp` | `recvWindow` | cancellation / configurable_application_limit | IMPLEMENTED_REDUCTION_GATED | UNIT_PENDING |
| USDT_M_PERPETUAL | position_control | `position_margin` | POST | `/openApi/swap/v2/trade/positionMargin` | SIGNED_TRADE | `symbol`, `positionSide`, `amount`, `type`, `timestamp` | `recvWindow` | position_control / configurable_application_limit | IMPLEMENTED_GATED | UNIT_PENDING |
| USDT_M_PERPETUAL | account | `force_orders` | GET | `/openApi/swap/v2/trade/forceOrders` | SIGNED | `timestamp` | `symbol`, `recvWindow` | account / configurable_application_limit | IMPLEMENTED | UNIT_PENDING |
| USDT_M_PERPETUAL | copy_trading | `copy_current_track` | GET | `/openApi/copyTrading/v1/swap/trace/currentTrack` | SIGNED | `timestamp` | `schema_not_supplied` | copy_trading / configurable_application_limit | DISABLED_SCHEMA | ERROR_TEST |
| USDT_M_PERPETUAL | copy_trading | `copy_close_track` | POST | `/openApi/copyTrading/v1/swap/trace/closeTrackOrder` | SIGNED_TRADE | `timestamp` | `schema_not_supplied` | copy_trading / configurable_application_limit | DISABLED_SCHEMA | ERROR_TEST |
| USDT_M_PERPETUAL | copy_trading | `copy_set_tpsl` | POST | `/openApi/copyTrading/v1/swap/trace/setTPSL` | SIGNED_TRADE | `timestamp` | `schema_not_supplied` | copy_trading / configurable_application_limit | DISABLED_SCHEMA | ERROR_TEST |
| SPOT | spot_copy_trading | `spot_copy_sell` | POST | `/openApi/copyTrading/v1/spot/trader/sellOrder` | SIGNED_TRADE | `timestamp` | `schema_not_supplied` | spot_copy_trading / configurable_application_limit | DISABLED_SCHEMA | ERROR_TEST |

## Deliberately disabled operations

Cancel/replace and optional official copy-trading operations remain `DISABLED_SCHEMA` because the supplied contract gives endpoint paths but not complete request/response fields. Their methods fail closed rather than inventing fields. Withdrawals are prohibited and are not present in the registry or code.

## Remaining controlled-demo gates

- Add sanitized parser fixtures for entries marked `UNIT_PENDING`.
- Configure and review application rate caps for each deployment; supplied contracts contain no numeric exchange limits.
- Configure public/private WebSocket URLs and subscription payloads; unverified private subscriptions remain disabled.
- Apply migration `0004_bingx_execution_records`, complete startup reconciliation, and run the non-trading certification report.
- Enable the test-order endpoint only with an explicit DEMO flag. Automated tests never contact BingX.
- Perform controlled BingX DEMO verification before considering any order mutation.
