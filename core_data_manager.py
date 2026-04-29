"""
Financial Data Manager
Handles data collection, storage, and analysis
"""
import json
import os
from datetime import datetime
from pathlib import Path
import logging

class FinancialDataManager:
    def __init__(self, data_dir="data"):
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(exist_ok=True)
        self.logger = logging.getLogger(__name__)
        
    def get_today_file(self):
        """Get today's data file path"""
        date_str = datetime.now().strftime("%Y-%m-%d")
        return self.data_dir / f"financial_data_{date_str}.json"
    
    def load_today_data(self):
        """Load today's financial data"""
        file_path = self.get_today_file()
        if file_path.exists():
            with open(file_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        return self._create_empty_data()
    
    def _create_empty_data(self):
        """Create empty data structure"""
        return {
            "date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "stocks": {},
            "indices": {},
            "news": [],
            "changes": [],
            "analysis": None
        }
    
    def save_today_data(self, data):
        """Save today's financial data"""
        file_path = self.get_today_file()
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        self.logger.info(f"Data saved to {file_path}")
    
    def add_stock_data(self, symbol, price, change_percent, volume):
        """Add stock data to today's record"""
        data = self.load_today_data()
        data["stocks"][symbol] = {
            "price": price,
            "change_percent": change_percent,
            "volume": volume,
            "timestamp": datetime.now().strftime("%H:%M:%S")
        }
        self.save_today_data(data)
    
    def add_news_item(self, title, source, url, keywords):
        """Add news item to today's record"""
        data = self.load_today_data()
        data["news"].append({
            "title": title,
            "source": source,
            "url": url,
            "keywords": keywords,
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        })
        self.save_today_data(data)
    
    def detect_significant_changes(self, threshold_percent=2.5):
        """Detect stocks with significant price changes"""
        data = self.load_today_data()
        significant = []
        
        for symbol, info in data["stocks"].items():
            if abs(info["change_percent"]) >= threshold_percent:
                significant.append({
                    "symbol": symbol,
                    "change": info["change_percent"],
                    "price": info["price"],
                    "needs_investigation": True
                })
        
        data["changes"] = significant
        self.save_today_data(data)
        return significant
    
    def get_historical_comparison(self, symbol, days=30):
        """Compare stock performance over time"""
        results = []
        for i in range(days):
            date_offset = datetime.now().replace(day=datetime.now().day - i)
            file_name = date_offset.strftime("financial_data_%Y-%m-%d.json")
            file_path = self.data_dir / file_name
            
            if file_path.exists():
                with open(file_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    if symbol in data["stocks"]:
                        results.append({
                            "date": date_offset.strftime("%Y-%m-%d"),
                            "data": data["stocks"][symbol]
                        })
        
        return results


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    manager = FinancialDataManager()
    
    # Test
    manager.add_stock_data("AAPL", 150.25, 2.5, 5000000)
    manager.add_news_item(
        "Apple announces new product", 
        "TechNews",
        "https://example.com",
        ["earnings", "technology"]
    )
    print("Data manager initialized successfully")
