from __future__ import annotations

import asyncio
import json
import logging
import time
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Callable

import aiohttp
import websockets

from financial_system.config import DB_PATH, load_settings
from financial_system.market import MarketSnapshot


@dataclass
class AlertRule:
    """告警規則配置"""
    id: str
    name: str
    symbol: str
    condition: str  # "price_above", "price_below", "change_pct", "volume_spike"
    threshold: float
    cooldown_minutes: int = 60
    enabled: bool = True
    last_triggered: Optional[datetime] = None


@dataclass
class Alert:
    """告警事件"""
    rule_id: str
    symbol: str
    message: str
    severity: str  # "low", "medium", "high", "critical"
    timestamp: datetime
    current_value: float
    threshold: float


class RealTimeMonitor:
    """即時市場監控系統"""

    def __init__(self):
        self.settings = load_settings()
        self.alert_rules: Dict[str, AlertRule] = {}
        self.active_connections: set = set()
        self.monitoring_symbols: set = set()
        self.last_prices: Dict[str, float] = {}
        self.alert_callbacks: List[Callable[[Alert], None]] = []

        # 監控間隔 (秒)
        self.price_check_interval = 60  # 1分鐘
        self.news_check_interval = 300  # 5分鐘
        self.volatility_check_interval = 600  # 10分鐘

        self.setup_logging()

    def setup_logging(self):
        """設定日誌"""
        logging.basicConfig(
            filename='logs/realtime_monitor.log',
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s'
        )
        self.logger = logging.getLogger(__name__)

    def add_alert_rule(self, rule: AlertRule):
        """新增告警規則"""
        self.alert_rules[rule.id] = rule
        self.monitoring_symbols.add(rule.symbol)
        self.logger.info(f"Added alert rule: {rule.name} for {rule.symbol}")

    def remove_alert_rule(self, rule_id: str):
        """移除告警規則"""
        if rule_id in self.alert_rules:
            rule = self.alert_rules[rule_id]
            self.monitoring_symbols.discard(rule.symbol)
            del self.alert_rules[rule_id]
            self.logger.info(f"Removed alert rule: {rule_id}")

    def add_alert_callback(self, callback: Callable[[Alert], None]):
        """新增告警回調函數"""
        self.alert_callbacks.append(callback)

    async def start_monitoring(self):
        """啟動即時監控"""
        self.logger.info("Starting real-time monitoring...")

        # 建立監控任務
        tasks = [
            self._monitor_prices(),
            self._monitor_news(),
            self._monitor_volatility(),
            self._websocket_server(),
        ]

        await asyncio.gather(*tasks)

    async def _monitor_prices(self):
        """監控價格變動"""
        while True:
            try:
                for symbol in self.monitoring_symbols:
                    await self._check_price_alerts(symbol)

                await asyncio.sleep(self.price_check_interval)

            except Exception as e:
                self.logger.error(f"Price monitoring error: {e}")
                await asyncio.sleep(60)

    async def _monitor_news(self):
        """監控新聞更新"""
        while True:
            try:
                # 檢查重要新聞
                await self._check_news_alerts()

                await asyncio.sleep(self.news_check_interval)

            except Exception as e:
                self.logger.error(f"News monitoring error: {e}")
                await asyncio.sleep(60)

    async def _monitor_volatility(self):
        """監控波動率變化"""
        while True:
            try:
                # 檢查 VIX 和其他波動指標
                await self._check_volatility_alerts()

                await asyncio.sleep(self.volatility_check_interval)

            except Exception as e:
                self.logger.error(f"Volatility monitoring error: {e}")
                await asyncio.sleep(60)

    async def _check_price_alerts(self, symbol: str):
        """檢查價格告警"""
        try:
            # 獲取最新價格 (這裡需要實現實際的即時價格獲取)
            current_price = await self._get_realtime_price(symbol)

            if symbol not in self.last_prices:
                self.last_prices[symbol] = current_price
                return

            last_price = self.last_prices[symbol]
            price_change_pct = (current_price - last_price) / last_price * 100

            # 檢查所有適用於此股票的規則
            for rule in self.alert_rules.values():
                if rule.symbol != symbol or not rule.enabled:
                    continue

                # 檢查冷卻時間
                if rule.last_triggered and \
                   (datetime.now() - rule.last_triggered).seconds < rule.cooldown_minutes * 60:
                    continue

                triggered = False
                message = ""

                if rule.condition == "price_above" and current_price > rule.threshold:
                    triggered = True
                    message = f"{symbol} 價格突破 {rule.threshold:.2f}，目前 {current_price:.2f}"

                elif rule.condition == "price_below" and current_price < rule.threshold:
                    triggered = True
                    message = f"{symbol} 價格跌破 {rule.threshold:.2f}，目前 {current_price:.2f}"

                elif rule.condition == "change_pct" and abs(price_change_pct) > rule.threshold:
                    triggered = True
                    direction = "上漲" if price_change_pct > 0 else "下跌"
                    message = f"{symbol} {direction} {price_change_pct:.2f}% 至 {current_price:.2f}"

                if triggered:
                    alert = Alert(
                        rule_id=rule.id,
                        symbol=symbol,
                        message=message,
                        severity=self._calculate_severity(price_change_pct),
                        timestamp=datetime.now(),
                        current_value=current_price,
                        threshold=rule.threshold
                    )

                    await self._trigger_alert(alert)
                    rule.last_triggered = datetime.now()

            self.last_prices[symbol] = current_price

        except Exception as e:
            self.logger.error(f"Error checking price alerts for {symbol}: {e}")

    async def _check_news_alerts(self):
        """檢查新聞告警"""
        try:
            # 獲取最新重要新聞
            urgent_news = await self._get_urgent_news()

            for news_item in urgent_news:
                # 檢查是否觸發關鍵字告警
                await self._analyze_news_sentiment(news_item)

        except Exception as e:
            self.logger.error(f"News alert check error: {e}")

    async def _check_volatility_alerts(self):
        """檢查波動率告警"""
        try:
            vix_level = await self._get_realtime_price("^VIX")

            # VIX 高於 30 發出警告
            if vix_level > 30:
                alert = Alert(
                    rule_id="vix_high",
                    symbol="^VIX",
                    message=f"VIX 波動率指數升至 {vix_level:.2f}，市場恐慌情緒升高",
                    severity="high" if vix_level > 35 else "medium",
                    timestamp=datetime.now(),
                    current_value=vix_level,
                    threshold=30.0
                )
                await self._trigger_alert(alert)

        except Exception as e:
            self.logger.error(f"Volatility alert check error: {e}")

    async def _trigger_alert(self, alert: Alert):
        """觸發告警"""
        self.logger.warning(f"ALERT: {alert.message}")

        # 發送給所有回調函數
        for callback in self.alert_callbacks:
            try:
                await callback(alert)
            except Exception as e:
                self.logger.error(f"Alert callback error: {e}")

        # 廣播給 WebSocket 連接
        await self._broadcast_alert(alert)

    async def _websocket_server(self):
        """WebSocket 服務器用於即時更新"""
        try:
            server = await websockets.serve(
                self._handle_websocket,
                "localhost",
                8765
            )
            self.logger.info("WebSocket server started on ws://localhost:8765")
            await server.wait_closed()
        except Exception as e:
            self.logger.error(f"WebSocket server error: {e}")

    async def _handle_websocket(self, websocket, path):
        """處理 WebSocket 連接"""
        self.active_connections.add(websocket)
        try:
            await websocket.wait_closed()
        finally:
            self.active_connections.remove(websocket)

    async def _broadcast_alert(self, alert: Alert):
        """廣播告警給所有連接"""
        message = {
            "type": "alert",
            "data": {
                "rule_id": alert.rule_id,
                "symbol": alert.symbol,
                "message": alert.message,
                "severity": alert.severity,
                "timestamp": alert.timestamp.isoformat(),
                "current_value": alert.current_value,
                "threshold": alert.threshold
            }
        }

        # 移除已斷開的連接
        disconnected = set()
        for connection in self.active_connections:
            try:
                await connection.send(json.dumps(message))
            except:
                disconnected.add(connection)

        self.active_connections -= disconnected

    def _calculate_severity(self, change_pct: float) -> str:
        """根據變動幅度計算嚴重程度"""
        abs_change = abs(change_pct)
        if abs_change >= 10:
            return "critical"
        elif abs_change >= 5:
            return "high"
        elif abs_change >= 2:
            return "medium"
        else:
            return "low"

    # 資料獲取方法 (需要實現實際 API 調用)
    async def _get_realtime_price(self, symbol: str) -> float:
        """獲取即時價格"""
        # TODO: 實現實際即時價格 API
        # 可以使用 Alpha Vantage, IEX Cloud, 或其他即時資料源
        return 100.0  # 模擬值

    async def _get_urgent_news(self) -> List[Dict]:
        """獲取緊急新聞"""
        # TODO: 實現新聞監控 API
        return []

    async def _analyze_news_sentiment(self, news_item: Dict):
        """分析新聞情緒"""
        # TODO: 實現情緒分析
        pass


# 使用範例
async def alert_handler(alert: Alert):
    """告警處理函數"""
    print(f"🚨 {alert.severity.upper()}: {alert.message}")

    # 可以整合郵件、SMS、推送通知等
    # await send_email_alert(alert)
    # await send_sms_alert(alert)


async def main():
    monitor = RealTimeMonitor()

    # 新增告警規則
    rules = [
        AlertRule("aapl_high", "AAPL 高價告警", "AAPL", "price_above", 250.0),
        AlertRule("nvda_drop", "NVDA 下跌告警", "NVDA", "change_pct", -5.0),
        AlertRule("vix_spike", "VIX 恐慌指數", "^VIX", "price_above", 30.0),
    ]

    for rule in rules:
        monitor.add_alert_rule(rule)

    # 新增告警處理器
    monitor.add_alert_callback(alert_handler)

    # 啟動監控
    await monitor.start_monitoring()


if __name__ == "__main__":
    asyncio.run(main())