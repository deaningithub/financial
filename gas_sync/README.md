# Google Sheets API 設定指南
# =================================

## 1. 建立 Google Cloud 專案

1. 前往 [Google Cloud Console](https://console.cloud.google.com/)
2. 建立新專案或選擇現有專案
3. 啟用 Google Sheets API 和 Google Drive API

## 2. 建立服務帳戶

1. 在 Google Cloud Console 中，前往 "IAM & Admin" > "Service Accounts"
2. 點擊 "Create Service Account"
3. 輸入服務帳戶名稱和描述
4. 點擊 "Create and Continue"
5. 選擇角色：Editor (或自訂角色，包含 Sheets 和 Drive 權限)
6. 點擊 "Done"

## 3. 產生金鑰

1. 在服務帳戶列表中，點擊剛建立的帳戶
2. 前往 "Keys" 標籤
3. 點擊 "Add Key" > "Create new key"
4. 選擇 JSON 格式
5. 下載 JSON 檔案

## 4. 設定 Google Sheets

1. 建立新的 Google Sheets 或使用現有的
2. 複製 Spreadsheet ID (網址中的長字串)
3. 與服務帳戶分享工作表：
   - 在工作表中點擊 "Share"
   - 輸入服務帳戶的 email (在 JSON 檔案中的 "client_email")
   - 給予 "Editor" 權限

## 5. 本地設定

1. 將下載的 JSON 檔案重新命名為 `credentials.json`
2. 放置在專案根目錄
3. 更新 `config/settings.yaml` 檔案：

```yaml
google_sheets:
  service_account_file: "credentials.json"
  spreadsheet_id: "你的_spreadsheet_id_這裡"
```

## 6. 安裝依賴

```bash
pip install gspread google-auth google-api-python-client
```

## 7. 測試連線

```bash
python -c "
import asyncio
from gas_sync.google_sheets_sync import GoogleSheetsSync

async def test():
    sync = GoogleSheetsSync()
    success = await sync.initialize()
    print('Connection successful!' if success else 'Connection failed!')

asyncio.run(test())
"
```

## 工作表結構

系統會自動建立以下工作表：

### RealTime_Monitor
即時市場監控資料：
- Timestamp: 時間戳
- Symbol: 股票代碼
- Price: 價格
- Change: 漲跌
- Change_Pct: 漲跌幅
- Volume: 成交量
- MA20: 20日均線
- MA50: 50日均線
- RSI: 相對強弱指標
- Status: 狀態

### Alerts_Log
告警記錄：
- Timestamp: 時間戳
- Rule_ID: 規則ID
- Symbol: 股票代碼
- Alert_Type: 告警類型
- Message: 訊息
- Severity: 嚴重程度
- Current_Value: 目前值
- Threshold: 閾值
- Status: 狀態

### Portfolio_Status
投資組合狀態：
- Timestamp: 時間戳
- Symbol: 股票代碼
- Quantity: 數量
- Entry_Price: 進場價格
- Current_Price: 目前價格
- Unrealized_PnL: 未實現損益
- Stop_Loss: 停損價
- Take_Profit: 停利價
- Rule_ID: 規則ID

### Dashboard
即時儀表板：
- 市場狀態總覽
- 主動告警數量
- 投資組合價值
- 持倉總數
- 最近告警列表

## 整合到主系統

在 `main.py` 中整合：

```python
from gas_sync.google_sheets_sync import GASRealtimeMonitor

# 在系統初始化時
gas_monitor = GASRealtimeMonitor()
await gas_monitor.initialize()

# 在監控循環中同步資料
await gas_monitor.sync_alert_to_sheets(alert)

# 在每日報告時同步投資組合
portfolio_data = trader.get_portfolio_summary()['positions_detail']
await gas_monitor.sync_portfolio_to_sheets(portfolio_data)
```

## 故障排除

### 常見問題

1. **"Request had insufficient authentication scopes"**
   - 檢查服務帳戶權限是否包含 Sheets 和 Drive API

2. **"The caller does not have permission"**
   - 確保工作表已與服務帳戶分享

3. **"Spreadsheet not found"**
   - 檢查 spreadsheet_id 是否正確

4. **"Service account key file not found"**
   - 確保 credentials.json 檔案存在且路徑正確

### 權限設定

服務帳戶需要以下權限：
- https://www.googleapis.com/auth/spreadsheets
- https://www.googleapis.com/auth/drive

### 配額限制

Google Sheets API 有以下限制：
- 每分鐘 60 次讀取請求
- 每分鐘 60 次寫入請求
- 每日 100 次請求 (免費等級)

如需更高配額，請在 Google Cloud Console 中調整。