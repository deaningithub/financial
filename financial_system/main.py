#!/usr/bin/env python3
"""
Financial System Integration Script
整合所有組件，提供統一的介面和協調功能
"""

from __future__ import annotations

import asyncio
import argparse
import logging
import signal
import sys
from datetime import datetime
from typing import List, Optional

from financial_system.config import load_settings, Settings
from financial_system.market import MarketDataCollector
from financial_system.llm import create_ai_report
from financial_system.realtime_monitor import RealTimeMonitor, AlertRule
from financial_system.trend_predictor import TrendPredictor
from financial_system.automated_trader import AutomatedTrader, TradingRule

# Google Sheets 同步 (可選)
try:
    from gas_sync.google_sheets_sync import GASRealtimeMonitor
    GAS_AVAILABLE = True
except ImportError:
    GAS_AVAILABLE = False
    print("Google Sheets sync not available. Install dependencies: pip install gspread google-auth google-api-python-client")


class FinancialSystem:
    """金融系統整合器"""

    def __init__(self):
        self.settings = load_settings()
        self.collector = MarketDataCollector()
        self.monitor = RealTimeMonitor()
        self.predictor = TrendPredictor()
        self.trader = AutomatedTrader()

        # Google Sheets 同步 (如果可用)
        self.gas_monitor = None
        if GAS_AVAILABLE and self.settings.get('google_sheets', {}).get('sync_enabled', False):
            self.gas_monitor = GASRealtimeMonitor()

        self.running = False
        self.tasks = []

        self.setup_logging()
        self.setup_signal_handlers()

    def setup_logging(self):
        """設定全系統日誌"""
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler('logs/financial_system.log'),
                logging.StreamHandler(sys.stdout)
            ]
        )
        self.logger = logging.getLogger(__name__)

    def setup_signal_handlers(self):
        """設定訊號處理器"""
        def signal_handler(signum, frame):
            self.logger.info(f"Received signal {signum}, shutting down...")
            self.running = False

        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)

    async def initialize_system(self):
        """初始化系統"""
        self.logger.info("Initializing Financial System...")

        try:
            # 初始化資料收集器
            await self.collector.initialize()

            # 初始化 Google Sheets 同步
            if self.gas_monitor:
                gas_success = await self.gas_monitor.initialize()
                if gas_success:
                    self.logger.info("Google Sheets sync initialized")
                else:
                    self.logger.warning("Google Sheets sync initialization failed")

            # 訓練預測模型
            symbols = ["AAPL", "NVDA", "2330.TW", "^GSPC", "^VIX"]
            await self.predictor.train_models(symbols)

            # 設定監控規則
            alert_rules = [
                AlertRule("aapl_high", "AAPL 高價告警", "AAPL", "price_above", 250.0),
                AlertRule("nvda_drop", "NVDA 下跌告警", "NVDA", "change_pct", -5.0),
                AlertRule("vix_spike", "VIX 恐慌指數", "^VIX", "price_above", 30.0),
            ]

            for rule in alert_rules:
                self.monitor.add_alert_rule(rule)

            # 設定交易規則
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
                ),
                TradingRule(
                    id="mr_nvda",
                    name="NVDA Mean Reversion",
                    symbol="NVDA",
                    strategy="mean_reversion",
                    entry_conditions={"deviation_threshold": -3},
                    exit_conditions={"profit_target": 2},
                    position_size_pct=0.03,
                    stop_loss_pct=0.03,
                    take_profit_pct=0.06,
                    max_holding_days=10
                )
            ]

            for rule in trading_rules:
                self.trader.add_trading_rule(rule)

            # 設定回調函數
            self.monitor.add_alert_callback(self.handle_alert)
            self.trader.add_trade_callback(self.handle_trade)

            self.logger.info("System initialization completed")

        except Exception as e:
            self.logger.error(f"System initialization failed: {e}")
            raise

    async def start_system(self):
        """啟動系統"""
        self.logger.info("Starting Financial System...")
        self.running = True

        try:
            # 建立並啟動任務
            tasks = [
                self._data_collection_loop(),
                self.monitor.start_monitoring(),
                self._trading_loop(),
                self._reporting_loop(),
            ]

            # 如果有GAS同步，加入同步循環
            if self.gas_monitor:
                tasks.append(self.gas_monitor.start_sync_loop())

            self.tasks = [asyncio.create_task(task) for task in tasks]

            # 等待所有任務完成或被中斷
            await asyncio.gather(*self.tasks, return_exceptions=True)

        except Exception as e:
            self.logger.error(f"System error: {e}")
        finally:
            await self.shutdown_system()

    async def shutdown_system(self):
        """關閉系統"""
        self.logger.info("Shutting down Financial System...")

        # 取消所有任務
        for task in self.tasks:
            if not task.done():
                task.cancel()

        # 等待任務完成
        await asyncio.gather(*self.tasks, return_exceptions=True)

        # 儲存最終狀態
        await self._save_system_state()

        self.logger.info("System shutdown completed")

    async def _data_collection_loop(self):
        """資料收集循環"""
        while self.running:
            try:
                await self.collector.collect_all_data()
                await asyncio.sleep(3600)  # 每小時收集一次
            except Exception as e:
                self.logger.error(f"Data collection error: {e}")
                await asyncio.sleep(60)

    async def _trading_loop(self):
        """交易循環"""
        while self.running:
            try:
                # 交易邏輯由 AutomatedTrader 處理
                await asyncio.sleep(60)
            except Exception as e:
                self.logger.error(f"Trading loop error: {e}")
                await asyncio.sleep(60)

    async def _reporting_loop(self):
        """報告生成循環"""
        while self.running:
            try:
                # 每天早上9點生成報告
                now = datetime.now()
                if now.hour == 9 and now.minute == 0:
                    await self.generate_daily_report()
                    await asyncio.sleep(60)  # 避免重複執行
                else:
                    await asyncio.sleep(60)
            except Exception as e:
                self.logger.error(f"Reporting error: {e}")
                await asyncio.sleep(60)

    async def generate_daily_report(self):
        """生成每日報告"""
        try:
            self.logger.info("Generating daily report...")

            # 收集市場資料
            snapshots = await self.collector.get_latest_snapshots()
            movers = await self.collector.get_top_movers()
            news_items = await self.collector.get_latest_news()

            # 生成趨勢預測
            symbols = ["AAPL", "NVDA", "2330.TW", "^GSPC"]
            trend_report = await self.predictor.generate_trend_report(symbols)

            # 生成 AI 報告
            ai_report = await create_ai_report(
                api_key=self.settings.openai_api_key,
                model=self.settings.openai_model,
                day=datetime.now().strftime("%Y-%m-%d"),
                notes=[],  # 可以從其他來源獲取
                snapshots=snapshots,
                movers=movers,
                news_items=news_items,
                trend_predictions=trend_report
            )

            # 儲存報告
            await self._save_report(ai_report)

            # 同步投資組合狀態到 Google Sheets
            if self.gas_monitor:
                try:
                    portfolio_data = self.trader.get_portfolio_summary()['positions_detail']
                    await self.gas_monitor.sync_portfolio_to_sheets(portfolio_data)
                    self.logger.info("Portfolio data synced to Google Sheets")
                except Exception as e:
                    self.logger.error(f"Failed to sync portfolio to sheets: {e}")

            self.logger.info("Daily report generated successfully")

        except Exception as e:
            self.logger.error(f"Daily report generation failed: {e}")

    async def handle_alert(self, alert):
        """處理告警"""
        self.logger.warning(f"ALERT: {alert.message}")

        # 同步到 Google Sheets
        if self.gas_monitor:
            try:
                await self.gas_monitor.sync_alert_to_sheets(alert)
            except Exception as e:
                self.logger.error(f"Failed to sync alert to sheets: {e}")

        # 可以整合郵件、SMS、推送通知等
        # await send_email_alert(alert)
        # await send_sms_alert(alert)

    async def handle_trade(self, trade):
        """處理交易"""
        self.logger.info(f"TRADE: {trade.symbol} {trade.side} {trade.quantity} @ {trade.price:.2f}")

        # 同步投資組合狀態到 Google Sheets
        if self.gas_monitor:
            try:
                portfolio_data = self.trader.get_portfolio_summary()['positions_detail']
                await self.gas_monitor.sync_portfolio_to_sheets(portfolio_data)
            except Exception as e:
                self.logger.error(f"Failed to sync portfolio to sheets: {e}")

        # 可以記錄到資料庫、發送通知等
        # await save_trade_to_db(trade)
        # await send_trade_notification(trade)

    async def _save_report(self, report: str):
        """儲存報告"""
        filename = f"reports/daily_report_{datetime.now().strftime('%Y%m%d')}.md"
        with open(filename, 'w', encoding='utf-8') as f:
            f.write(report)

    async def _save_system_state(self):
        """儲存系統狀態"""
        # 儲存投資組合狀態
        portfolio = self.trader.get_portfolio_summary()

        # 儲存到檔案
        state = {
            "timestamp": datetime.now().isoformat(),
            "portfolio": portfolio,
            "active_rules": len(self.trader.trading_rules),
            "active_alerts": len(self.monitor.alert_rules),
        }

        with open('logs/system_state.json', 'w', encoding='utf-8') as f:
            json.dump(state, f, ensure_ascii=False, indent=2)

    async def run_command(self, command: str, args: List[str]):
        """執行命令"""
        if command == "status":
            await self.show_status()
        elif command == "report":
            await self.generate_daily_report()
        elif command == "predict":
            await self.show_predictions(args)
        elif command == "portfolio":
            await self.show_portfolio()
        else:
            print(f"Unknown command: {command}")

    async def show_status(self):
        """顯示系統狀態"""
        portfolio = self.trader.get_portfolio_summary()

        print("=== Financial System Status ===")
        print(f"Running: {self.running}")
        print(f"Portfolio Value: ${portfolio['total_value']:,.2f}")
        print(f"Active Positions: {portfolio['positions']}")
        print(f"Total Trades: {portfolio['total_trades']}")
        print(f"Win Rate: {portfolio['winning_trades']/(portfolio['total_trades'] or 1):.1%}")
        print(f"Active Trading Rules: {len(self.trader.trading_rules)}")
        print(f"Active Alert Rules: {len(self.monitor.alert_rules)}")

    async def show_predictions(self, symbols: List[str]):
        """顯示預測"""
        if not symbols:
            symbols = ["AAPL", "NVDA", "2330.TW", "^GSPC"]

        print("=== Trend Predictions ===")
        for symbol in symbols:
            prediction = await self.predictor.predict_trend(symbol)
            if prediction:
                print(f"{symbol}: {prediction.predicted_direction.upper()} "
                      f"(Confidence: {prediction.confidence_score:.1%}, "
                      f"Change: {prediction.predicted_change_pct:.1f}%)")
            else:
                print(f"{symbol}: No prediction available")

    async def show_portfolio(self):
        """顯示投資組合"""
        portfolio = self.trader.get_portfolio_summary()

        print("=== Portfolio Summary ===")
        print(f"Total Value: ${portfolio['total_value']:,.2f}")
        print(f"Positions: {portfolio['positions']}")

        if portfolio['positions_detail']:
            print("\nPositions:")
            for pos in portfolio['positions_detail']:
                pnl_color = "🟢" if pos['unrealized_pnl'] >= 0 else "🔴"
                print(f"  {pos['symbol']}: {pos['quantity']} shares @ {pos['entry_price']:.2f} "
                      f"(Current: {pos['current_price']:.2f}) {pnl_color}${pos['unrealized_pnl']:,.2f}")


async def main():
    parser = argparse.ArgumentParser(description="Financial System")
    parser.add_argument("command", nargs="?", choices=["start", "status", "report", "predict", "portfolio"],
                       help="Command to execute")
    parser.add_argument("--symbols", nargs="*", help="Symbols for prediction")
    parser.add_argument("--init-only", action="store_true", help="Only initialize, don't start")

    args = parser.parse_args()

    system = FinancialSystem()

    if args.command == "start":
        await system.initialize_system()
        if not args.init_only:
            await system.start_system()
    elif args.command in ["status", "report", "predict", "portfolio"]:
        await system.initialize_system()
        await system.run_command(args.command, args.symbols or [])
    else:
        # 預設啟動系統
        await system.initialize_system()
        await system.start_system()


if __name__ == "__main__":
    asyncio.run(main())