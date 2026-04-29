#!/usr/bin/env python3
"""
System Test Script
測試金融系統各組件是否正常運作
"""

import sys
import json
import asyncio
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from financial_system.config import load_settings
from financial_system.market import MarketDataCollector
from gas_sync.google_sheets_sync import GoogleSheetsSync


async def test_config():
    """測試設定載入"""
    print("🧪 Testing configuration...")
    try:
        settings = load_settings()
        print("✅ Configuration loaded successfully")
        return True
    except Exception as e:
        print(f"❌ Configuration test failed: {e}")
        return False


async def test_market_data():
    """測試市場資料收集"""
    print("🧪 Testing market data collection...")
    try:
        market = MarketDataCollector()
        await market.initialize()
        snapshots = await market.get_latest_snapshots()
        if snapshots:
            print(f"✅ Market data collection successful ({len(snapshots)} snapshots)")
        else:
            print("⚠️  Market data collection returned no snapshots")
        return True
    except Exception as e:
        print(f"❌ Market data test failed: {e}")
        return False


async def test_gas_sync():
    """測試 GAS 同步 (如果已設定)"""
    print("🧪 Testing GAS sync...")
    try:
        config_path = Path(__file__).parent / "config" / "settings.json"
        if not config_path.exists():
            print("⚠️  GAS sync config not found, skipping test")
            return True

        with config_path.open("r", encoding="utf-8") as file:
            settings = json.load(file)

        google_settings = settings.get("google_sheets", {})
        if not google_settings.get("sync_enabled", False):
            print("⚠️  GAS sync disabled in settings, skipping test")
            return True

        if not google_settings.get("spreadsheet_id") or google_settings.get("spreadsheet_id") == "your_spreadsheet_id_here":
            print("⚠️  Google Sheets spreadsheet_id not configured, skipping test")
            return True

        if not google_settings.get("service_account_file") or google_settings.get("service_account_file") == "credentials.json":
            print("⚠️  Google Sheets service_account_file not configured, skipping test")
            return True

        sync = GoogleSheetsSync()
        success = await sync.initialize()

        if success:
            print("✅ GAS sync initialized successfully")
            return True
        print("❌ GAS sync initialization failed")
        return False
    except Exception as e:
        print(f"❌ GAS sync test failed: {e}")
        return False


async def test_imports():
    """測試所有必要的模組匯入"""
    print("🧪 Testing module imports...")
    try:
        import financial_system.main
        import financial_system.market
        import financial_system.realtime_monitor
        import financial_system.trend_predictor
        import financial_system.automated_trader
        import gas_sync.google_sheets_sync
        import gas_sync.gas_sync_service
        print("✅ All modules imported successfully")
        return True
    except ImportError as e:
        print(f"❌ Import test failed: {e}")
        return False


async def run_tests():
    """執行所有測試"""
    print("🚀 Running Financial System Tests")
    print("=" * 40)

    tests = [
        ("Module Imports", test_imports),
        ("Configuration", test_config),
        ("Market Data", test_market_data),
        ("GAS Sync", test_gas_sync),
    ]

    passed = 0
    total = len(tests)

    for test_name, test_func in tests:
        print(f"\n🔍 Running {test_name} test...")
        if await test_func():
            print(f"✅ {test_name} PASSED")
            passed += 1
        else:
            print(f"❌ {test_name} FAILED")

    print("\n" + "=" * 40)
    print("📊 Test Results Summary:")
    print(f"  Passed: {passed}\n  Total: {total}")

    return passed == total


if __name__ == "__main__":
    success = asyncio.run(run_tests())
    sys.exit(0 if success else 1)

