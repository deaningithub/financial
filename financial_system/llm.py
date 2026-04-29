from __future__ import annotations

from openai import OpenAI

from financial_system.market import MarketSnapshot
from financial_system.news import NewsItem


SYSTEM_PROMPT = """你是一位金融情報分析師，服務對象是台灣投資者。

請根據提供的市場數據、使用者筆記與新聞連結，產出每日市場摘要與風險評估。

規則：
- 全文使用繁體中文，語氣專業、清楚，貼近台灣投資者。
- 不要自行編造因果關係。若原因只來自新聞標題，請標示為「可能驅動因素」。
- 清楚區分事實、解讀與風險評估。
- 同時納入上行風險與下行風險。
- 保持精簡，但要足以支援投資者隔日追蹤。
- 這不是投資建議。
"""


def _market_lines(snapshots: list[MarketSnapshot]) -> str:
    lines = []
    for item in snapshots:
        lines.append(
            f"{item.name} ({item.symbol}, region={item.region}, type={item.asset_type}): price={item.last_price}, "
            f"daily_change_pct={item.daily_change_pct}, "
            f"5d_change_pct={item.five_day_change_pct}, "
            f"1m_change_pct={item.one_month_change_pct}, status={item.status}"
        )
    return "\n".join(lines)


def _news_lines(news_items: list[NewsItem]) -> str:
    return "\n".join(
        f"- [{item.query}] {item.title} ({item.source}) {item.link}"
        for item in news_items
    )


def create_ai_report(
    api_key: str,
    model: str,
    day: str,
    notes: str,
    snapshots: list[MarketSnapshot],
    movers: list[MarketSnapshot],
    news_items: list[NewsItem],
) -> str:
    client = OpenAI(api_key=api_key)
    mover_names = ", ".join(
        f"{mover.name} {mover.daily_change_pct:.2f}%"
        for mover in movers
        if mover.daily_change_pct is not None
    )
    user_prompt = f"""Date: {day}

User notes:
{notes or "No manual notes provided."}

Market data:
{_market_lines(snapshots)}

Biggest movers:
{mover_names or "No movers detected."}

Collected news:
{_news_lines(news_items) or "No news collected."}

請用繁體中文回答，並使用台灣投資者熟悉的表達方式。

請在解讀中固定納入以下「全球趨勢框架」，但只有在資料或新聞有支持時才做具體判斷：
- AI 晶片：GPU、HBM、先進封裝、資料中心資本支出、台積電與相關供應鏈。
- 衛星通訊：低軌衛星、衛星網路、地面設備、航太供應鏈。
- 機器人與車用科技：人形機器人、工業自動化、電動車、自動駕駛、車用半導體。
- 太空探索與登月：登月計畫、火箭發射、太空基礎建設、航太材料與零組件。

請用以下章節產出每日金融摘要與風險評估：
1. 執行摘要
2. 最大波動與可能驅動因素
3. 台股市場狀態
4. 全球趨勢觀察
5. 政治與公司政策觀察
6. 趨勢追蹤
7. 風險評估
8. 下一步觀察清單
"""
    response = client.responses.create(
        model=model,
        input=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ],
    )
    return response.output_text
