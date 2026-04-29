#!/usr/bin/env python3
"""
Financial System Launcher
一鍵啟動完整金融系統，包括 GAS 同步服務
"""

import asyncio
import argparse
import subprocess
import sys
import time
from pathlib import Path


def check_requirements():
    """檢查必要條件"""
    print("🔍 Checking requirements...")

    # 檢查 Python 版本
    if sys.version_info < (3, 8):
        print("❌ Python 3.8+ required")
        return False

    # 檢查必要檔案
    required_files = [
        "config/settings.json",
        "financial_system/main.py",
        "gas_sync/google_sheets_sync.py"
    ]

    for file_path in required_files:
        if not Path(file_path).exists():
            print(f"❌ Required file not found: {file_path}")
            return False

    print("✅ Requirements check passed")
    return True


async def start_gas_sync_service(log_level="INFO"):
    """啟動 GAS 同步服務"""
    print("🚀 Starting GAS Sync Service...")

    try:
        # 啟動 GAS 同步服務作為子行程
        process = subprocess.Popen([
            sys.executable, "gas_sync/gas_sync_service.py",
            "--daemon", f"--log-level={log_level}"
        ])

        # 等待一下讓服務啟動
        await asyncio.sleep(2)

        if process.poll() is None:
            print("✅ GAS Sync Service started successfully")
            return process
        else:
            print("❌ GAS Sync Service failed to start")
            return None

    except Exception as e:
        print(f"❌ Error starting GAS sync service: {e}")
        return None


async def start_main_system(log_level="INFO"):
    """啟動主系統"""
    print("🚀 Starting Main Financial System...")

    try:
        # 使用 asyncio 建立子行程
        process = await asyncio.create_subprocess_exec(
            sys.executable, "-m", "financial_system.main", "start",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )

        print("✅ Main Financial System started successfully")
        return process

    except Exception as e:
        print(f"❌ Error starting main system: {e}")
        return None


async def monitor_processes(processes):
    """監控行程狀態"""
    gas_process, main_process = processes

    try:
        while True:
            # 檢查 GAS 同步服務
            if gas_process and gas_process.poll() is not None:
                print(f"⚠️  GAS Sync Service exited with code {gas_process.returncode}")
                gas_process = None

            # 檢查主系統
            if main_process and main_process.returncode is not None:
                print(f"⚠️  Main System exited with code {main_process.returncode}")
                main_process = None

            # 如果兩個行程都結束了，退出監控
            if not gas_process and not main_process:
                break

            await asyncio.sleep(5)

    except KeyboardInterrupt:
        print("\n🛑 Shutting down all services...")

        # 終止所有行程
        if gas_process and gas_process.poll() is None:
            gas_process.terminate()
            try:
                gas_process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                gas_process.kill()

        if main_process and main_process.returncode is None:
            main_process.terminate()
            try:
                await asyncio.wait_for(main_process.wait(), timeout=10)
            except asyncio.TimeoutError:
                main_process.kill()


async def main():
    """主啟動函數"""
    parser = argparse.ArgumentParser(description="Financial System Launcher")
    parser.add_argument("--no-gas", action="store_true", help="Skip GAS sync service")
    parser.add_argument("--log-level", default="INFO", choices=["DEBUG", "INFO", "WARNING", "ERROR"],
                       help="Set logging level")
    parser.add_argument("--test-only", action="store_true", help="Only run tests, don't start services")

    args = parser.parse_args()

    print("🚀 Financial System Launcher")
    print("=" * 40)

    # 檢查必要條件
    if not check_requirements():
        sys.exit(1)

    if args.test_only:
        # 執行測試
        print("🧪 Running system tests...")
        result = subprocess.run([sys.executable, "test_system.py"], capture_output=True, text=True)

        if result.returncode == 0:
            print("✅ All tests passed!")
            print(result.stdout)
        else:
            print("❌ Tests failed!")
            print(result.stderr)
            sys.exit(1)

        return

    processes = [None, None]  # [gas_process, main_process]

    try:
        # 啟動 GAS 同步服務 (如果沒有被跳過)
        if not args.no_gas:
            gas_process = await start_gas_sync_service(args.log_level)
            processes[0] = gas_process

            if not gas_process:
                print("⚠️  Continuing without GAS sync service...")

        # 啟動主系統
        main_process = await start_main_system(args.log_level)
        processes[1] = main_process

        if not main_process:
            print("❌ Failed to start main system")
            sys.exit(1)

        print("\n🎉 Financial System started successfully!")
        print("\nActive services:")
        if processes[0]:
            print("✅ GAS Sync Service (Google Sheets)")
        print("✅ Main Financial System")
        print("\nPress Ctrl+C to stop all services")

        # 監控行程
        await monitor_processes(processes)

    except KeyboardInterrupt:
        print("\n🛑 Shutdown requested by user")
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
    finally:
        # 清理資源
        for process in processes:
            if process and process.poll() is None:
                if hasattr(process, 'terminate'):
                    process.terminate()
                elif hasattr(process, 'kill'):
                    process.kill()

        print("👋 All services stopped")


if __name__ == "__main__":
    asyncio.run(main())