# Advanced Financial Analysis System

一個完整的金融分析和自動化交易系統，整合了市場資料收集、AI 趨勢預測、即時監控和自動化交易功能。

## 主要功能

### 1. 即時市場監控 (Real-time Monitoring)
- **價格告警**: 設定價格突破、跌破或大幅波動的告警
- **趨勢監控**: 監控市場趨勢變化
- **新聞情緒分析**: 自動分析新聞對市場的影響
- **WebSocket 即時更新**: 提供即時資料串流

### 2. AI 趨勢預測 (AI Trend Prediction)
- **機器學習模型**: 使用隨機森林和梯度提升演算法
- **多因子分析**: 整合技術指標、市場寬度和波動率
- **市場狀態分類**: 識別牛市、熊市、盤整和高波動期
- **預測報告**: 生成詳細的趨勢分析報告

### 3. 自動化交易 (Automated Trading)
- **多策略支援**: 趨勢跟隨、均值回歸、突破策略
- **風險管理**: 停損停利、倉位控制、每日損益限制
- **即時執行**: 根據市場條件自動進出場
- **績效追蹤**: 詳細的交易記錄和績效分析

### 4. 整合系統架構
- **模組化設計**: 各組件獨立運作，可靈活配置
- **統一介面**: 命令列工具整合所有功能
- **日誌系統**: 完整的系統日誌和錯誤追蹤
- **設定管理**: 靈活的設定檔案管理

## 系統架構

```
financial_system/
├── config.py              # 系統設定管理
├── market.py              # 市場資料收集
├── llm.py                 # AI 分析和報告生成
├── realtime_monitor.py    # 即時監控系統
├── trend_predictor.py     # AI 趨勢預測
├── automated_trader.py    # 自動化交易
├── main.py                # 系統整合和命令介面
└── database.py            # 資料庫操作 (待實現)

gas_sync/
├── google_sheets_sync.py  # Google Sheets API 同步核心
├── gas_sync_service.py    # 獨立同步服務
├── setup_sheets.py        # 設定協助工具
└── README.md              # 詳細設定指南
```

### 5. Google Sheets 即時同步 (GAS Sync)
- **即時資料同步**: 市場資料自動同步到 Google Sheets
- **告警記錄**: 即時告警自動記錄到試算表
- **投資組合追蹤**: 持倉和PnL即時更新
- **儀表板**: 自動生成即時監控儀表板
- **無需 Apps Script**: 使用 Google Sheets API，直接從 Python 同步

## 安裝和設定

### 1. 安裝依賴
```bash
pip install -r requirements.txt
```

### 2. Google Sheets 同步設定 (可選)

如果要啟用 Google Sheets 即時同步功能：

```bash
# 1. 設定 Google Sheets API
python gas_sync/setup_sheets.py

# 2. 測試連線
python gas_sync/gas_sync_service.py

# 3. 以背景服務模式啟動同步
python gas_sync/gas_sync_service.py --daemon --log-level INFO
```

詳細設定請參考 [`gas_sync/README.md`](gas_sync/README.md)

### 2. 設定環境變數
建立 `.env` 檔案：
```env
OPENAI_API_KEY=your_openai_api_key
DATABASE_PATH=data/financial.db
LOG_LEVEL=INFO
```

### 3. 初始化系統
```bash
python -m financial_system.main start --init-only
```

## 使用方法

### 啟動完整系統
```bash
python -m financial_system.main start
```

### Google Sheets 同步服務
```bash
# 設定 Google Sheets 連線
python gas_sync/setup_sheets.py

# 測試同步服務
python gas_sync/gas_sync_service.py

# 以背景模式啟動同步服務
python gas_sync/gas_sync_service.py --daemon
```

### 檢查系統狀態
```bash
python -m financial_system.main status
```

### 生成每日報告
```bash
python -m financial_system.main report
```

### 查看趨勢預測
```bash
python -m financial_system.main predict --symbols AAPL NVDA TSLA
```

### 查看投資組合
```bash
python -m financial_system.main portfolio
```

## 設定範例

### 告警規則設定
```python
from financial_system.realtime_monitor import AlertRule

alert_rules = [
    AlertRule("aapl_high", "AAPL 高價告警", "AAPL", "price_above", 250.0),
    AlertRule("nvda_drop", "NVDA 下跌告警", "NVDA", "change_pct", -5.0),
    AlertRule("vix_spike", "VIX 恐慌指數", "^VIX", "price_above", 30.0),
]
```

### 交易規則設定
```python
from financial_system.automated_trader import TradingRule

trading_rules = [
    TradingRule(
        id="trend_aapl",
        name="AAPL Trend Following",
        symbol="AAPL",
        strategy="trend_following",
        entry_conditions={"min_confidence": 0.7},
        exit_conditions={},
        position_size_pct=0.05,
        stop_loss_pct=0.05,
        take_profit_pct=0.10,
        max_holding_days=30
    )
]
```

## 風險管理

系統包含多層風險控制：

1. **單一倉位限制**: 單一股票倉位不超過投資組合的10%
2. **每日損益限制**: 設定每日最大損益限制
3. **停損停利**: 自動停損停利機制
4. **持有時間限制**: 避免長期持有風險
5. **多策略分散**: 使用不同策略降低集中風險

## 資料來源

- **Yahoo Finance**: 歷史價格和基本面資料
- **Alpha Vantage**: 即時價格和技術指標
- **News APIs**: 金融新聞和情緒分析
- **WebSocket**: 即時市場資料串流

## 擴展功能

### 自訂策略
可以輕鬆新增交易策略：

```python
class CustomStrategy:
    async def evaluate_entry(self, symbol: str) -> bool:
        # 實作進場邏輯
        pass

    async def evaluate_exit(self, position) -> bool:
        # 實作出場邏輯
        pass
```

### 自訂指標
新增技術指標：

```python
def custom_indicator(price_data: pd.DataFrame) -> float:
    # 實作自訂指標計算
    pass
```

### 通知整合
整合各種通知渠道：

```python
async def send_notification(message: str):
    # 郵件、SMS、推送通知等
    pass
```

## 效能優化

- **非同步處理**: 使用 asyncio 提高並發效能
- **快取機制**: 預測結果和資料快取
- **批次處理**: 大資料量批次處理
- **記憶體管理**: 控制記憶體使用量

## 測試和驗證

```bash
# 執行單元測試
pytest tests/

# 執行整合測試
pytest tests/integration/

# 效能測試
pytest tests/performance/
```

## 日誌和監控

系統提供完整的日誌記錄：

- `logs/financial_system.log`: 主要系統日誌
- `logs/realtime_monitor.log`: 監控系統日誌
- `logs/trend_predictor.log`: 預測系統日誌
- `logs/automated_trader.log`: 交易系統日誌

## 故障排除

### 常見問題

1. **API 連線失敗**
   - 檢查網路連線
   - 驗證 API 金鑰
   - 檢查 API 配額

2. **模型訓練失敗**
   - 檢查資料品質
   - 驗證特徵工程
   - 調整模型參數

3. **交易執行失敗**
   - 檢查交易介面連線
   - 驗證資金餘額
   - 檢查交易限制

### 除錯模式

啟用詳細日誌：
```bash
export LOG_LEVEL=DEBUG
python -m financial_system.main start
```

## 版本歷史

- **v1.0.0**: 基礎市場資料收集和 AI 分析
- **v2.0.0**: 新增即時監控和自動化交易
- **v2.1.0**: 增強風險管理和多策略支援

## 授權

本專案採用 MIT 授權條款。

## 貢獻

歡迎提交 Issue 和 Pull Request！

請確保：
- 所有程式碼通過測試
- 更新相關文檔
- 遵循程式碼風格指南