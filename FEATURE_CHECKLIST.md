# FEATURE CHECKLIST

| Feature | Backend | Mock mode | Live mode path | Dashboard | Tests | Docs |
|---|---:|---:|---:|---:|---:|---:|
| ExchangeAdapter interface | ✅ | ✅ | ✅ gated | n/a | ⚠️ partial | ✅ |
| MarketDataProvider interface | ✅ | ✅ | ✅ gated | ✅ | ⚠️ partial | ✅ |
| OrderExecutor interface | ✅ | ✅ | ✅ gated | ✅ | ⚠️ partial | ✅ |
| PositionManager interface | ✅ | ✅ | ✅ gated | ✅ | ⚠️ partial | ✅ |
| CopySignalProvider interface | ✅ | ✅ | ✅ external path | ✅ | ⚠️ partial | ✅ |
| NotificationProvider interface | ✅ | ✅ preview | ✅ gated | ✅ | ⚠️ partial | ✅ |
| StorageProvider interface | ✅ | ✅ in-memory | ✅ database path | ✅ | ⚠️ partial | ✅ |
| RiskManager interface | ✅ | ✅ | ✅ shared path | ✅ | ⚠️ partial | ✅ |
| StrategyEngine interface | ✅ | ✅ | ✅ shared path | ✅ | ⚠️ partial | ✅ |
| Mock BingX balance | ✅ | ✅ | n/a | ✅ | ⚠️ partial | ✅ |
| Mock market prices/candles/order book | ✅ | ✅ | n/a | ✅ | ⚠️ partial | ✅ |
| Mock volume spikes/breakouts | ✅ | ✅ | n/a | ✅ | ⚠️ partial | ✅ |
| Mock lead-trader signals | ✅ | ✅ | n/a | ✅ | ⚠️ partial | ✅ |
| Mock order fills/positions | ✅ | ✅ | n/a | ✅ | ⚠️ partial | ✅ |
| Stop-loss/take-profit simulation | ✅ | ✅ | ✅ design path | ✅ | ⚠️ partial | ✅ |
| Daily-loss and spread risk rejections | ✅ | ✅ | ✅ shared path | ✅ | ⚠️ partial | ✅ |
| Emergency close-all | ✅ | ✅ | ✅ shared path | ✅ | ⚠️ partial | ✅ |
| Telegram/email notification preview | ✅ | ✅ preview | ✅ provider path | ✅ | ⚠️ partial | ✅ |
| Reports | ✅ | ✅ | ✅ storage path | ✅ | ⚠️ partial | ✅ |
| Dashboard controls connected to backend | ✅ | ✅ | ✅ gated | ✅ | ⚠️ partial | ✅ |

Legend: ✅ implemented for this scaffold/MVP; ⚠️ partial automated coverage because dependency installation is blocked in this environment. Production-live certification remains outstanding.
