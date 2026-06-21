# -*- coding: utf-8 -*-
"""季重排（全 FinMind，不碰 TWSE/TPEx，GitHub 雲端可跑）。
候選池：ranking.json 前 POOL 檔（季度間 top50 churn 幾乎都在此池內）。
排名：市場推算 ROE(=股價淨值比/本益比, FinMind TaiwanStockPER) 的「>15% 一致性 → 均ROE」(與初版方法一致)。
前50 再補「會計 ROE」(FinMind 財報) 供對帳。
產出：data50.json（與 gen_daily 共用 schema）。
用法：python3 scan_finmind.py [POOL]   （預設 150；測試給小數字）
"""
import json, os, sys, subprocess, urllib.parse, statistics, time

GEN = os.path.dirname(os.path.abspath(__file__))
RANKING = os.path.join(GEN, "ranking.json")
OUT = os.path.join(GEN, "data50.json")
FINMIND = "https://api.finmindtrade.com/api/v4/data"
WIN_START, WIN_END = 2010, 2025
MIN_YEARS = 10
NEED = 50

def fm(dataset, code, start, end, tries=4):
    q = urllib.parse.urlencode({"dataset": dataset, "data_id": code, "start_date": start, "end_date": end})
    for t in range(tries):
        try:
            out = subprocess.run(["curl", "-s", "-m", "30", f"{FINMIND}?{q}"], capture_output=True, text=True, timeout=40)
            d = json.loads(out.stdout)
            if d.get("status") == 200: return d.get("data", [])
            if d.get("status") == 402: time.sleep(3.0*(t+1)); continue
        except Exception: pass
        time.sleep(1.5)
    return None

def per_history(code):
    rows = fm("TaiwanStockPER", code, f"{WIN_START}-01-01", f"{WIN_END}-12-31")
    if not rows: return {}
    byd = {}
    for r in rows:
        y = int(r["date"][:4])
        if y not in byd or r["date"] > byd[y][0]: byd[y] = (r["date"], r.get("PER"), r.get("PBR"))
    out = {}
    for y, (_, per, pbr) in byd.items():
        try: per = float(per)
        except (TypeError, ValueError): per = None
        try: pbr = float(pbr)
        except (TypeError, ValueError): pbr = None
        rec = {}
        if per and per > 0: rec["per"] = round(per, 2)
        if pbr and pbr > 0: rec["pbr"] = round(pbr, 2)
        if per and per > 0 and pbr and pbr > 0: rec["roe"] = round(pbr/per*100, 1)
        elif pbr and pbr > 0: rec["roe"] = 0.0
        if rec: out[str(y)] = rec
    return out

def acc_roe(code):
    """會計ROE：年度淨利(逐季加總)/年末權益(母公司優先,否則總權益)"""
    fs = fm("TaiwanStockFinancialStatements", code, f"{WIN_START}-01-01", f"{WIN_END}-12-31")
    bs = fm("TaiwanStockBalanceSheet", code, f"{WIN_START}-01-01", f"{WIN_END}-12-31")
    if not fs or not bs: return {}
    ni = {}
    for r in fs:
        if r.get("type") != "IncomeAfterTaxes": continue
        try: ni[int(r["date"][:4])] = ni.get(int(r["date"][:4]), 0.0) + float(r["value"])
        except (TypeError, ValueError): pass
    eqp, eqt = {}, {}
    for r in bs:
        t = r.get("type")
        if t not in ("EquityAttributableToOwnersOfParent", "Equity"): continue
        y = int(r["date"][:4])
        try: v = float(r["value"])
        except (TypeError, ValueError): continue
        tgt = eqp if t == "EquityAttributableToOwnersOfParent" else eqt
        if y not in tgt or r["date"] > tgt[y][0]: tgt[y] = (r["date"], v)
    roe = {}
    for y in range(WIN_START, WIN_END+1):
        e = eqp.get(y) or eqt.get(y)
        if y in ni and e and e[1]: roe[str(y)] = round(ni[y]/e[1]*100, 1)
    return roe

def main():
    pool_n = int(sys.argv[1]) if len(sys.argv) > 1 else 150
    rk = json.load(open(RANKING))["ranking"]
    cands = rk[:pool_n]
    scored, fail = [], 0
    for i, c in enumerate(cands):
        by = per_history(c["code"]); time.sleep(0.3)
        roes = [v["roe"] for v in by.values() if v.get("roe") is not None]
        if len(roes) < MIN_YEARS:
            if not by: fail += 1
            continue
        pos = [v for v in roes if v > 0]; gt15 = sum(1 for v in roes if v > 15)
        scored.append({"code": c["code"], "name": c.get("name", c["code"]), "mkt": c.get("mkt", "tse"),
                       "n": len(roes), "gt15": gt15, "ratio": round(gt15/len(roes), 3),
                       "avg": round(statistics.mean(pos), 1) if pos else 0,
                       "min": round(min(pos), 1) if pos else 0, "byYear": by})
        if (i+1) % 25 == 0: print(f"  候選 {i+1}/{len(cands)} 命中{len(scored)} 失敗{fail}", flush=True)
    scored.sort(key=lambda r: (-r["ratio"], -r["avg"]))
    top = scored[:NEED]
    for r in top:
        r["roeAcc"] = acc_roe(r["code"]); time.sleep(0.4)
    stocks = [{"rank": i, "disp": i, "code": r["code"], "name": r["name"], "mkt": r["mkt"],
               "cons": f'{r["gt15"]}/{r["n"]}', "avgRoe": r["avg"], "minRoe": r["min"],
               "roeAcc": r.get("roeAcc", {}), "byYear": r["byYear"]} for i, r in enumerate(top, 1)]
    json.dump({"generated_from": "FinMind 市場推算ROE 季重排(候選池前%d)" % pool_n, "count": len(stocks), "stocks": stocks},
              open(OUT, "w", encoding="utf-8"), ensure_ascii=False)
    print(f"\n✓ 季重排 → data50.json（{len(stocks)} 檔，候選{len(cands)} 命中{len(scored)} 失敗{fail}）")
    for s in stocks[:10]: print(f"   #{s['disp']:<3}{s['code']} {s['name'][:6]:<7}一致{s['cons']} 均{s['avgRoe']}")

if __name__ == "__main__":
    main()
