from __future__ import annotations

import asyncio
import json
import logging
from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal, ROUND_DOWN
from typing import Dict, List, Optional, Callable

from financial_system.config import DB_PATH, load_settings
from financial_system.trend_predictor import TrendPredictor, TrendPrediction
from financial_system.realtime_monitor import RealTimeMonitor, Alert


@dataclass
class TradingRule:
    """交易規則配置"""
    id: str
    name: str
    symbol: str
    strategy: str  # "trend_following", "mean_reversion", "breakout", "custom"
    entry_conditions: Dict[str, any]
    exit_conditions: Dict[str, any]
    position_size_pct: float  # 倉位百分比
    stop_loss_pct: float
    take_profit_pct: float
    max_holding_days: int
    enabled: bool = True


@dataclass
class Position:
    """持倉資訊"""
    symbol: str
    quantity: int
    entry_price: float
    entry_date: datetime
    current_price: float
    unrealized_pnl: float
    stop_loss_price: float
    take_profit_price: float
    rule_id: str


@dataclass
class Trade:
    """交易記錄"""
    id: str
    symbol: str
    side: str  # "buy", "sell"
    quantity: int
    price: float
    timestamp: datetime
    rule_id: str
    pnl: Optional[float] = None
    notes: str = ""


class AutomatedTrader:
    """自動化交易系統"""

    def __init__(self):
        self.settings = load_settings()
        self.db_path = DB_PATH

        # 交易規則
        self.trading_rules: Dict[str, TradingRule] = {}

        # 持倉管理
        self.positions: Dict[str, Position] = {}

        # 交易歷史
        self.trade_history: List[Trade] = []

        # 風險管理
        self.daily_pnl_limit = self.settings.daily_pnl_limit or 10000
        self.max_positions = self.settings.max_positions or 10
        self.total_portfolio_value = self.settings.initial_capital or 100000

        # 依賴組件
        self.trend_predictor = TrendPredictor()
        self.monitor = RealTimeMonitor()

        # 交易回調
        self.trade_callbacks: List[Callable[[Trade], None]] = []

        self.setup_logging()

    def setup_logging(self):
        """設定日誌"""
        logging.basicConfig(
            filename='logs/automated_trader.log',
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s'
        )
        self.logger = logging.getLogger(__name__)

    def add_trading_rule(self, rule: TradingRule):
        """新增交易規則"""
        self.trading_rules[rule.id] = rule
        self.logger.info(f"Added trading rule: {rule.name} for {rule.symbol}")

    def remove_trading_rule(self, rule_id: str):
        """移除交易規則"""
        if rule_id in self.trading_rules:
            del self.trading_rules[rule_id]
            self.logger.info(f"Removed trading rule: {rule_id}")

    def add_trade_callback(self, callback: Callable[[Trade], None]):
        """新增交易回調函數"""
        self.trade_callbacks.append(callback)

    async def start_trading(self):
        """啟動自動交易"""
        self.logger.info("Starting automated trading...")

        # 設定監控回調
        self.monitor.add_alert_callback(self._handle_market_alert)

        # 啟動監控任務
        monitor_task = asyncio.create_task(self.monitor.start_monitoring())

        # 啟動交易決策任務
        trading_task = asyncio.create_task(self._trading_loop())

        # 啟動風險管理任務
        risk_task = asyncio.create_task(self._risk_management_loop())

        await asyncio.gather(monitor_task, trading_task, risk_task)

    async def _trading_loop(self):
        """交易決策主循環"""
        while True:
            try:
                await self._evaluate_trading_opportunities()
                await self._check_exit_conditions()
                await asyncio.sleep(300)  # 5分鐘檢查一次

            except Exception as e:
                self.logger.error(f"Trading loop error: {e}")
                await asyncio.sleep(60)

    async def _risk_management_loop(self):
        """風險管理循環"""
        while True:
            try:
                await self._check_risk_limits()
                await self._update_portfolio_value()
                await asyncio.sleep(3600)  # 1小時檢查一次

            except Exception as e:
                self.logger.error(f"Risk management error: {e}")
                await asyncio.sleep(60)

    async def _evaluate_trading_opportunities(self):
        """評估交易機會"""
        for rule in self.trading_rules.values():
            if not rule.enabled:
                continue

            try:
                # 檢查是否已有持倉
                if rule.symbol in self.positions:
                    continue

                # 檢查風險限制
                if not await self._check_entry_risk_limits(rule):
                    continue

                # 根據策略評估進場機會
                if await self._evaluate_entry_condition(rule):
                    await self._execute_entry_trade(rule)

            except Exception as e:
                self.logger.error(f"Error evaluating {rule.symbol}: {e}")

    async def _check_exit_conditions(self):
        """檢查出場條件"""
        positions_to_close = []

        for symbol, position in self.positions.items():
            rule = self.trading_rules.get(position.rule_id)
            if not rule:
                continue

            try:
                # 檢查停損
                if position.current_price <= position.stop_loss_price:
                    await self._execute_exit_trade(position, "stop_loss")
                    positions_to_close.append(symbol)
                    continue

                # 檢查停利
                if position.current_price >= position.take_profit_price:
                    await self._execute_exit_trade(position, "take_profit")
                    positions_to_close.append(symbol)
                    continue

                # 檢查持有時間限制
                holding_days = (datetime.now() - position.entry_date).days
                if holding_days >= rule.max_holding_days:
                    await self._execute_exit_trade(position, "time_limit")
                    positions_to_close.append(symbol)
                    continue

                # 檢查策略特定出場條件
                if await self._evaluate_exit_condition(rule, position):
                    await self._execute_exit_trade(position, "strategy_exit")
                    positions_to_close.append(symbol)
                    continue

            except Exception as e:
                self.logger.error(f"Error checking exit for {symbol}: {e}")

        # 移除已關閉的持倉
        for symbol in positions_to_close:
            del self.positions[symbol]

    async def _evaluate_entry_condition(self, rule: TradingRule) -> bool:
        """評估進場條件"""
        if rule.strategy == "trend_following":
            return await self._check_trend_following_entry(rule)
        elif rule.strategy == "mean_reversion":
            return await self._check_mean_reversion_entry(rule)
        elif rule.strategy == "breakout":
            return await self._check_breakout_entry(rule)
        else:
            return False

    async def _evaluate_exit_condition(self, rule: TradingRule, position: Position) -> bool:
        """評估出場條件"""
        if rule.strategy == "trend_following":
            return await self._check_trend_following_exit(rule, position)
        elif rule.strategy == "mean_reversion":
            return await self._check_mean_reversion_exit(rule, position)
        elif rule.strategy == "breakout":
            return await self._check_breakout_exit(rule, position)
        else:
            return False

    async def _check_trend_following_entry(self, rule: TradingRule) -> bool:
        """檢查趨勢跟隨進場條件"""
        prediction = await self.trend_predictor.predict_trend(rule.symbol)

        if not prediction:
            return False

        # 趨勢跟隨：預測看漲且信心夠高
        return (prediction.predicted_direction == "bullish" and
                prediction.confidence_score > rule.entry_conditions.get("min_confidence", 0.6))

    async def _check_mean_reversion_entry(self, rule: TradingRule) -> bool:
        """檢查均值回歸進場條件"""
        # 檢查價格是否偏離均線過遠
        current_price = await self._get_current_price(rule.symbol)
        sma_20 = await self._get_sma(rule.symbol, 20)

        if not current_price or not sma_20:
            return False

        deviation = (current_price - sma_20) / sma_20 * 100

        # 價格低於均線一定百分比
        return deviation < rule.entry_conditions.get("deviation_threshold", -5)

    async def _check_breakout_entry(self, rule: TradingRule) -> bool:
        """檢查突破進場條件"""
        # 檢查是否突破阻力線
        current_price = await self._get_current_price(rule.symbol)
        resistance = await self._get_resistance_level(rule.symbol)

        if not current_price or not resistance:
            return False

        # 價格突破阻力線
        return current_price > resistance * (1 + rule.entry_conditions.get("breakout_pct", 0.01))

    async def _check_trend_following_exit(self, rule: TradingRule, position: Position) -> bool:
        """檢查趨勢跟隨出場條件"""
        prediction = await self.trend_predictor.predict_trend(rule.symbol)

        if not prediction:
            return False

        # 趨勢轉向看跌
        return prediction.predicted_direction == "bearish"

    async def _check_mean_reversion_exit(self, rule: TradingRule, position: Position) -> bool:
        """檢查均值回歸出場條件"""
        current_price = position.current_price
        entry_price = position.entry_price

        # 價格回到均線附近
        profit_pct = (current_price - entry_price) / entry_price * 100
        return profit_pct > rule.exit_conditions.get("profit_target", 2)

    async def _check_breakout_exit(self, rule: TradingRule, position: Position) -> bool:
        """檢查突破出場條件"""
        # 檢查是否跌破支撐線
        support = await self._get_support_level(rule.symbol)
        return position.current_price < support

    async def _execute_entry_trade(self, rule: TradingRule):
        """執行進場交易"""
        try:
            current_price = await self._get_current_price(rule.symbol)
            if not current_price:
                return

            # 計算倉位大小
            position_value = self.total_portfolio_value * rule.position_size_pct
            quantity = int(position_value / current_price)

            if quantity <= 0:
                return

            # 計算停損和停利價格
            stop_loss_price = current_price * (1 - rule.stop_loss_pct)
            take_profit_price = current_price * (1 + rule.take_profit_pct)

            # 創建持倉
            position = Position(
                symbol=rule.symbol,
                quantity=quantity,
                entry_price=current_price,
                entry_date=datetime.now(),
                current_price=current_price,
                unrealized_pnl=0.0,
                stop_loss_price=stop_loss_price,
                take_profit_price=take_profit_price,
                rule_id=rule.id
            )

            self.positions[rule.symbol] = position

            # 記錄交易
            trade = Trade(
                id=f"entry_{rule.symbol}_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
                symbol=rule.symbol,
                side="buy",
                quantity=quantity,
                price=current_price,
                timestamp=datetime.now(),
                rule_id=rule.id,
                notes=f"Entry via {rule.strategy} strategy"
            )

            self.trade_history.append(trade)

            # 觸發回調
            for callback in self.trade_callbacks:
                await callback(trade)

            self.logger.info(f"Executed entry trade: {trade.id} - {rule.symbol} {quantity} shares @ {current_price:.2f}")

        except Exception as e:
            self.logger.error(f"Error executing entry trade for {rule.symbol}: {e}")

    async def _execute_exit_trade(self, position: Position, reason: str):
        """執行出場交易"""
        try:
            current_price = position.current_price

            # 計算盈虧
            pnl = (current_price - position.entry_price) * position.quantity

            # 記錄交易
            trade = Trade(
                id=f"exit_{position.symbol}_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
                symbol=position.symbol,
                side="sell",
                quantity=position.quantity,
                price=current_price,
                timestamp=datetime.now(),
                rule_id=position.rule_id,
                pnl=pnl,
                notes=f"Exit due to {reason}"
            )

            self.trade_history.append(trade)

            # 更新投資組合價值
            self.total_portfolio_value += pnl

            # 觸發回調
            for callback in self.trade_callbacks:
                await callback(trade)

            self.logger.info(f"Executed exit trade: {trade.id} - {position.symbol} {position.quantity} shares @ {current_price:.2f}, PnL: {pnl:.2f}")

        except Exception as e:
            self.logger.error(f"Error executing exit trade for {position.symbol}: {e}")

    async def _check_entry_risk_limits(self, rule: TradingRule) -> bool:
        """檢查進場風險限制"""
        # 檢查最大持倉數量
        if len(self.positions) >= self.max_positions:
            return False

        # 檢查倉位大小限制
        position_value = self.total_portfolio_value * rule.position_size_pct
        if position_value > self.total_portfolio_value * 0.1:  # 單一倉位不超過10%
            return False

        return True

    async def _check_risk_limits(self):
        """檢查整體風險限制"""
        # 計算當日盈虧
        today_trades = [t for t in self.trade_history
                       if t.timestamp.date() == datetime.now().date() and t.pnl is not None]

        daily_pnl = sum(t.pnl for t in today_trades)

        if abs(daily_pnl) > self.daily_pnl_limit:
            self.logger.warning(f"Daily PnL limit reached: {daily_pnl:.2f}")
            # 停止所有交易規則
            for rule in self.trading_rules.values():
                rule.enabled = False

    async def _update_portfolio_value(self):
        """更新投資組合價值"""
        total_value = self.settings.initial_capital or 100000

        for position in self.positions.values():
            try:
                current_price = await self._get_current_price(position.symbol)
                if current_price:
                    position.current_price = current_price
                    position.unrealized_pnl = (current_price - position.entry_price) * position.quantity
                    total_value += position.unrealized_pnl
            except Exception as e:
                self.logger.error(f"Error updating position for {position.symbol}: {e}")

        self.total_portfolio_value = total_value

    async def _handle_market_alert(self, alert: Alert):
        """處理市場告警"""
        # 根據告警調整交易策略
        if alert.severity in ["high", "critical"]:
            # 高風險告警：減少倉位或停止交易
            for rule in self.trading_rules.values():
                if rule.symbol == alert.symbol:
                    rule.position_size_pct *= 0.5  # 減半倉位
                    self.logger.info(f"Reduced position size for {rule.symbol} due to alert")

    # 資料獲取方法 (需要實現)
    async def _get_current_price(self, symbol: str) -> Optional[float]:
        """獲取當前價格"""
        # TODO: 實現即時價格獲取
        return 100.0

    async def _get_sma(self, symbol: str, period: int) -> Optional[float]:
        """獲取簡單移動平均"""
        # TODO: 實現技術指標計算
        return 100.0

    async def _get_resistance_level(self, symbol: str) -> Optional[float]:
        """獲取阻力線"""
        # TODO: 實現技術分析
        return 110.0

    async def _get_support_level(self, symbol: str) -> Optional[float]:
        """獲取支撐線"""
        # TODO: 實現技術分析
        return 90.0

    def get_portfolio_summary(self) -> Dict:
        """獲取投資組合摘要"""
        return {
            "total_value": self.total_portfolio_value,
            "positions": len(self.positions),
            "total_trades": len(self.trade_history),
            "winning_trades": len([t for t in self.trade_history if t.pnl and t.pnl > 0]),
            "losing_trades": len([t for t in self.trade_history if t.pnl and t.pnl < 0]),
            "positions_detail": [
                {
                    "symbol": p.symbol,
                    "quantity": p.quantity,
                    "entry_price": p.entry_price,
                    "current_price": p.current_price,
                    "unrealized_pnl": p.unrealized_pnl
                } for p in self.positions.values()
            ]
        }


# 使用範例
async def trade_logger(trade: Trade):
    """交易日誌記錄器"""
    print(f"📊 Trade: {trade.symbol} {trade.side.upper()} {trade.quantity} @ {trade.price:.2f}")
    if trade.pnl is not None:
        print(f"💰 PnL: {trade.pnl:.2f}")


async def main():
    trader = AutomatedTrader()

    # 新增交易規則
    rules = [
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

    for rule in rules:
        trader.add_trading_rule(rule)

    # 新增交易回調
    trader.add_trade_callback(trade_logger)

    # 啟動交易系統
    await trader.start_trading()


if __name__ == "__main__":
    asyncio.run(main())