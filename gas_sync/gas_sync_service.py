#!/usr/bin/env python3
"""
GAS Sync Service
獨立的 Google Sheets 同步服務，可以在背景執行
"""

import asyncio
import argparse
import logging
import signal
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from gas_sync.google_sheets_sync import GASRealtimeMonitor


class GASSyncService:
    """GAS 同步服務"""

    def __init__(self):
        self.monitor = GASRealtimeMonitor()
        self.running = False
        self.logger = logging.getLogger(__name__)

    async def start(self):
        """啟動服務"""
        self.logger.info("Starting GAS Sync Service...")

        # 初始化
        success = await self.monitor.initialize()
        if not success:
            self.logger.error("Failed to initialize GAS monitor")
            return False

        self.running = True

        # 設定訊號處理
        def signal_handler(signum, frame):
            self.logger.info(f"Received signal {signum}, shutting down...")
            self.running = False

        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)

        try:
            # 啟動同步循環
            await self.monitor.start_sync_loop()
        except KeyboardInterrupt:
            self.logger.info("Service interrupted by user")
        except Exception as e:
            self.logger.error(f"Service error: {e}")
        finally:
            self.logger.info("GAS Sync Service stopped")

        return True

    async def sync_alert(self, alert_data):
        """同步告警資料"""
        await self.monitor.sync_alert_to_sheets(alert_data)

    async def sync_portfolio(self, portfolio_data):
        """同步投資組合資料"""
        await self.monitor.sync_portfolio_to_sheets(portfolio_data)


async def main():
    """主函數"""
    parser = argparse.ArgumentParser(description="GAS Sync Service")
    parser.add_argument("--log-level", default="INFO", choices=["DEBUG", "INFO", "WARNING", "ERROR"],
                       help="Set logging level")
    parser.add_argument("--daemon", action="store_true", help="Run as daemon")

    args = parser.parse_args()

    # 設定日誌
    logging.basicConfig(
        level=getattr(logging, args.log_level),
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler('logs/gas_sync_service.log'),
            logging.StreamHandler(sys.stdout)
        ]
    )

    logger = logging.getLogger(__name__)

    if args.daemon:
        logger.info("Starting GAS Sync Service in daemon mode...")

        service = GASSyncService()
        success = await service.start()

        if not success:
            logger.error("Failed to start service")
            sys.exit(1)
    else:
        # 測試模式
        logger.info("Testing GAS Sync Service...")

        monitor = GASRealtimeMonitor()
        success = await monitor.initialize()

        if success:
            logger.info("GAS Sync Service test successful!")

            # 測試同步範例資料
            sample_alert = type('Alert', (), {
                'rule_id': 'test_alert',
                'symbol': 'AAPL',
                'alert_type': 'price_alert',
                'message': 'Test alert message',
                'severity': 'medium',
                'current_value': 150.0,
                'threshold': 145.0
            })()

            await monitor.sync_alert_to_sheets(sample_alert)
            logger.info("Sample alert synced successfully!")

            sample_portfolio = [
                {
                    'symbol': 'AAPL',
                    'quantity': 100,
                    'entry_price': 145.0,
                    'current_price': 150.0,
                    'unrealized_pnl': 500.0,
                    'stop_loss': 140.0,
                    'take_profit': 160.0,
                    'rule_id': 'test_rule'
                }
            ]

            await monitor.sync_portfolio_to_sheets(sample_portfolio)
            logger.info("Sample portfolio synced successfully!")

        else:
            logger.error("GAS Sync Service test failed!")
            sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())