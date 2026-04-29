#!/usr/bin/env python3
"""
Google Sheets Sync Setup Script
協助設定 Google Sheets API 和測試連線
"""

import asyncio
import json
import os
from pathlib import Path

from gas_sync.google_sheets_sync import GoogleSheetsSync


async def test_google_sheets_connection():
    """測試 Google Sheets 連線"""
    print("🔗 Testing Google Sheets Connection...")

    sync = GoogleSheetsSync()
    success = await sync.initialize()

    if success:
        print("✅ Google Sheets connection successful!")

        # 測試同步範例資料
        sample_data = {
            'symbol': 'AAPL',
            'price': 150.25,
            'change': 2.50,
            'change_pct': 1.69,
            'volume': 50000000,
            'ma20': 148.75,
            'ma50': 145.30,
            'rsi': 65.5,
            'status': 'active'
        }

        await sync.sync_realtime_data(sample_data)
        print("✅ Sample data synced successfully!")

        # 建立儀表板
        await sync.create_realtime_dashboard()
        print("✅ Dashboard created successfully!")

    else:
        print("❌ Google Sheets connection failed!")
        print("\n請檢查以下設定：")
        print("1. credentials.json 檔案是否存在")
        print("2. Google Sheets API 已啟用")
        print("3. 服務帳戶有權限存取 Spreadsheet")
        print("4. spreadsheet_id 正確")

    return success


async def setup_google_sheets_config():
    """設定 Google Sheets 配置"""
    print("⚙️  Google Sheets Configuration Setup")
    print("=" * 50)

    config_file = Path("config/settings.json")

    if not config_file.exists():
        print("❌ config/settings.json not found!")
        return False

    # 讀取現有設定
    with config_file.open('r', encoding='utf-8') as f:
        config = json.load(f)

    # 檢查是否已有 google_sheets 設定
    if 'google_sheets' not in config:
        config['google_sheets'] = {}

    google_sheets_config = config['google_sheets']

    print("\n請提供以下資訊：")

    # 服務帳戶檔案
    service_account_file = input("服務帳戶金鑰檔案路徑 (credentials.json): ").strip()
    if service_account_file:
        google_sheets_config['service_account_file'] = service_account_file

    # Spreadsheet ID
    spreadsheet_id = input("Google Sheets Spreadsheet ID: ").strip()
    if spreadsheet_id:
        google_sheets_config['spreadsheet_id'] = spreadsheet_id

    # 啟用同步
    enable_sync = input("啟用 Google Sheets 同步? (y/n): ").strip().lower()
    google_sheets_config['sync_enabled'] = enable_sync in ['y', 'yes', 'true']

    # 同步間隔
    sync_interval = input("同步間隔秒數 (預設 60): ").strip()
    if sync_interval.isdigit():
        google_sheets_config['sync_interval_seconds'] = int(sync_interval)
    else:
        google_sheets_config['sync_interval_seconds'] = 60

    # 最大行數
    max_rows = input("工作表最大行數 (預設 5000): ").strip()
    if max_rows.isdigit():
        google_sheets_config['max_sheet_rows'] = int(max_rows)
    else:
        google_sheets_config['max_sheet_rows'] = 5000

    # 儲存設定
    with config_file.open('w', encoding='utf-8') as f:
        json.dump(config, f, indent=2, ensure_ascii=False)

    print("✅ Configuration saved successfully!")
    return True


def check_credentials_file():
    """檢查憑證檔案"""
    credentials_files = [
        'credentials.json',
        'config/credentials.json',
        Path.home() / 'credentials.json'
    ]

    for cred_file in credentials_files:
        if Path(cred_file).exists():
            print(f"✅ Found credentials file: {cred_file}")
            return str(cred_file)

    print("❌ credentials.json not found!")
    print("\n請按照以下步驟取得憑證檔案：")
    print("1. 前往 https://console.cloud.google.com/")
    print("2. 建立或選擇專案")
    print("3. 啟用 Google Sheets API 和 Google Drive API")
    print("4. 建立服務帳戶並下載 JSON 金鑰")
    print("5. 將檔案重新命名為 credentials.json 並放置在專案根目錄")

    return None


async def main():
    """主設定函數"""
    print("🚀 Google Sheets Sync Setup")
    print("=" * 40)

    # 檢查憑證檔案
    cred_file = check_credentials_file()
    if not cred_file:
        return

    # 設定配置
    await setup_google_sheets_config()

    # 測試連線
    print("\n" + "=" * 50)
    success = await test_google_sheets_connection()

    if success:
        print("\n🎉 Google Sheets sync setup completed successfully!")
        print("\n你現在可以：")
        print("1. 執行 python -m financial_system.main start 啟動完整系統")
        print("2. 即時監控資料會自動同步到 Google Sheets")
        print("3. 告警和交易記錄會即時更新")
        print("4. 每日報告時會同步投資組合狀態")
    else:
        print("\n⚠️  設定完成但連線測試失敗，請檢查設定後重新測試")


if __name__ == "__main__":
    asyncio.run(main())