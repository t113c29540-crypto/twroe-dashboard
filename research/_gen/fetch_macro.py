# -*- coding: utf-8 -*-
"""主要期貨 ＋ 美債殖利率 ＋ 債券ETF → macro.json
資料源：Yahoo Finance(yfinance)。誠實範圍說明：
  - 期貨無「前50名」的公認清單——列 18 檔全球主要合約（指數/貴金屬/能源/農產/畜產），皆近月合約(有轉倉效應)。
  - 個別債券為 OTC 報價、免費拿不到——以「美債殖利率指數(CBOE ^IRX/^FVX/^TNX/^TYX)＋10檔債券ETF」為代理。
非投資建議。
"""
import json, os, datetime

GEN = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(GEN, "macro.json")

FUTURES = [("ES=F","標普500期"),("NQ=F","那斯達克期"),("YM=F","道瓊期"),("RTY=F","羅素2000期"),
           ("GC=F","黃金"),("SI=F","白銀"),("PL=F","白金"),("HG=F","銅"),
           ("CL=F","WTI原油"),("BZ=F","布蘭特原油"),("NG=F","天然氣"),
           ("ZC=F","玉米"),("ZW=F","小麥"),("ZS=F","黃豆"),
           ("SB=F","糖"),("KC=F","咖啡"),("CT=F","棉花"),("LE=F","活牛")]
YIELDS  = [("^IRX","美國3月期國庫券"),("^FVX","美國5年期公債"),("^TNX","美國10年期公債"),("^TYX","美國30年期公債")]
BONDETF = [("TLT","20年+美債ETF"),("IEF","7-10年美債"),("SHY","1-3年美債"),("AGG","美國綜合債"),
           ("BND","全債市"),("LQD","投資級公司債"),("HYG","高收益債"),("EMB","新興市場債"),
           ("TIP","抗通膨債"),("BNDX","國際債(美元避險)")]

def rets_from(h):
    out = {}
    if h is None or len(h) < 2: return out
    last = float(h.iloc[-1])
    for k, n in (("d",1),("w",5),("m",20),("q",60),("y",240)):
        if len(h) > n and float(h.iloc[-1-n]):
            out[k] = round((last/float(h.iloc[-1-n])-1)*100, 1)
    return out

def main():
    import yfinance as yf
    fut, yl, be = [], [], []
    for code, name in FUTURES:
        try:
            h = yf.Ticker(code).history(period="2y")["Close"].dropna()
            if len(h) < 2: continue
            fut.append({"code": code.replace("=F",""), "name": name,
                        "price": round(float(h.iloc[-1]), 2), "ret": rets_from(h)})
            print(f"  ✓ 期 {code:<6}{name:<8}{fut[-1]['price']} 日{fut[-1]['ret'].get('d')}%", flush=True)
        except Exception as e: print(f"  ! {code} {repr(e)[:40]}")
    for code, name in YIELDS:
        try:
            h = yf.Ticker(code).history(period="1mo")["Close"].dropna()
            if len(h) < 2: continue
            v, p = float(h.iloc[-1]), float(h.iloc[-2])
            f = 10.0 if v > 20 else 1.0            # CBOE 指數若為 10×% 自動換算
            yl.append({"code": code, "name": name, "pct": round(v/f, 2),
                       "bp": round((v-p)/f*100, 1)})   # 1日變動(基點)
            print(f"  ✓ 債 {code:<6}{name:<10}{yl[-1]['pct']}% ({yl[-1]['bp']:+}bp)", flush=True)
        except Exception as e: print(f"  ! {code} {repr(e)[:40]}")
    for code, name in BONDETF:
        try:
            h = yf.Ticker(code).history(period="2y")["Close"].dropna()
            if len(h) < 2: continue
            be.append({"code": code, "name": name,
                       "price": round(float(h.iloc[-1]), 2), "ret": rets_from(h)})
        except Exception as e: print(f"  ! {code} {repr(e)[:40]}")
    if len(fut) < 10 or len(be) < 5:
        print(f"✗ 資料不足(期{len(fut)}/債ETF{len(be)})。不覆寫 macro.json。")
        raise SystemExit(1)
    payload = {"date": datetime.date.today().isoformat(),
               "source": "Yahoo Finance；期貨=近月合約；債券=殖利率指數與債券ETF代理；非投資建議",
               "futures": fut, "yields": yl, "bondEtf": be}
    tmp = OUT + ".tmp"
    json.dump(payload, open(tmp, "w", encoding="utf-8"), ensure_ascii=False)
    os.replace(tmp, OUT)
    print(f"✓ macro.json（期貨{len(fut)} 殖利率{len(yl)} 債ETF{len(be)}）")

if __name__ == "__main__":
    main()
