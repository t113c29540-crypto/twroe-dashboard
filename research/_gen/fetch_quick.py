# -*- coding: utf-8 -*-
"""盤中快刷：批次更新 global/etf/macro 的「現價與當日變動」＋ crypto 全欄位 → 原檔就地更新。
與完整抓取器(fetch_global/etf/macro)的差別：只用 yf.download 一次批次抓 5 日收盤（~1分鐘），
不動 ROE/規模/歷史 ret 的 w/m/q/y（那些每日完整跑一次即可）。
設計原因：Yahoo 擋公共 CORS 代理(實測 520/522)，前端無法直連——改由 GitHub Actions
（乾淨 IP）盤中每 2 小時執行本檔，前端每 5 分鐘輪詢 JSON。加密另由前端直連 CoinGecko(真即時)。
"""
import json, os, subprocess, datetime

GEN = os.path.dirname(os.path.abspath(__file__))

def load(p):
    try: return json.load(open(p, encoding="utf-8"))
    except Exception: return None

def save(p, d):
    tmp = p + ".tmp"
    json.dump(d, open(tmp, "w", encoding="utf-8"), ensure_ascii=False)
    os.replace(tmp, p)

def now_tw():
    return (datetime.datetime.utcnow() + datetime.timedelta(hours=8)).strftime("%Y-%m-%d %H:%M")

def main():
    import yfinance as yf
    g = load(os.path.join(GEN, "global.json"))
    e = load(os.path.join(GEN, "etf.json"))
    m = load(os.path.join(GEN, "macro.json"))
    syms = []
    if g: syms += [s["code"] for s in g.get("stocks", [])]
    if e: syms += [x["code"] for x in e.get("etfs", [])]
    if m:
        syms += [f["code"] + "=F" for f in m.get("futures", [])]
        syms += [y["code"] for y in m.get("yields", [])]
        syms += [b["code"] for b in m.get("bondEtf", [])]
    syms = list(dict.fromkeys(syms))
    print(f"批次抓 {len(syms)} 檔 5 日收盤…")
    df = yf.download(syms, period="5d", interval="1d", progress=False, group_by="ticker", threads=True)
    px = {}
    for s in syms:
        try:
            cl = df[s]["Close"].dropna()
            if len(cl) >= 2: px[s] = (float(cl.iloc[-1]), float(cl.iloc[-2]))
            elif len(cl) == 1: px[s] = (float(cl.iloc[-1]), None)
        except Exception: pass
    hit = len(px)
    print(f"命中 {hit}/{len(syms)}")
    if hit < len(syms) * 0.5:
        print("✗ 命中率過低（可能被限流），不更新任何檔案。")
        raise SystemExit(1)
    ts = now_tw()

    def upd(row, key):
        p = px.get(key)
        if not p: return
        last, prev = p
        row["price"] = round(last, 4 if last < 1 else 2)
        if prev:
            chg = round((last/prev - 1) * 100, 2)
            row["chgPct"] = chg
            row.setdefault("ret", {})["d"] = chg

    if g:
        for s in g.get("stocks", []): upd(s, s["code"])
        g["date"] = ts; save(os.path.join(GEN, "global.json"), g)
    if e:
        for x in e.get("etfs", []): upd(x, x["code"])
        e["date"] = ts; save(os.path.join(GEN, "etf.json"), e)
    if m:
        for f in m.get("futures", []): upd(f, f["code"] + "=F")
        for b in m.get("bondEtf", []): upd(b, b["code"])
        for y in m.get("yields", []):
            p = px.get(y["code"])
            if p and p[0]:
                fdiv = 10.0 if p[0] > 20 else 1.0
                y["pct"] = round(p[0]/fdiv, 2)
                if p[1]: y["bp"] = round((p[0]-p[1])/fdiv*100, 1)
        m["date"] = ts; save(os.path.join(GEN, "macro.json"), m)

    # 加密：CoinGecko 快照（保留原 spark）
    c = load(os.path.join(GEN, "crypto.json"))
    if c:
        try:
            url = ("https://api.coingecko.com/api/v3/coins/markets?vs_currency=usd&order=market_cap_desc"
                   "&per_page=50&page=1&price_change_percentage=24h%2C7d%2C30d%2C1y")
            out = subprocess.run(["curl","-s","-m","40",url], capture_output=True, text=True, timeout=60)
            arr = json.loads(out.stdout)
            if isinstance(arr, list) and len(arr) >= 30:
                spark = {x["sym"]: x.get("spark") for x in c.get("coins", [])}
                def rnd(v, n=1):
                    try: return round(float(v), n)
                    except (TypeError, ValueError): return None
                c["coins"] = [{"rank": x.get("market_cap_rank"), "sym": (x.get("symbol") or "").upper(),
                               "name": x.get("name"), "price": rnd(x.get("current_price"), 4),
                               "mcap": x.get("market_cap"),
                               "ret": {"d": rnd(x.get("price_change_percentage_24h_in_currency")),
                                       "w": rnd(x.get("price_change_percentage_7d_in_currency")),
                                       "m": rnd(x.get("price_change_percentage_30d_in_currency")),
                                       "y": rnd(x.get("price_change_percentage_1y_in_currency"))},
                               "ath": rnd(x.get("ath_change_percentage")),
                               "spark": spark.get((x.get("symbol") or "").upper())}
                              for x in arr[:50]]
                c["date"] = ts; save(os.path.join(GEN, "crypto.json"), c)
                print("✓ crypto 快照更新")
        except Exception as ex: print(f"  ! crypto 快照失敗 {repr(ex)[:50]}")
    print(f"✓ 快刷完成 {ts}（Yahoo命中 {hit}/{len(syms)}）")

if __name__ == "__main__":
    main()
