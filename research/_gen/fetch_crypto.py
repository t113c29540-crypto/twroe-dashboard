# -*- coding: utf-8 -*-
"""前50大加密貨幣（依市值）→ crypto.json
資料源：CoinGecko 免費公開 API（免金鑰、CORS 開放，看板可直接即時刷新）。
一次呼叫取得：現價/市值/24h/7d/30d/1y 變動/距歷史高點/7日走勢(降採樣28點)。
注意：加密貨幣無基本面(ROE/盈餘)，僅價格與市值面分析。非投資建議。
"""
import json, os, subprocess, datetime

GEN = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(GEN, "crypto.json")
URL = ("https://api.coingecko.com/api/v3/coins/markets"
       "?vs_currency=usd&order=market_cap_desc&per_page=50&page=1"
       "&sparkline=true&price_change_percentage=24h%2C7d%2C30d%2C1y")

def rnd(x, n=1):
    try: return round(float(x), n)
    except (TypeError, ValueError): return None

def main():
    out = subprocess.run(["curl", "-s", "-m", "40", URL], capture_output=True, text=True, timeout=60)
    data = json.loads(out.stdout)
    if not isinstance(data, list) or len(data) < 30:
        print(f"✗ CoinGecko 資料不足({len(data) if isinstance(data,list) else data})。不覆寫 crypto.json。")
        raise SystemExit(1)
    coins = []
    for c in data[:50]:
        spark = ((c.get("sparkline_in_7d") or {}).get("price")) or []
        step = max(1, len(spark)//28)
        coins.append({
            "rank": c.get("market_cap_rank"),
            "sym": (c.get("symbol") or "").upper(),
            "name": c.get("name"),
            "price": rnd(c.get("current_price"), 4),
            "mcap": c.get("market_cap"),
            "ret": {"d": rnd(c.get("price_change_percentage_24h_in_currency")),
                    "w": rnd(c.get("price_change_percentage_7d_in_currency")),
                    "m": rnd(c.get("price_change_percentage_30d_in_currency")),
                    "y": rnd(c.get("price_change_percentage_1y_in_currency"))},
            "ath": rnd(c.get("ath_change_percentage")),          # 距歷史高點%
            "spark": [rnd(v, 4) for v in spark[::step]][:28],    # 7日走勢降採樣
        })
    payload = {"date": datetime.date.today().isoformat(),
               "source": "CoinGecko 公開API；市值前50；無基本面僅價格/市值；非投資建議",
               "count": len(coins), "coins": coins}
    tmp = OUT + ".tmp"
    json.dump(payload, open(tmp, "w", encoding="utf-8"), ensure_ascii=False)
    os.replace(tmp, OUT)
    print(f"✓ crypto.json（{len(coins)} 檔）")
    for c in coins[:5]:
        print(f"   #{c['rank']:<3}{c['sym']:<6}{str(c['price']):<12}日{c['ret']['d']}% 年{c['ret']['y']}% 距ATH {c['ath']}%")

if __name__ == "__main__":
    main()
