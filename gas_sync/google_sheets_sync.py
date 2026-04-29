#!/usr/bin/env python3
"""
Google Sheets Sync Module for Financial System
使用 Google Sheets API 進行即時監控資料同步
"""

from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any

import gspread
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from financial_system.config import DB_PATH, CONFIG_DIR


class GoogleSheetsSync:
    """Google Sheets 同步管理器"""

    def __init__(self):
        self.settings = self._load_json_settings()
        self.creds = None
        self.gc = None
        self.service = None

        # 工作表配置
        self.spreadsheet_id = self.settings.get('google_sheets', {}).get('spreadsheet_id')
        self.monitor_sheet = "RealTime_Monitor"
        self.alerts_sheet = "Alerts_Log"
        self.portfolio_sheet = "Portfolio_Status"

        self.setup_logging()

    def setup_logging(self):
        """設定日誌"""
        logging.basicConfig(
            filename='logs/google_sheets_sync.log',
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s'
        )
        self.logger = logging.getLogger(__name__)

    def _load_json_settings(self) -> dict:
        """Load optional JSON-based settings from config/settings.json."""
        try:
            settings_path = CONFIG_DIR / "settings.json"
            if settings_path.exists():
                with settings_path.open("r", encoding="utf-8") as file:
                    return json.load(file)
        except Exception as e:
            self.logger = logging.getLogger(__name__)
            self.logger.warning(f"Could not load JSON settings: {e}")
        return {}

    async def initialize(self):
        """初始化 Google Sheets 連線"""
        try:
            # 載入服務帳戶金鑰
            service_account_file = self.settings.get('google_sheets', {}).get('service_account_file', 'credentials.json')

            if not self.spreadsheet_id:
                self.logger.warning("Google Sheets spreadsheet_id not configured")
                return False

            # 設定權限範圍
            scopes = [
                'https://www.googleapis.com/auth/spreadsheets',
                'https://www.googleapis.com/auth/drive'
            ]

            # 載入憑證
            self.creds = Credentials.from_service_account_file(service_account_file, scopes=scopes)

            # 初始化客戶端
            self.gc = gspread.authorize(self.creds)
            self.service = build('sheets', 'v4', credentials=self.creds)

            # 確保工作表存在
            await self._ensure_sheets_exist()

            self.logger.info("Google Sheets sync initialized successfully")
            return True

        except Exception as e:
            self.logger.error(f"Failed to initialize Google Sheets: {e}")
            return False

    async def _ensure_sheets_exist(self):
        """確保必要的工作表存在"""
        try:
            spreadsheet = self.gc.open_by_key(self.spreadsheet_id)

            # 檢查工作表是否存在
            existing_sheets = [sheet.title for sheet in spreadsheet.worksheets()]

            required_sheets = [self.monitor_sheet, self.alerts_sheet, self.portfolio_sheet]

            for sheet_name in required_sheets:
                if sheet_name not in existing_sheets:
                    # 建立新工作表
                    worksheet = spreadsheet.add_worksheet(title=sheet_name, rows=1000, cols=20)
                    await self._initialize_sheet_headers(sheet_name, worksheet)
                    self.logger.info(f"Created sheet: {sheet_name}")
                else:
                    # 確保標題列存在
                    worksheet = spreadsheet.worksheet(sheet_name)
                    await self._ensure_sheet_headers(sheet_name, worksheet)

        except Exception as e:
            self.logger.error(f"Error ensuring sheets exist: {e}")

    async def _initialize_sheet_headers(self, sheet_name: str, worksheet):
        """初始化工作表標題列"""
        if sheet_name == self.monitor_sheet:
            headers = [
                "Timestamp", "Symbol", "Price", "Change", "Change_Pct",
                "Volume", "MA20", "MA50", "RSI", "Status"
            ]
        elif sheet_name == self.alerts_sheet:
            headers = [
                "Timestamp", "Rule_ID", "Symbol", "Alert_Type", "Message",
                "Severity", "Current_Value", "Threshold", "Status"
            ]
        elif sheet_name == self.portfolio_sheet:
            headers = [
                "Timestamp", "Symbol", "Quantity", "Entry_Price", "Current_Price",
                "Unrealized_PnL", "Stop_Loss", "Take_Profit", "Rule_ID"
            ]
        else:
            headers = ["Timestamp", "Data"]

        worksheet.update('A1', [headers])

    async def _ensure_sheet_headers(self, sheet_name: str, worksheet):
        """確保標題列存在"""
        try:
            # 檢查第一行是否為空
            first_row = worksheet.row_values(1)
            if not first_row or all(not cell for cell in first_row):
                await self._initialize_sheet_headers(sheet_name, worksheet)
        except Exception as e:
            self.logger.error(f"Error ensuring headers for {sheet_name}: {e}")

    async def sync_realtime_data(self, symbol_data: Dict[str, Any]):
        """同步即時市場資料到 Google Sheets"""
        try:
            if not self.gc:
                return

            spreadsheet = self.gc.open_by_key(self.spreadsheet_id)
            worksheet = spreadsheet.worksheet(self.monitor_sheet)

            # 準備資料
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            row_data = [
                timestamp,
                symbol_data.get('symbol', ''),
                symbol_data.get('price', ''),
                symbol_data.get('change', ''),
                symbol_data.get('change_pct', ''),
                symbol_data.get('volume', ''),
                symbol_data.get('ma20', ''),
                symbol_data.get('ma50', ''),
                symbol_data.get('rsi', ''),
                symbol_data.get('status', '')
            ]

            # 新增到工作表
            worksheet.append_row(row_data)

            # 限制行數，避免工作表過大
            await self._limit_sheet_rows(worksheet, 5000)

            self.logger.info(f"Synced realtime data for {symbol_data.get('symbol')}")

        except Exception as e:
            self.logger.error(f"Error syncing realtime data: {e}")

    async def sync_alert(self, alert_data: Dict[str, Any]):
        """同步告警資料到 Google Sheets"""
        try:
            if not self.gc:
                return

            spreadsheet = self.gc.open_by_key(self.spreadsheet_id)
            worksheet = spreadsheet.worksheet(self.alerts_sheet)

            # 準備資料
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            row_data = [
                timestamp,
                alert_data.get('rule_id', ''),
                alert_data.get('symbol', ''),
                alert_data.get('alert_type', ''),
                alert_data.get('message', ''),
                alert_data.get('severity', ''),
                alert_data.get('current_value', ''),
                alert_data.get('threshold', ''),
                'Active'
            ]

            # 新增到工作表
            worksheet.append_row(row_data)

            self.logger.info(f"Synced alert: {alert_data.get('message', '')[:50]}...")

        except Exception as e:
            self.logger.error(f"Error syncing alert: {e}")

    async def sync_portfolio_status(self, portfolio_data: List[Dict[str, Any]]):
        """同步投資組合狀態到 Google Sheets"""
        try:
            if not self.gc:
                return

            spreadsheet = self.gc.open_by_key(self.spreadsheet_id)
            worksheet = spreadsheet.worksheet(self.portfolio_sheet)

            # 清空現有資料（保留標題列）
            worksheet.clear()

            # 重新寫入標題
            await self._initialize_sheet_headers(self.portfolio_sheet, worksheet)

            # 寫入投資組合資料
            for position in portfolio_data:
                timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                row_data = [
                    timestamp,
                    position.get('symbol', ''),
                    position.get('quantity', ''),
                    position.get('entry_price', ''),
                    position.get('current_price', ''),
                    position.get('unrealized_pnl', ''),
                    position.get('stop_loss', ''),
                    position.get('take_profit', ''),
                    position.get('rule_id', '')
                ]
                worksheet.append_row(row_data)

            self.logger.info(f"Synced portfolio status: {len(portfolio_data)} positions")

        except Exception as e:
            self.logger.error(f"Error syncing portfolio: {e}")

    async def get_recent_alerts(self, hours: int = 24) -> List[Dict[str, Any]]:
        """從 Google Sheets 獲取最近的告警"""
        try:
            if not self.gc:
                return []

            spreadsheet = self.gc.open_by_key(self.spreadsheet_id)
            worksheet = spreadsheet.worksheet(self.alerts_sheet)

            # 獲取所有資料
            all_data = worksheet.get_all_records()

            # 過濾最近的告警
            cutoff_time = datetime.now() - timedelta(hours=hours)
            recent_alerts = []

            for row in all_data:
                try:
                    alert_time = datetime.strptime(row['Timestamp'], "%Y-%m-%d %H:%M:%S")
                    if alert_time > cutoff_time:
                        recent_alerts.append(row)
                except (ValueError, KeyError):
                    continue

            return recent_alerts

        except Exception as e:
            self.logger.error(f"Error getting recent alerts: {e}")
            return []

    async def get_monitoring_data(self, symbol: str, hours: int = 24) -> List[Dict[str, Any]]:
        """從 Google Sheets 獲取監控資料"""
        try:
            if not self.gc:
                return []

            spreadsheet = self.gc.open_by_key(self.spreadsheet_id)
            worksheet = spreadsheet.worksheet(self.monitor_sheet)

            # 獲取所有資料
            all_data = worksheet.get_all_records()

            # 過濾指定股票和時間範圍
            cutoff_time = datetime.now() - timedelta(hours=hours)
            symbol_data = []

            for row in all_data:
                try:
                    if row.get('Symbol') == symbol:
                        data_time = datetime.strptime(row['Timestamp'], "%Y-%m-%d %H:%M:%S")
                        if data_time > cutoff_time:
                            symbol_data.append(row)
                except (ValueError, KeyError):
                    continue

            return symbol_data

        except Exception as e:
            self.logger.error(f"Error getting monitoring data: {e}")
            return []

    async def _limit_sheet_rows(self, worksheet, max_rows: int = 5000):
        """限制工作表行數"""
        try:
            # 獲取目前行數
            current_rows = len(worksheet.get_all_values())

            if current_rows > max_rows:
                # 刪除舊資料，保留標題列
                rows_to_delete = current_rows - max_rows
                worksheet.delete_rows(2, rows_to_delete + 1)  # 保留第一行標題

        except Exception as e:
            self.logger.error(f"Error limiting sheet rows: {e}")

    async def create_realtime_dashboard(self):
        """建立即時儀表板"""
        try:
            if not self.service:
                return

            # 建立新的工作表作為儀表板
            dashboard_sheet = "Dashboard"

            spreadsheet = self.gc.open_by_key(self.spreadsheet_id)

            # 檢查是否已存在
            try:
                worksheet = spreadsheet.worksheet(dashboard_sheet)
                worksheet.clear()
            except gspread.WorksheetNotFound:
                worksheet = spreadsheet.add_worksheet(title=dashboard_sheet, rows=50, cols=10)

            # 建立儀表板內容
            dashboard_data = [
                ["Financial System Dashboard"],
                [f"Last Update: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"],
                [""],
                ["Market Status", "Value"],
                ["Active Alerts", "=COUNTA(Alerts_Log!A:A)-1"],
                ["Portfolio Value", "=SUM(Portfolio_Status!E:E)"],
                ["Total Positions", "=COUNTA(Portfolio_Status!A:A)-1"],
                [""],
                ["Recent Alerts (Last 5)"],
                ["=SORT(FILTER(Alerts_Log!A:E, Alerts_Log!A:A >= NOW()-1), 1, FALSE)"]
            ]

            worksheet.update('A1', dashboard_data)

            self.logger.info("Created realtime dashboard")

        except Exception as e:
            self.logger.error(f"Error creating dashboard: {e}")


# 整合到現有系統的同步器
class GASRealtimeMonitor:
    """整合 GAS 和本地即時監控的同步器"""

    def __init__(self):
        self.sheets_sync = GoogleSheetsSync()
        self.monitoring_symbols = ["AAPL", "NVDA", "2330.TW", "^GSPC", "^VIX"]
        self.sync_interval = 60  # 每60秒同步一次

    async def initialize(self):
        """初始化同步器"""
        success = await self.sheets_sync.initialize()
        if success:
            # 建立儀表板
            await self.sheets_sync.create_realtime_dashboard()
        return success

    async def start_sync_loop(self):
        """啟動同步循環"""
        while True:
            try:
                await self._sync_realtime_data()
                await asyncio.sleep(self.sync_interval)
            except Exception as e:
                logging.error(f"Sync loop error: {e}")
                await asyncio.sleep(60)

    async def _sync_realtime_data(self):
        """同步即時資料"""
        try:
            # 這裡應該從實際的市場資料源獲取資料
            # 目前使用模擬資料
            for symbol in self.monitoring_symbols:
                mock_data = {
                    'symbol': symbol,
                    'price': 100.0 + (hash(symbol) % 50),  # 模擬價格
                    'change': (hash(symbol + 'change') % 10) - 5,
                    'change_pct': ((hash(symbol + 'pct') % 100) - 50) / 100.0,
                    'volume': hash(symbol + 'vol') % 1000000,
                    'ma20': 98.0 + (hash(symbol) % 10),
                    'ma50': 95.0 + (hash(symbol) % 15),
                    'rsi': 50 + (hash(symbol + 'rsi') % 50) - 25,
                    'status': 'active'
                }

                await self.sheets_sync.sync_realtime_data(mock_data)

        except Exception as e:
            logging.error(f"Error syncing realtime data: {e}")

    async def sync_alert_to_sheets(self, alert):
        """同步告警到 Sheets"""
        alert_data = {
            'rule_id': alert.rule_id,
            'symbol': alert.symbol,
            'alert_type': 'price_alert',
            'message': alert.message,
            'severity': alert.severity,
            'current_value': alert.current_value,
            'threshold': alert.threshold
        }

        await self.sheets_sync.sync_alert(alert_data)

    async def sync_portfolio_to_sheets(self, portfolio_data):
        """同步投資組合到 Sheets"""
        await self.sheets_sync.sync_portfolio_status(portfolio_data)


# 使用範例
async def main():
    # 初始化同步器
    sync = GASRealtimeMonitor()
    success = await sync.initialize()

    if success:
        print("Google Sheets sync initialized successfully")

        # 啟動同步循環
        await sync.start_sync_loop()
    else:
        print("Failed to initialize Google Sheets sync")
        print("Please check your credentials and spreadsheet configuration")


if __name__ == "__main__":
    asyncio.run(main())