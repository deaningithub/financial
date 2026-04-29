"""
AI Analyzer Module
Uses OpenAI to analyze financial data and assess risks
"""
import os
import json
import logging
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

class FinancialAIAnalyzer:
    def __init__(self, api_key=None):
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        self.client = OpenAI(api_key=self.api_key)
        self.logger = logging.getLogger(__name__)
    
    def generate_summary(self, financial_data, news_items):
        """Generate AI summary of financial situation"""
        try:
            # Prepare context
            stock_summary = "\n".join([
                f"- {symbol}: ${info['price']} ({info['change_percent']:+.2f}%)"
                for symbol, info in financial_data.get("stocks", {}).items()
            ])
            
            news_summary = "\n".join([
                f"- {item['title']} (Source: {item['source']})"
                for item in news_items[:10]  # Top 10 news
            ])
            
            prompt = f"""
Analyze the following financial data and provide a concise summary:

**Stock Performance:**
{stock_summary}

**Recent News:**
{news_summary}

Please provide:
1. Key market movements
2. Main news drivers
3. Short-term outlook
"""
            
            response = self.client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": "You are a financial analyst expert."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.7,
                max_tokens=500
            )
            
            return response.choices[0].message.content
        
        except Exception as e:
            self.logger.error(f"Error generating summary: {str(e)}")
            return None
    
    def assess_risk(self, changes, financial_data):
        """Assess risk level based on changes"""
        try:
            changes_text = json.dumps(changes, indent=2)
            
            prompt = f"""
Based on the following market changes, assess the financial risk:

{changes_text}

Provide a risk assessment with:
1. Overall Risk Level (Low/Medium/High/Critical)
2. Risk Factors
3. Recommended Actions
4. Portfolio Impact
"""
            
            response = self.client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": "You are a financial risk analyst."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.7,
                max_tokens=600
            )
            
            return response.choices[0].message.content
        
        except Exception as e:
            self.logger.error(f"Error assessing risk: {str(e)}")
            return None
    
    def investigate_change(self, symbol, price_change, related_news):
        """Investigate what caused a price change"""
        try:
            news_text = "\n".join([
                f"- {news['title']}" for news in related_news
            ])
            
            prompt = f"""
Investigate the significant price movement for {symbol} ({price_change:+.2f}%):

Related news:
{news_text}

Provide analysis on:
1. Likely causes of the price movement
2. Credibility of the news
3. Historical context
4. Future implications
"""
            
            response = self.client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": "You are a financial detective."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.7,
                max_tokens=600
            )
            
            return response.choices[0].message.content
        
        except Exception as e:
            self.logger.error(f"Error investigating change: {str(e)}")
            return None


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    analyzer = FinancialAIAnalyzer()
    print("AI Analyzer initialized")
