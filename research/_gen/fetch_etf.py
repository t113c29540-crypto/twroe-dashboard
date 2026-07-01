# -*- coding: utf-8 -*-
"""台股 + 全球 ETF 前50名排名 → etf.json
排名依據：規模(totalAssets/AUM)換算美元。另顯示殖利率、今年來報酬(YTD)。
資料源：yfinance(Yahoo，免金鑰，全球可達；台股ETF 用 .TW 後綴)。
用法：python3 fetch_etf.py
"""
import json, os, datetime

GEN = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(GEN, "etf.json")

# (代號, 地區, 中文名)  台股ETF＋全球主要ETF
ETFS = [
    # 🇹🇼 台股 ETF
    ("0050.TW","台","元大台灣50"),("006208.TW","台","富邦台50"),("0056.TW","台","元大高股息"),
    ("00878.TW","台","國泰永續高股息"),("00919.TW","台","群益台灣精選高息"),("00929.TW","台","復華台灣科技優息"),
    ("00713.TW","台","元大台灣高息低波"),("00940.TW","台","元大台灣價值高息"),("00939.TW","台","統一台灣高息動能"),
    ("00692.TW","台","富邦公司治理"),("00850.TW","台","元大臺灣ESG永續"),("00646.TW","台","元大S&P500"),
    ("00757.TW","台","統一FANG+"),("00662.TW","台","富邦NASDAQ"),("00881.TW","台","國泰台灣5G+"),
    ("00891.TW","台","中信關鍵半導體"),("00679B.TW","台","元大美債20年"),("00687B.TW","台","國泰20年美債"),
    ("0051.TW","台","元大中型100"),("0052.TW","台","富邦科技"),("00895.TW","台","富邦未來車"),
    ("00751B.TW","台","元大AAA至A公司債"),
    # 🌐 全球 ETF(美股掛牌,USD)
    ("SPY","美","SPDR 標普500"),("VOO","美","Vanguard 標普500"),("IVV","美","iShares 標普500"),
    ("QQQ","美","Invesco 那斯達克100"),("VTI","美","Vanguard 美股全市場"),("VUG","美","Vanguard 成長"),
    ("VTV","美","Vanguard 價值"),("SCHD","美","Schwab 高股息"),("VYM","美","Vanguard 高股息"),
    ("VIG","美","Vanguard 股息成長"),("DIA","美","SPDR 道瓊"),("IWM","美","iShares 羅素2000"),
    ("VEA","成熟","Vanguard 成熟市場(不含美)"),("VWO","新興","Vanguard 新興市場"),("IEFA","成熟","iShares 核心成熟"),
    ("IEMG","新興","iShares 核心新興"),("VGK","歐","Vanguard 歐洲"),("EWJ","日","iShares 日本"),
    ("VT","全球","Vanguard 全世界股"),("AGG","美","iShares 美國綜合債"),("BND","美","Vanguard 美國全債"),
    ("GLD","商品","SPDR 黃金"),("XLK","美","科技類股"),("SMH","美","半導體"),
    ("VNQ","美","美國不動產REIT"),("XLF","美","金融類股"),
]

def num(x):
    try:
        if x is None: return None
        return float(x)
    except (ValueError, TypeError): return None

def fetch():
    import yfinance as yf
    # 匯率：USD/TWD(≈30)，把台股ETF規模換成美元才能同榜比大小
    fx = {}
    try:
        fx["TWD"] = num(yf.Ticker("TWD=X").info.get("regularMarketPrice"))
    except Exception: fx["TWD"] = None
    rows = []
    for code, region, cname in ETFS:
        try: info = yf.Ticker(code).info
        except Exception as e:
            print(f"  ! {code} 失敗 {repr(e)[:50]}"); continue
        cur = info.get("currency") or "USD"
        price = num(info.get("navPrice")) or num(info.get("regularMarketPrice")) or num(info.get("currentPrice"))
        aum = num(info.get("totalAssets"))
        # 換算美元(TWD→USD;其餘視為美元)
        aum_usd = None
        if aum is not None:
            aum_usd = aum/fx["TWD"] if (cur == "TWD" and fx.get("TWD")) else (aum if cur == "USD" else None)
        yld = num(info.get("yield"))
        ytd = num(info.get("ytdReturn"))
        rows.append({
            "code": code, "region": region, "name": cname,
            "enName": info.get("shortName") or code,
            "price": round(price, 2) if price else None, "cur": cur,
            "aum": aum, "aumUsd": aum_usd,
            "yieldPct": round(yld*100, 2) if yld is not None else None,
            "ytdPct": round(ytd, 1) if ytd is not None else None,   # yfinance ytdReturn 已是百分比數
            "chgPct": num(info.get("regularMarketChangePercent")),
        })
        print(f"  {'✓' if price else '?'} {code:<10}{cname[:12]:<14} 規模USD{round(aum_usd/1e9,1) if aum_usd else '—'}B 殖{rows[-1]['yieldPct']}% YTD{rows[-1]['ytdPct']}", flush=True)
    return rows

def main():
    rows = fetch()
    valid = [r for r in rows if r.get("price")]
    if len(valid) < max(10, len(ETFS)//2):
        print(f"✗ ETF 資料不足：{len(valid)}/{len(ETFS)} 有價。不覆寫 etf.json。")
        raise SystemExit(1)
    # 依規模(美元)排名；無規模者排末
    rows.sort(key=lambda r: -(r["aumUsd"] or -1))
    for i, r in enumerate(rows[:50], 1): r["rank"] = i
    rows = rows[:50]
    payload = {"date": datetime.date.today().isoformat(),
               "source": "Yahoo Finance (yfinance)；規模換算美元排名；非投資建議",
               "count": len(rows), "etfs": rows}
    tmp = OUT + ".tmp"
    json.dump(payload, open(tmp, "w", encoding="utf-8"), ensure_ascii=False)
    os.replace(tmp, OUT)
    print(f"\n✓ etf.json（前{len(rows)}名，{len(valid)} 有價）→ {OUT}")

if __name__ == "__main__":
    main()
