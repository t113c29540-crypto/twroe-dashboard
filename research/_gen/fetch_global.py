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

# 全球觀察名單(可自行增刪)：各市場前10大型權值股＋市場ETF。(code, 地區, 類型)
# 類型 stock=個股 etf=市場/ETF。Yahoo 後綴：.SW瑞士 .PA法國 .DE德國 .L倫敦 .AS荷蘭
#   .T東京 .KS首爾 .HK香港 .TW台灣 .TO多倫多 .AX雪梨
TICKERS = [
    # 🇺🇸 美股前10+
    ("AAPL","美","stock"),("MSFT","美","stock"),("NVDA","美","stock"),("GOOGL","美","stock"),
    ("AMZN","美","stock"),("META","美","stock"),("AVGO","美","stock"),("LLY","美","stock"),
    ("JPM","美","stock"),("V","美","stock"),("MA","美","stock"),("COST","美","stock"),
    ("UNH","美","stock"),("HD","美","stock"),("ORCL","美","stock"),("WMT","美","stock"),
    # 🇪🇺 歐股前10
    ("ASML","歐","stock"),("NVO","歐","stock"),("MC.PA","歐","stock"),("NESN.SW","歐","stock"),
    ("SAP","歐","stock"),("AZN","歐","stock"),("OR.PA","歐","stock"),("RMS.PA","歐","stock"),
    ("SIE.DE","歐","stock"),("NOVN.SW","歐","stock"),("SHEL","歐","stock"),("ROG.SW","歐","stock"),
    # 🇯🇵 日股前10
    ("7203.T","日","stock"),("6758.T","日","stock"),("6861.T","日","stock"),("9984.T","日","stock"),
    ("8306.T","日","stock"),("6098.T","日","stock"),("9433.T","日","stock"),("4063.T","日","stock"),
    ("6501.T","日","stock"),("7974.T","日","stock"),
    # 🇰🇷 韓 / 🇨🇳🇭🇰 中港 / 🇮🇳 印 ADR / 🇹🇼 台
    ("005930.KS","韓","stock"),("000660.KS","韓","stock"),
    ("TCEHY","中","stock"),("BABA","中","stock"),("0700.HK","港","stock"),
    ("INFY","印","stock"),("TSM","台ADR","stock"),
    # 🌐 市場/ETF(無ROE,只看價/趨勢)
    ("SPY","美","etf"),("QQQ","美","etf"),("VTI","美","etf"),("DIA","美","etf"),
    ("EFA","成熟","etf"),("VWO","新興","etf"),("VGK","歐","etf"),("EWJ","日","etf"),
    ("0050.TW","台","etf"),("VT","全球","etf"),
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
    for code, region, typ in TICKERS:
        try:
            info = yf.Ticker(code).info
        except Exception as e:
            print(f"  ! {code} 失敗 {repr(e)[:60]}"); continue
        price = info.get("currentPrice") or info.get("regularMarketPrice")
        roe = info.get("returnOnEquity")  # 小數,如 0.45=45%
        roe_pct = round(roe*100, 1) if isinstance(roe, (int, float)) and abs(roe) <= 5 else None  # |ROE|>500% 視為壞值
        rows.append({
            "code": code, "region": region, "type": typ,
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
