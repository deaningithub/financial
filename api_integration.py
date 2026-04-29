"""
API Integration Module
Handles stock data and news API calls
"""
import requests
import os
import logging
from dotenv import load_dotenv

load_dotenv()

class StockDataAPI:
    def __init__(self, api_key=None):
        self.api_key = api_key or os.getenv("STOCK_API_KEY")
        self.logger = logging.getLogger(__name__)
        
    def get_stock_quote(self, symbol):
        """Fetch stock quote from API"""
        # Example using Alpha Vantage API
        try:
            url = f"https://www.alphavantage.co/query"
            params = {
                "function": "GLOBAL_QUOTE",
                "symbol": symbol,
                "apikey": self.api_key
            }
            response = requests.get(url, params=params, timeout=10)
            data = response.json()
            
            if "Global Quote" in data:
                quote = data["Global Quote"]
                return {
                    "symbol": symbol,
                    "price": float(quote.get("05. price", 0)),
                    "change": float(quote.get("09. change", 0)),
                    "change_percent": float(quote.get("10. change percent", "0").rstrip("%")),
                    "volume": int(quote.get("06. volume", 0))
                }
        except Exception as e:
            self.logger.error(f"Error fetching {symbol}: {str(e)}")
        
        return None


class NewsAPI:
    def __init__(self, api_key=None):
        self.api_key = api_key or os.getenv("NEWS_API_KEY")
        self.logger = logging.getLogger(__name__)
    
    def search_news(self, keywords, days=1):
        """Search for financial news by keywords"""
        try:
            # Using NewsAPI.org
            url = "https://newsapi.org/v2/everything"
            
            query = " OR ".join(keywords)
            params = {
                "q": query,
                "sortBy": "publishedAt",
                "language": "en",
                "apiKey": self.api_key,
                "pageSize": 20
            }
            
            response = requests.get(url, params=params, timeout=10)
            data = response.json()
            
            articles = []
            if data.get("articles"):
                for article in data["articles"]:
                    articles.append({
                        "title": article.get("title"),
                        "source": article.get("source", {}).get("name"),
                        "url": article.get("url"),
                        "description": article.get("description"),
                        "publishedAt": article.get("publishedAt")
                    })
            
            return articles
        except Exception as e:
            self.logger.error(f"Error searching news: {str(e)}")
        
        return []


class WebScraper:
    def __init__(self):
        self.logger = logging.getLogger(__name__)
    
    def scrape_financial_data(self, url):
        """Scrape financial data from web"""
        try:
            from bs4 import BeautifulSoup
            response = requests.get(url, timeout=10)
            soup = BeautifulSoup(response.content, 'html.parser')
            
            return {
                "title": soup.title.string if soup.title else "N/A",
                "content": soup.get_text()[:500]  # First 500 chars
            }
        except Exception as e:
            self.logger.error(f"Error scraping {url}: {str(e)}")
        
        return None


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    
    # Test stock API
    stock_api = StockDataAPI()
    print("Stock API initialized")
    
    # Test news API
    news_api = NewsAPI()
    print("News API initialized")
