from __future__ import annotations

import asyncio
import json
import logging
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestRegressor, GradientBoostingClassifier
from sklearn.preprocessing import StandardScaler
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score, mean_squared_error

from financial_system.config import DB_PATH, load_settings
from financial_system.llm import create_ai_report


@dataclass
class TrendPrediction:
    """趨勢預測結果"""
    symbol: str
    prediction_date: str
    predicted_direction: str  # "bullish", "bearish", "neutral"
    confidence_score: float
    predicted_change_pct: float
    time_horizon_days: int
    feature_importance: Dict[str, float]
    supporting_factors: List[str]


@dataclass
class MarketRegime:
    """市場狀態分類"""
    regime: str  # "bull_market", "bear_market", "sideways", "high_volatility"
    confidence: float
    indicators: Dict[str, float]
    description: str


class TrendPredictor:
    """AI 驅動趨勢預測系統"""

    def __init__(self):
        self.settings = load_settings()
        self.db_path = DB_PATH

        # 機器學習模型
        self.price_models: Dict[str, RandomForestRegressor] = {}
        self.direction_models: Dict[str, GradientBoostingClassifier] = {}
        self.regime_classifier = None

        # 特徵縮放器
        self.scalers: Dict[str, StandardScaler] = {}

        # 預測快取
        self.prediction_cache = {}
        self.cache_expiry = timedelta(hours=4)

        self.setup_logging()

    def setup_logging(self):
        """設定日誌"""
        logging.basicConfig(
            filename='logs/trend_predictor.log',
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s'
        )
        self.logger = logging.getLogger(__name__)

    async def train_models(self, symbols: List[str], lookback_days: int = 252):
        """訓練預測模型"""
        self.logger.info("Starting model training...")

        for symbol in symbols:
            try:
                # 獲取歷史資料
                features_df, target_df = await self._prepare_training_data(symbol, lookback_days)

                if len(features_df) < 50:
                    self.logger.warning(f"Insufficient data for {symbol}")
                    continue

                # 訓練價格預測模型
                await self._train_price_model(symbol, features_df, target_df)

                # 訓練方向預測模型
                await self._train_direction_model(symbol, features_df, target_df)

                self.logger.info(f"Trained models for {symbol}")

            except Exception as e:
                self.logger.error(f"Error training model for {symbol}: {e}")

        # 訓練市場狀態分類器
        await self._train_regime_classifier()

        self.logger.info("Model training completed")

    async def predict_trend(self, symbol: str, horizon_days: int = 30) -> Optional[TrendPrediction]:
        """預測特定股票的趨勢"""
        try:
            # 檢查快取
            cache_key = f"{symbol}_{horizon_days}"
            if cache_key in self.prediction_cache:
                cached_result, timestamp = self.prediction_cache[cache_key]
                if datetime.now() - timestamp < self.cache_expiry:
                    return cached_result

            # 獲取最新特徵
            features = await self._extract_features(symbol)

            if not features:
                return None

            # 價格預測
            price_model = self.price_models.get(symbol)
            direction_model = self.direction_models.get(symbol)

            if not price_model or not direction_model:
                return None

            # 標準化特徵
            scaler = self.scalers.get(symbol)
            if scaler:
                features_scaled = scaler.transform([list(features.values())])
            else:
                features_scaled = [list(features.values())]

            # 預測價格變動
            predicted_change = price_model.predict(features_scaled)[0]

            # 預測方向
            direction_prob = direction_model.predict_proba(features_scaled)[0]
            direction_classes = direction_model.classes_

            # 確定主要方向
            max_prob_idx = np.argmax(direction_prob)
            predicted_direction = direction_classes[max_prob_idx]
            confidence_score = direction_prob[max_prob_idx]

            # 獲取特徵重要性
            feature_importance = dict(zip(features.keys(),
                                         price_model.feature_importances_))

            # 生成支持因素說明
            supporting_factors = await self._generate_supporting_factors(
                symbol, features, predicted_direction, predicted_change
            )

            prediction = TrendPrediction(
                symbol=symbol,
                prediction_date=datetime.now().strftime("%Y-%m-%d"),
                predicted_direction=predicted_direction,
                confidence_score=float(confidence_score),
                predicted_change_pct=float(predicted_change),
                time_horizon_days=horizon_days,
                feature_importance=feature_importance,
                supporting_factors=supporting_factors
            )

            # 快取結果
            self.prediction_cache[cache_key] = (prediction, datetime.now())

            return prediction

        except Exception as e:
            self.logger.error(f"Error predicting trend for {symbol}: {e}")
            return None

    async def predict_market_regime(self) -> MarketRegime:
        """預測整體市場狀態"""
        try:
            # 收集市場指標
            indicators = await self._collect_market_indicators()

            if not indicators or not self.regime_classifier:
                return MarketRegime("unknown", 0.0, {}, "Unable to determine market regime")

            # 預測市場狀態
            indicators_scaled = self.regime_scaler.transform([list(indicators.values())])
            regime_prob = self.regime_classifier.predict_proba(indicators_scaled)[0]
            regime_classes = self.regime_classifier.classes_

            max_prob_idx = np.argmax(regime_prob)
            predicted_regime = regime_classes[max_prob_idx]
            confidence = regime_prob[max_prob_idx]

            # 生成描述
            description = self._generate_regime_description(predicted_regime, indicators)

            return MarketRegime(
                regime=predicted_regime,
                confidence=float(confidence),
                indicators=indicators,
                description=description
            )

        except Exception as e:
            self.logger.error(f"Error predicting market regime: {e}")
            return MarketRegime("error", 0.0, {}, f"Prediction error: {e}")

    async def generate_trend_report(self, symbols: List[str]) -> str:
        """生成趨勢預測報告"""
        try:
            # 獲取市場狀態
            market_regime = await self.predict_market_regime()

            # 獲取個股預測
            predictions = []
            for symbol in symbols:
                prediction = await self.predict_trend(symbol)
                if prediction:
                    predictions.append(prediction)

            # 使用 AI 生成報告
            report_data = {
                "market_regime": {
                    "regime": market_regime.regime,
                    "confidence": market_regime.confidence,
                    "description": market_regime.description,
                    "indicators": market_regime.indicators
                },
                "predictions": [
                    {
                        "symbol": p.symbol,
                        "direction": p.predicted_direction,
                        "confidence": p.confidence_score,
                        "change_pct": p.predicted_change_pct,
                        "supporting_factors": p.supporting_factors
                    } for p in predictions
                ],
                "generated_at": datetime.now().isoformat()
            }

            # 使用現有的 AI 摘要功能生成報告
            ai_report = await create_ai_report(
                api_key=self.settings.openai_api_key,
                model=self.settings.openai_model,
                day=datetime.now().strftime("%Y-%m-%d"),
                notes=[],  # 空筆記
                snapshots=[],  # 空快照
                movers=[],  # 空異動
                news_items=[],  # 空新聞
                trend_predictions=report_data
            )

            return ai_report if ai_report else json.dumps(report_data, ensure_ascii=False, indent=2)

        except Exception as e:
            self.logger.error(f"Error generating trend report: {e}")
            return f"Error generating trend report: {e}"

    async def _prepare_training_data(self, symbol: str, lookback_days: int) -> Tuple[pd.DataFrame, pd.DataFrame]:
        """準備訓練資料"""
        # 從資料庫獲取歷史資料
        historical_data = await self._get_historical_data(symbol, lookback_days + 30)

        features_list = []
        targets_list = []

        for i in range(30, len(historical_data) - 30):  # 確保有足夠的未來資料
            # 提取特徵
            features = await self._extract_features_from_historical(historical_data, i)
            features_list.append(features)

            # 提取目標 (30天後的價格變動)
            future_price = historical_data.iloc[i + 30]['close']
            current_price = historical_data.iloc[i]['close']
            price_change = (future_price - current_price) / current_price * 100

            # 分類目標 (看漲/看跌/中性)
            if price_change > 2:
                direction = "bullish"
            elif price_change < -2:
                direction = "bearish"
            else:
                direction = "neutral"

            targets_list.append({
                'price_change': price_change,
                'direction': direction
            })

        features_df = pd.DataFrame(features_list)
        targets_df = pd.DataFrame(targets_list)

        return features_df, targets_df

    async def _train_price_model(self, symbol: str, features_df: pd.DataFrame, targets_df: pd.DataFrame):
        """訓練價格預測模型"""
        # 分割訓練和測試資料
        X_train, X_test, y_train, y_test = train_test_split(
            features_df, targets_df['price_change'], test_size=0.2, random_state=42
        )

        # 特徵縮放
        scaler = StandardScaler()
        X_train_scaled = scaler.fit_transform(X_train)
        X_test_scaled = scaler.transform(X_test)

        # 訓練隨機森林模型
        model = RandomForestRegressor(
            n_estimators=100,
            max_depth=10,
            random_state=42,
            n_jobs=-1
        )
        model.fit(X_train_scaled, y_train)

        # 評估模型
        y_pred = model.predict(X_test_scaled)
        mse = mean_squared_error(y_test, y_pred)
        self.logger.info(f"{symbol} price model MSE: {mse:.4f}")

        self.price_models[symbol] = model
        self.scalers[symbol] = scaler

    async def _train_direction_model(self, symbol: str, features_df: pd.DataFrame, targets_df: pd.DataFrame):
        """訓練方向預測模型"""
        X_train, X_test, y_train, y_test = train_test_split(
            features_df, targets_df['direction'], test_size=0.2, random_state=42
        )

        scaler = self.scalers.get(symbol)
        if scaler:
            X_train_scaled = scaler.transform(X_train)
            X_test_scaled = scaler.transform(X_test)
        else:
            X_train_scaled, X_test_scaled = X_train, X_test

        # 訓練梯度提升分類器
        model = GradientBoostingClassifier(
            n_estimators=100,
            max_depth=6,
            random_state=42
        )
        model.fit(X_train_scaled, y_train)

        # 評估模型
        y_pred = model.predict(X_test_scaled)
        accuracy = accuracy_score(y_test, y_pred)
        self.logger.info(f"{symbol} direction model accuracy: {accuracy:.4f}")

        self.direction_models[symbol] = model

    async def _train_regime_classifier(self):
        """訓練市場狀態分類器"""
        # 收集歷史市場指標
        market_data = await self._get_market_regime_training_data()

        if len(market_data) < 50:
            self.logger.warning("Insufficient market data for regime classification")
            return

        features = market_data.drop('regime', axis=1)
        targets = market_data['regime']

        X_train, X_test, y_train, y_test = train_test_split(
            features, targets, test_size=0.2, random_state=42
        )

        # 特徵縮放
        self.regime_scaler = StandardScaler()
        X_train_scaled = self.regime_scaler.fit_transform(X_train)
        X_test_scaled = self.regime_scaler.transform(X_test)

        # 訓練分類器
        self.regime_classifier = GradientBoostingClassifier(
            n_estimators=100,
            max_depth=6,
            random_state=42
        )
        self.regime_classifier.fit(X_train_scaled, y_train)

        # 評估
        y_pred = self.regime_classifier.predict(X_test_scaled)
        accuracy = accuracy_score(y_test, y_pred)
        self.logger.info(f"Market regime classifier accuracy: {accuracy:.4f}")

    async def _extract_features(self, symbol: str) -> Dict[str, float]:
        """提取預測特徵"""
        # 技術指標
        features = {}

        # 價格動量
        features.update(await self._calculate_momentum_features(symbol))

        # 波動率指標
        features.update(await self._calculate_volatility_features(symbol))

        # 成交量指標
        features.update(await self._calculate_volume_features(symbol))

        # 技術指標
        features.update(await self._calculate_technical_features(symbol))

        # 市場寬度指標
        features.update(await self._calculate_market_breadth_features())

        return features

    async def _calculate_momentum_features(self, symbol: str) -> Dict[str, float]:
        """計算動量特徵"""
        # 簡化實現
        return {
            "momentum_5d": 0.0,
            "momentum_20d": 0.0,
            "momentum_60d": 0.0,
            "rsi_14": 50.0,
            "macd_signal": 0.0
        }

    async def _calculate_volatility_features(self, symbol: str) -> Dict[str, float]:
        """計算波動率特徵"""
        return {
            "volatility_20d": 0.0,
            "volatility_60d": 0.0,
            "bollinger_width": 0.0
        }

    async def _calculate_volume_features(self, symbol: str) -> Dict[str, float]:
        """計算成交量特徵"""
        return {
            "volume_ratio": 1.0,
            "volume_trend": 0.0
        }

    async def _calculate_technical_features(self, symbol: str) -> Dict[str, float]:
        """計算技術指標"""
        return {
            "sma_20_vs_price": 0.0,
            "sma_50_vs_price": 0.0,
            "ema_12_vs_ema_26": 0.0
        }

    async def _calculate_market_breadth_features(self) -> Dict[str, float]:
        """計算市場寬度指標"""
        return {
            "advance_decline_ratio": 1.0,
            "new_highs_new_lows": 0.0,
            "put_call_ratio": 1.0
        }

    async def _generate_supporting_factors(self, symbol: str, features: Dict[str, float],
                                         direction: str, change_pct: float) -> List[str]:
        """生成支持因素說明"""
        factors = []

        if direction == "bullish":
            if features.get("momentum_20d", 0) > 0:
                factors.append("20日動量指標為正")
            if features.get("rsi_14", 50) < 70:
                factors.append("RSI指標未過熱")
        elif direction == "bearish":
            if features.get("momentum_20d", 0) < 0:
                factors.append("20日動量指標為負")
            if features.get("volatility_20d", 0) > 0.3:
                factors.append("波動率較高")

        return factors

    def _generate_regime_description(self, regime: str, indicators: Dict[str, float]) -> str:
        """生成市場狀態描述"""
        descriptions = {
            "bull_market": "市場處於上升趨勢，主要指標顯示樂觀情緒",
            "bear_market": "市場處於下跌趨勢，風險指標升高",
            "sideways": "市場處於盤整狀態，缺乏明確方向",
            "high_volatility": "市場波動劇烈，投資者情緒不穩定"
        }
        return descriptions.get(regime, "市場狀態不明確")

    # 資料獲取方法 (需要實現)
    async def _get_historical_data(self, symbol: str, days: int) -> pd.DataFrame:
        """獲取歷史資料"""
        # TODO: 實現實際資料庫查詢
        return pd.DataFrame()

    async def _get_market_regime_training_data(self) -> pd.DataFrame:
        """獲取市場狀態訓練資料"""
        # TODO: 實現市場指標收集
        return pd.DataFrame()

    async def _collect_market_indicators(self) -> Dict[str, float]:
        """收集市場指標"""
        # TODO: 實現市場指標收集
        return {}


# 使用範例
async def main():
    predictor = TrendPredictor()

    # 訓練模型
    symbols = ["AAPL", "NVDA", "2330.TW", "^GSPC"]
    await predictor.train_models(symbols)

    # 生成預測
    for symbol in symbols:
        prediction = await predictor.predict_trend(symbol)
        if prediction:
            print(f"{symbol}: {prediction.predicted_direction} ({prediction.confidence_score:.2f})")

    # 生成趨勢報告
    report = await predictor.generate_trend_report(symbols)
    print(f"\nTrend Report:\n{report}")


if __name__ == "__main__":
    asyncio.run(main())