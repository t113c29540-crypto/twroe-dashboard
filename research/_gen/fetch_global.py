# -*- coding: utf-8 -*-
"""抓全球股市(美股/歐股等)現價＋ROE/本益比/淨值比 → global.json
資料源：yfinance(Yahoo Finance,免金鑰,全球可達;非官方API,壞了會優雅降級)。
與本專案高ROE主題一致：除了報價，重點抓 returnOnEquity / trailingPE / priceToBook。
注意：全球免費基本面僅「現值」，非台股那種16年逐年歷史。
用法：python3 fetch_global.py
"""
import json, os, datetime

GEN = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(GEN, "global.json")

# 全球觀察名單(可自行增刪)：美股大型權值＋歐股代表＋台積電ADR
TICKERS = [
    # 美股
    ("AAPL", "美"), ("MSFT", "美"), ("NVDA", "美"), ("GOOGL", "美"), ("AMZN", "美"),
    ("META", "美"), ("AVGO", "美"), ("LLY", "美"), ("V", "美"), ("MA", "美"),
    ("COST", "美"), ("UNH", "美"), ("JPM", "美"), ("HD", "美"), ("ADBE", "美"),
    ("TSM", "美ADR"),
    # 歐股(Yahoo 後綴：.SW瑞士 .PA法國 .CO哥本哈根 .AS荷蘭 .L倫敦)
    ("ASML", "歐"), ("NVO", "歐ADR"), ("NESN.SW", "歐"), ("MC.PA", "歐"),
    ("SAP", "歐"), ("AZN", "歐ADR"),
]

def num(x):
    try:
        if x is None: return None
        return round(float(x), 4)
    except (ValueError, TypeError): return None

def sane(x, lo, hi):
    """過濾 yfinance 海外資料常見的離譜值(幣別/單位錯亂)"""
    v = num(x)
    if v is None or v < lo or v > hi: return None
    return v

def fetch():
    import yfinance as yf
    rows = []
    for code, region in TICKERS:
        try:
            info = yf.Ticker(code).info
        except Exception as e:
            print(f"  ! {code} 失敗 {repr(e)[:60]}"); continue
        price = info.get("currentPrice") or info.get("regularMarketPrice")
        roe = info.get("returnOnEquity")  # 小數,如 0.45=45%
        roe_pct = round(roe*100, 1) if isinstance(roe, (int, float)) and abs(roe) <= 5 else None  # |ROE|>500% 視為壞值
        rows.append({
            "code": code, "region": region,
            "name": info.get("shortName") or code,
            "price": num(price),
            "chgPct": sane(info.get("regularMarketChangePercent"), -50, 50),
            "roe": roe_pct,
            "pe": sane(info.get("trailingPE"), 0, 500),    # 離譜值丟掉
            "pb": sane(info.get("priceToBook"), 0, 100),
            "mcap": info.get("marketCap"),
            "cur": info.get("currency") or "USD",
            "sector": info.get("sector") or "",
        })
        ok = "✓" if rows[-1]["price"] else "?"
        print(f"  {ok} {code:<9}{rows[-1]['name'][:22]:<24}價{rows[-1]['price']} ROE{rows[-1]['roe']}% PE{rows[-1]['pe']}", flush=True)
    return rows

def main():
    rows = fetch()
    # 品質關卡：抓到太少就不覆寫(避免 Yahoo 壞掉時發空資料)
    valid = [r for r in rows if r.get("price")]
    MIN_OK = max(6, len(TICKERS)//2)
    if len(valid) < MIN_OK:
        print(f"✗ 全球資料不足：{len(valid)}/{len(TICKERS)} 有價(門檻{MIN_OK})。不覆寫 global.json(保留上一版)。")
        raise SystemExit(1)
    rows.sort(key=lambda r: -(r["roe"] or -999))   # 依 ROE 由高到低(呼應高ROE主題)
    payload = {"date": datetime.date.today().isoformat(),
               "source": "Yahoo Finance (yfinance)；現值非歷史；非投資建議",
               "count": len(rows), "stocks": rows}
    tmp = OUT + ".tmp"
    json.dump(payload, open(tmp, "w", encoding="utf-8"), ensure_ascii=False)
    os.replace(tmp, OUT)
    print(f"\n✓ global.json（{len(rows)} 檔，{len(valid)} 有價）→ {OUT}")

if __name__ == "__main__":
    main()
