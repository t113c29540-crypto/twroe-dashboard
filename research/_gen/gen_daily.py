# -*- coding: utf-8 -*-
"""每日研究圖文產生器（GitHub Actions 雲端每日執行）。
資料：TWSE/TPEx 官方開放資料（免費）。ROE = 股價淨值比 / 本益比。
產出：research/YYYY-MM-DD.html（含內嵌 SVG 圖）、更新 research/index.html、_gen/state.json
本產出為數據彙整，非投資建議。
"""
import json, os, subprocess, statistics, glob, time, datetime, sys

PLABEL = {"daily":"每日","weekly":"每週","monthly":"每月","quarterly":"每季","yearly":"每年"}
PWINDOW = {"daily":1,"weekly":5,"monthly":20,"quarterly":60,"yearly":240}
FM_TOKEN = os.environ.get("FINMIND_TOKEN", "")   # 有 token 額度大;無則免費層

GEN = os.path.dirname(os.path.abspath(__file__))
RES = os.path.dirname(GEN)                      # research/
DATA = os.path.join(GEN, "data50.json")
STATE = os.path.join(GEN, "state.json")

CC = {"gold":"#C9A227","goldlt":"#E8C75A","up":"#E0403A","down":"#22A06B",
      "mut":"#8A97AC","line":"#26384f","tx":"#E8ECF3","card":"#172539","bg":"#0E1726","blue":"#5B9BD5"}

def curl(url, tries=3):
    for _ in range(tries):
        try:
            o = subprocess.run(["curl","-s","-m","45",url], capture_output=True, text=True, timeout=60)
            if o.stdout.strip(): return o.stdout
        except Exception: pass
    return ""

def num(x):
    try: return float(str(x).replace(",","").replace("--","").strip())
    except (ValueError, TypeError): return None

FINMIND = "https://api.finmindtrade.com/api/v4/data"

def fm(dataset, code, start, end, tries=4):
    """FinMind 取單檔資料（全球可達；GitHub 雲端用此，TWSE/TPEx 官網會擋雲端IP）"""
    url = f"{FINMIND}?dataset={dataset}&data_id={code}&start_date={start}&end_date={end}" + (f"&token={FM_TOKEN}" if FM_TOKEN else "")
    for t in range(tries):
        txt = curl(url, tries=1)
        try:
            d = json.loads(txt)
            if d.get("status") == 200: return d.get("data", [])
            if d.get("status") == 402: time.sleep(3.0*(t+1)); continue   # 限流→退避
        except Exception: pass
        time.sleep(1.5)
    return []

def fetch_market(codes):
    """逐檔抓最新本益比/股價淨值比(TaiwanStockPER)與收盤(TaiwanStockPrice)。
    回傳 {code:{price,per,pbr,yield}} 與 交易日。"""
    today = datetime.date.today()
    start = (today - datetime.timedelta(days=90)).isoformat()
    end = today.isoformat()
    out, tdate = {}, ""
    for c in codes:
        per_rows = fm("TaiwanStockPER", c, start, end)
        price_rows = fm("TaiwanStockPrice", c, start, end)
        rec = {}
        if per_rows:
            last = per_rows[-1]
            rec["per"] = num(last.get("PER")); rec["pbr"] = num(last.get("PBR"))
            rec["yield"] = num(last.get("dividend_yield"))
            if last.get("date") and last["date"] > tdate: tdate = last["date"]
        if price_rows:
            pr = [r for r in price_rows if num(r.get("close"))]
            if pr:
                rec["price"] = num(pr[-1].get("close"))
                if pr[-1].get("date") and pr[-1]["date"] > tdate: tdate = pr[-1]["date"]
        out[c] = rec
        time.sleep(0.25)
    return out, tdate

def pctile(a, p):
    a = sorted(v for v in a if v is not None and v>0)
    if not a: return None
    k = (len(a)-1)*p; lo=int(k); hi=min(lo+1,len(a)-1)
    return a[lo] + (a[hi]-a[lo])*(k-lo)

def valuation(stk, price, per, pbr):
    hp = [r.get("per") for r in stk["byYear"].values()]
    hb = [r.get("pbr") for r in stk["byYear"].values()]
    eps = price/per if (per and per>0) else None
    bvps = price/pbr if (pbr and pbr>0) else None
    chs, frs = [], []
    if eps:
        c=pctile(hp,0.2); f=pctile(hp,0.5)
        if c: chs.append(eps*c)
        if f: frs.append(eps*f)
    if bvps:
        c=pctile(hb,0.2); f=pctile(hb,0.5)
        if c: chs.append(bvps*c)
        if f: frs.append(bvps*f)
    cheap = round(statistics.mean(chs),1) if chs else None
    fair  = round(statistics.mean(frs),1) if frs else None
    roe = round(pbr/per*100,1) if (per and per>0 and pbr and pbr>0) else None
    return cheap, fair, roe

# ---------- SVG 圖 ----------
def svg_wrap(w,h,inner): return f'<svg viewBox="0 0 {w} {h}" style="width:100%;height:auto;display:block;max-width:760px;margin:0 auto" xmlns="http://www.w3.org/2000/svg">{inner}</svg>'

def chart_valuation(rows):
    """估值位階分布：每檔一點，x=現價相對(便宜0→合理0.5→偏貴1)，y=分組抖動"""
    W,H,P=760,260,{"t":24,"r":16,"b":34,"l":16}
    pts=[]
    for r in rows:
        if r["cheap"] is None or r["fair"] is None or not r["price"]: continue
        c,f,pr=r["cheap"],r["fair"],r["price"]; hi=f*1.25
        if pr<=c: x=(pr/c)*0.34 if c else 0
        elif pr<=f: x=0.34+((pr-c)/(f-c))*0.33 if f>c else 0.5
        else: x=0.67+min(1,(pr-f)/(hi-f))*0.33 if hi>f else 1
        pts.append((max(0,min(1,x)), r))
    if not pts: return ""
    iw=W-P["l"]-P["r"]
    bands=f'<rect x="{P["l"]}" y="{P["t"]}" width="{iw*0.34}" height="{H-P["t"]-P["b"]}" fill="{CC["down"]}" opacity="0.10"/>'
    bands+=f'<rect x="{P["l"]+iw*0.34}" y="{P["t"]}" width="{iw*0.33}" height="{H-P["t"]-P["b"]}" fill="{CC["gold"]}" opacity="0.10"/>'
    bands+=f'<rect x="{P["l"]+iw*0.67}" y="{P["t"]}" width="{iw*0.33}" height="{H-P["t"]-P["b"]}" fill="{CC["up"]}" opacity="0.10"/>'
    labs=f'<text x="{P["l"]+iw*0.17}" y="{H-12}" text-anchor="middle" font-size="12" fill="{CC["down"]}">估值偏低</text>'
    labs+=f'<text x="{P["l"]+iw*0.505}" y="{H-12}" text-anchor="middle" font-size="12" fill="{CC["goldlt"]}">估值合理</text>'
    labs+=f'<text x="{P["l"]+iw*0.835}" y="{H-12}" text-anchor="middle" font-size="12" fill="{CC["up"]}">估值偏高</text>'
    dots=""
    rng=H-P["t"]-P["b"]-16
    for i,(x,r) in enumerate(sorted(pts,key=lambda t:t[0])):
        px=P["l"]+x*iw; py=P["t"]+8+(i%9)*(rng/9)
        col=CC["down"] if x<0.34 else (CC["gold"] if x<0.67 else CC["up"])
        dots+=f'<circle cx="{px:.1f}" cy="{py:.1f}" r="3.4" fill="{col}"/><text x="{px+5:.1f}" y="{py+3:.1f}" font-size="8.5" fill="{CC["mut"]}">{r["name"]}</text>'
    return svg_wrap(W,H,bands+labs+dots)

def chart_roe_bar(rows, n=15):
    top=sorted(rows,key=lambda r:-(r["avgRoe"] or 0))[:n]
    W,H,P=760,250,{"t":18,"r":12,"b":46,"l":30}
    mx=max((r["avgRoe"] or 0) for r in top) if top else 0
    if mx<=0: return ""   # 防呆:全為0/None 時不畫(避免除以零)
    iw=W-P["l"]-P["r"]; bw=iw/len(top)*0.66
    g=""
    for k in range(0,int(mx)+10,10):
        if k>mx+5: break
        y=H-P["b"]-(k/mx)*(H-P["t"]-P["b"])
        g+=f'<line x1="{P["l"]}" y1="{y:.1f}" x2="{W-P["r"]}" y2="{y:.1f}" stroke="{CC["line"]}" stroke-width="0.6"/><text x="{P["l"]-4}" y="{y+3:.1f}" text-anchor="end" font-size="9" fill="{CC["mut"]}">{k}</text>'
    for i,r in enumerate(top):
        x=P["l"]+iw*(i+0.5)/len(top); h=(r["avgRoe"]/mx)*(H-P["t"]-P["b"])
        y=H-P["b"]-h
        g+=f'<rect x="{x-bw/2:.1f}" y="{y:.1f}" width="{bw:.1f}" height="{h:.1f}" rx="2" fill="{CC["gold"]}"/>'
        g+=f'<text x="{x:.1f}" y="{y-3:.1f}" text-anchor="middle" font-size="8.5" fill="{CC["goldlt"]}">{r["avgRoe"]:.0f}</text>'
        g+=f'<text x="{x:.1f}" y="{H-P["b"]+12:.1f}" text-anchor="middle" font-size="8.5" fill="{CC["tx"]}">{r["name"]}</text>'
        g+=f'<text x="{x:.1f}" y="{H-P["b"]+24:.1f}" text-anchor="middle" font-size="7.5" fill="{CC["mut"]}">{r["code"]}</text>'
    return svg_wrap(W,H,g)

def chart_roe_trend(stk):
    yrs=sorted(int(y) for y in stk["byYear"])
    vals=[stk["byYear"][str(y)].get("roe") for y in yrs]
    pairs=[(y,v) for y,v in zip(yrs,vals) if v is not None]
    if len(pairs)<5: return ""
    W,H,P=760,210,{"t":16,"r":14,"b":26,"l":28}
    mx=max(40,max(v for _,v in pairs)); n=len(pairs); iw=W-P["l"]-P["r"]
    g=""
    for k in (0,15,30,45):
        if k>mx: continue
        y=H-P["b"]-(k/mx)*(H-P["t"]-P["b"])
        col=CC["up"] if k==15 else CC["line"]
        g+=f'<line x1="{P["l"]}" y1="{y:.1f}" x2="{W-P["r"]}" y2="{y:.1f}" stroke="{col}" stroke-width="{0.9 if k==15 else 0.6}" {"stroke-dasharray=\"4 3\"" if k==15 else ""}/><text x="{P["l"]-4}" y="{y+3:.1f}" text-anchor="end" font-size="9" fill="{CC["mut"]}">{k}</text>'
    bw=iw/n*0.5
    for i,(yr,v) in enumerate(pairs):
        x=P["l"]+iw*(i+0.5)/n; h=(v/mx)*(H-P["t"]-P["b"]); y=H-P["b"]-h
        col=CC["gold"] if v>15 else CC["up"]
        g+=f'<rect x="{x-bw/2:.1f}" y="{y:.1f}" width="{bw:.1f}" height="{h:.1f}" rx="1.5" fill="{col}" opacity="0.9"/>'
        if i%2==0 or i==n-1: g+=f'<text x="{x:.1f}" y="{H-P["b"]+12:.1f}" text-anchor="middle" font-size="8" fill="{CC["mut"]}">{str(yr)[2:]}</text>'
    return svg_wrap(W,H,g)

# ---------- 文章 ----------
def esc(s): return str(s).replace("&","&amp;").replace("<","&lt;")

def build_article(date, rows, changes, featured, recon=None, period="daily"):
    plabel=PLABEL.get(period,"每日"); recon=recon or []
    buys=[r for r in rows if r["sig"]=="buy"]
    fairs=[r for r in rows if r["sig"]=="fair"]
    def sigtag(s): return {"buy":('🟢 估值偏低',CC["down"]),"fair":('🟡 估值合理',CC["goldlt"]),"exp":('🔴 估值偏高',CC["up"]),"na":('—',CC["mut"])}[s]
    head=f"""<!DOCTYPE html><html lang="zh-Hant"><head><meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>台股高ROE長青股 · {plabel}研究 {date}</title>
<style>body{{margin:0;background:{CC['bg']};color:{CC['tx']};font-family:-apple-system,"PingFang TC","Microsoft JhengHei",sans-serif;line-height:1.7;font-size:15px}}
.wrap{{max-width:820px;margin:0 auto;padding:20px 16px 60px}}
h1{{font-size:22px;color:{CC['gold']};margin:6px 0 2px}} h2{{font-size:16px;color:{CC['goldlt']};border-left:3px solid {CC['gold']};padding-left:9px;margin:26px 0 10px}}
.sub{{color:{CC['mut']};font-size:13px;margin-bottom:8px}}
.card{{background:{CC['card']};border:1px solid {CC['line']};border-radius:12px;padding:12px 14px;margin:8px 0}}
table{{width:100%;border-collapse:collapse;font-size:12.5px}} th,td{{padding:5px 6px;border-bottom:1px solid {CC['line']};text-align:right;white-space:nowrap}}
th{{color:{CC['mut']};font-weight:600}} td.l,th.l{{text-align:left}}
.pill{{display:inline-block;padding:2px 8px;border-radius:7px;font-size:11px;font-weight:700}}
.note{{color:{CC['mut']};font-size:11px}} a{{color:{CC['goldlt']}}}
.foot{{color:{CC['mut']};font-size:11px;border-top:1px solid {CC['line']};margin-top:24px;padding-top:12px;line-height:1.6}}
.kpi{{display:flex;gap:10px;flex-wrap:wrap;margin:8px 0}} .kpi div{{background:{CC['card']};border:1px solid {CC['line']};border-radius:10px;padding:8px 14px;font-size:13px}} .kpi b{{font-size:18px;color:{CC['goldlt']};display:block}}
</style></head><body><div class="wrap">
<p class="sub"><a href="index.html">← 研究索引</a> ｜ <a href="../index.html">回行動看板</a></p>
<h1>台股高 ROE 長青股 · {plabel}研究</h1>
<p class="sub">交易日 {date}　｜　資料：TWSE／TPEx 官方開放資料（ROE＝股價淨值比 ÷ 本益比）　｜　本文為數據彙整，非投資建議</p>
<div class="kpi"><div>追蹤長青股<b>{len(rows)} 檔</b></div><div>🟢估值偏低<b>{len(buys)} 檔</b></div><div>🟡估值合理<b>{len(fairs)} 檔</b></div>{f'<div>⚠️對帳待查<b>{len(recon)} 檔</b></div>' if recon else ''}</div>
"""
    # 估值偏低觀察名單
    s=['<h2>① 估值偏低觀察名單（現價 ≤ 歷史便宜價）</h2>']
    if buys:
        s.append('<div class="card"><table><tr><th class="l">名次</th><th class="l">股票</th><th>現價</th><th>便宜價</th><th>距便宜價</th><th>均ROE</th><th>達標</th></tr>')
        for r in sorted(buys,key=lambda r:r["disp"]):
            dp=(r["price"]-r["cheap"])/r["cheap"]*100
            s.append(f'<tr><td class="l">#{r["disp"]}</td><td class="l">{esc(r["name"])} <span class="note">{r["code"]}</span></td><td>{r["price"]:.1f}</td><td>{r["cheap"]:.1f}</td><td style="color:{CC["down"]}">{dp:+.1f}%</td><td>{r["avgRoe"]:.1f}%</td><td>{r["cons"]}</td></tr>')
        s.append('</table></div>')
    else:
        s.append(f'<div class="card" style="color:{CC["mut"]}">今日無長青股現價低於其歷史便宜價（估值偏低）。</div>')
    s.append(f'<p class="note">估值法：以各股歷史本益比／股價淨值比 20 百分位推算「便宜價」、50 百分位推算「合理價」（近16年）。<b>此為統計位階，非進出場指示；「便宜」不代表值得買，若基本面轉壞可能是價值陷阱。</b></p>')
    s.append('<h2>② 今日估值位階分布（前50長青股）</h2><div class="card">'+chart_valuation(rows)+'</div>')
    # 異動
    s.append('<h2>③ 前50排行與今日異動</h2>')
    if changes:
        s.append('<div class="card">'+changes+'</div>')
    s.append('<div class="card"><table><tr><th class="l">名次</th><th class="l">股票</th><th>市場</th><th>達標</th><th>均ROE</th><th>現價</th><th>估值位階</th></tr>')
    for r in sorted(rows,key=lambda r:r["disp"]):
        tg,cl=sigtag(r["sig"]); pr=f'{r["price"]:.1f}' if r["price"] else '—'
        s.append(f'<tr><td class="l">#{r["disp"]}</td><td class="l">{esc(r["name"])} <span class="note">{r["code"]}</span></td><td>{"上市" if r["mkt"]=="tse" else "上櫃"}</td><td>{r["cons"]}</td><td>{r["avgRoe"]:.1f}%</td><td>{pr}</td><td style="color:{cl}">{tg}</td></tr>')
    s.append('</table></div>')
    # ROE 圖
    s.append('<h2>④ 近16年平均 ROE（前15名）</h2><div class="card">'+chart_roe_bar(rows)+'</div>')
    if featured:
        s.append(f'<h2>⑤ ROE 趨勢快照：{esc(featured["name"])}（{featured["code"]}）</h2>')
        s.append(f'<div class="card">{chart_roe_trend(featured)}<p class="note">金柱＝市場推算ROE（股價淨值比÷本益比，紅＝低於15%門檻）。一致性 {featured["cons"]}、平均 {featured["avgRoe"]:.1f}%。</p></div>')
    # 對帳(市場推算ROE vs 會計ROE)
    s.append('<h2>⑥ 資料對帳（市場推算 ROE × 會計 ROE）</h2>')
    if recon:
        s.append(f'<div class="card"><p class="note">以下 {len(recon)} 檔，兩種獨立算法的 ROE 差異 &gt;35%，數字僅供參考、<b>待查</b>（常見於高股價淨值比股、財報時點差異，多為時點差非錯誤）。</p><table><tr><th class="l">股票</th><th>市場推算ROE</th><th>會計ROE</th><th>差異</th></tr>')
        for x in recon[:15]:
            s.append(f'<tr><td class="l">{esc(x["name"])} <span class="note">{x["code"]}</span></td><td>{x["mkt"]}%</td><td>{x["acc"]}%</td><td style="color:{CC["up"]}">{x["diff"]}%</td></tr>')
        s.append('</table></div>')
    else:
        s.append(f'<div class="card" style="color:{CC["down"]}">✓ 前50檔市場推算 ROE 與會計 ROE 大致一致（差異皆 ≤35%）。</div>')
    s.append(f'<p class="note">對帳方法：市場推算 ROE＝股價淨值比÷本益比；會計 ROE＝年度稅後淨利÷年末股東權益（皆取自 FinMind 不同資料集，獨立計算）。</p>')
    # 方法
    s.append(f"""<h2>⑦ 研究方法</h2><div class="card" style="font-size:13px;line-height:1.8">
<b>選股：</b>近16年（2010–2025）ROE 年年＞15% 的長青股，以「達標一致性」排序、均ROE 次之。<br>
<b>ROE：</b>＝股價淨值比 ÷ 本益比（＝每股盈餘／每股淨值），資料取自 TWSE／TPEx 官方每年年底全市場本益比與股價淨值比；某年無本益比＝該年虧損／無盈餘，計為未達標（修正景氣循環股偏誤）。<br>
<b>估值：</b>三法（本益比／股價淨值比）歷史百分位推算便宜價（20%）與合理價（50%）。<br>
<b>估值口徑（非進出場指示）：</b>便宜價／合理價為統計位階；此類股的「便宜」前提是 ROE 持續＞15%，ROE 跌破門檻時所謂便宜可能是<b>價值陷阱</b>。個股最大回撤可達 55–88%，須注意集中度。本研究僅供教育，不構成任何買賣建議。</div>""")
    foot=f"""<div class="foot">本文由程式自動彙整 TWSE／TPEx 官方公開資料生成（ROE＝股價淨值比÷本益比），<b>僅供研究與教育，非投資建議，盈虧自負</b>。估值為歷史統計推算、非保證。資料可能因官方更新或停牌而有缺漏。<br>產生時間（交易日）：{date}　｜　專案：台股高ROE長青股看板</div></div></body></html>"""
    return head+"\n".join(s)+foot

def rebuild_index():
    files=sorted([os.path.basename(f) for f in glob.glob(os.path.join(RES,"2*.html"))], reverse=True)
    items="".join(f'<li><a href="{f}">{f[:-5]}</a> · 每日研究</li>' for f in files)
    html=f"""<!DOCTYPE html><html lang="zh-Hant"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>台股高ROE長青股 · 研究索引</title><style>body{{margin:0;background:{CC['bg']};color:{CC['tx']};font-family:-apple-system,"PingFang TC",sans-serif;line-height:1.8}}
.wrap{{max-width:760px;margin:0 auto;padding:24px 16px 60px}} h1{{color:{CC['gold']};font-size:22px}} a{{color:{CC['goldlt']};text-decoration:none}}
ul{{list-style:none;padding:0}} li{{background:{CC['card']};border:1px solid {CC['line']};border-radius:10px;padding:11px 14px;margin:7px 0}}
.note{{color:{CC['mut']};font-size:12px}}</style></head><body><div class="wrap">
<p class="note"><a href="../index.html">← 回行動看板</a></p><h1>📑 台股高ROE長青股 · 每日研究</h1>
<p class="note">每日由 GitHub Actions 自動產生（TWSE／TPEx 官方資料，ROE＝股價淨值比÷本益比）。非投資建議。</p>
<ul>{items or '<li class="note">尚無文章</li>'}</ul></div></body></html>"""
    open(os.path.join(RES,"index.html"),"w",encoding="utf-8").write(html)

def main():
    PERIOD = sys.argv[1] if len(sys.argv)>1 and sys.argv[1] in PLABEL else "daily"
    WINDOW = PWINDOW[PERIOD]; plabel = PLABEL[PERIOD]
    data=json.load(open(DATA)); stocks=data["stocks"]
    market, date = fetch_market([s["code"] for s in stocks])
    date = date or datetime.date.today().isoformat()
    rows=[]
    for s in stocks:
        c=s["code"]; m=market.get(c,{}); price=m.get("price"); per=m.get("per"); pbr=m.get("pbr")
        cheap,fair,roe=valuation(s,price,per,pbr) if price else (None,None,None)
        sig="na"
        if price and cheap and fair:
            sig = "buy" if price<=cheap else ("fair" if price<=fair else "exp")
        rows.append({**s,"price":price,"per":per,"pbr":pbr,"cheap":cheap,"fair":fair,"roeNow":roe,"sig":sig})
    # 資料品質關卡：抓不到足夠資料就不發佈（寧缺勿錯）
    MIN_OK = 40
    hits = sum(1 for r in rows if r["price"])
    valued = sum(1 for r in rows if r["cheap"] is not None)
    if hits < MIN_OK or valued < MIN_OK:
        print(f"✗ 資料品質不足：現價命中 {hits}/{len(rows)}、可估值 {valued}/{len(rows)}（門檻 {MIN_OK}）。今日不發佈、不提交。")
        raise SystemExit(1)
    # === 優化：valuations.json 供看板直接讀(免即時代理) ===
    val={r["code"]:{"cheap":r["cheap"],"fair":r["fair"],"roe":r["roeNow"],"per":r["per"],"pbr":r["pbr"],
                    "price":r["price"],"sig":r["sig"],"cons":r.get("cons"),"aroe":r.get("avgRoe")}
         for r in rows if r["cheap"] is not None}
    json.dump({"date":date,"v":val}, open(os.path.join(GEN,"valuations.json"),"w",encoding="utf-8"), ensure_ascii=False)
    # === 對帳：市場推算ROE(PBR/PER) vs 會計ROE(財報),差異>35% 示警 ===
    recon=[]
    for r in rows:
        acc=r.get("roeAcc") or {}; ay=sorted(acc.keys()); av=acc[ay[-1]] if ay else None
        if av and av>0 and r.get("roeNow"):
            df=abs(r["roeNow"]-av)/av
            if df>0.35: recon.append({"code":r["code"],"name":r["name"],"mkt":round(r["roeNow"],1),"acc":round(av,1),"diff":round(df*100)})
    recon.sort(key=lambda x:-x["diff"])
    # === 歷史快照(週/月/季報變化比較用) ===
    HIST=os.path.join(GEN,"history.json"); hist=[]
    if os.path.exists(HIST):
        try: hist=json.load(open(HIST))
        except Exception: hist=[]
    hist=[h for h in hist if h.get("date")!=date]
    hist.append({"date":date,"prices":{r["code"]:r["price"] for r in rows if r["price"]},
                 "sigs":{r["code"]:r["sig"] for r in rows}})
    hist=sorted(hist,key=lambda h:h["date"])[-220:]
    json.dump(hist, open(HIST,"w",encoding="utf-8"), ensure_ascii=False)
    # === 變化比較：日報比前次;週/月/季報比 N 個交易日前(取自 history) ===
    base=None
    if PERIOD=="daily" and os.path.exists(STATE):
        try: base=json.load(open(STATE))
        except Exception: base=None
    elif PERIOD!="daily":
        i=len(hist)-1-WINDOW
        if i>=0: base={"prices":hist[i]["prices"],"signals":hist[i]["sigs"],"date":hist[i]["date"]}
    win_lbl={"daily":"前一交易日","weekly":"約一週前","monthly":"約一個月前","quarterly":"約一季前"}.get(PERIOD,"前次")
    nmmap={r["code"]:r["name"] for r in rows}
    changes=[]
    if base:
        bsig=base.get("signals",{})
        nb=[r for r in rows if r["sig"]=="buy" and bsig.get(r["code"])!="buy"]
        lb=[c for c,sg in bsig.items() if sg=="buy" and next((r for r in rows if r["code"]==c and r["sig"]=="buy"),None) is None]
        if nb: changes.append('🟢 新增估值偏低：'+("、".join(f'{r["name"]}({r["code"]})' for r in nb)))
        if lb: changes.append('⬆️ 脫離估值偏低區：'+("、".join(f'{nmmap.get(c,c)}({c})' for c in lb)))
        mv=[]
        for r in rows:
            pp=base.get("prices",{}).get(r["code"])
            if pp and r["price"]: mv.append((((r["price"]-pp)/pp*100), r))
        mv.sort(key=lambda t:-abs(t[0]))
        if mv[:5]: changes.append('📊 波動較大：'+("、".join(f'{r["name"]} {d:+.1f}%' for d,r in mv[:5])))
    chg_html=(f"（對比 {base.get('date','—')}，{win_lbl}）<br>"+"<br>".join(changes)) if (base and changes) else ("（首次發佈，建立基準）" if not base else f"與{win_lbl}相比無顯著變化。")
    featured=next((r for r in sorted(rows,key=lambda r:r["disp"]) if r["sig"]=="buy"), None) or next((r for r in rows if r["disp"]==1), rows[0])
    html=build_article(date, rows, chg_html, featured, recon, PERIOD)
    suffix="" if PERIOD=="daily" else f"-{PERIOD}"; stub=f"{date}{suffix}"
    out=os.path.join(RES, f"{stub}.html")
    open(out,"w",encoding="utf-8").write(html)
    rebuild_index()
    if PERIOD=="daily":
        json.dump({"date":date,"prices":{r["code"]:r["price"] for r in rows if r["price"]},
                   "signals":{r["code"]:r["sig"] for r in rows}}, open(STATE,"w",encoding="utf-8"), ensure_ascii=False)
    # 審核用：PR 摘要與日期（寫到 repo 根，不進 git；供 workflow 開草稿 PR）
    REPO_ROOT = os.path.dirname(RES)
    buys_sorted = sorted([r for r in rows if r["sig"]=="buy"], key=lambda r:r["disp"])
    nlow = sum(1 for r in rows if r["sig"]=="buy"); nfair = sum(1 for r in rows if r["sig"]=="fair")
    lines = [f"- #{r['disp']} {r['name']}({r['code']})　現價 {r['price']} / 便宜價 {r['cheap']}（{(r['price']-r['cheap'])/r['cheap']*100:+.1f}%）" for r in buys_sorted]
    nrecon=len(recon)
    body = (f"## {plabel}研究草稿 · {date}\n\n"
            f"**追蹤 {len(rows)} 檔　｜　🟢 估值偏低 {nlow} 檔　｜　🟡 估值合理 {nfair} 檔"
            + (f"　｜　⚠️ 對帳待查 {nrecon} 檔" if nrecon else "") + "**\n\n"
            f"### 🟢 估值偏低觀察名單（現價 ≤ 歷史便宜價）\n"
            + ("\n".join(lines) if lines else "（今日無）") + "\n\n"
            "> ⚠️ 估值位階為歷史統計推算、**非投資建議**；「便宜」不代表值得買，基本面轉壞時可能是價值陷阱。\n\n"
            "---\n**審核方式**：看過上方摘要與預覽後 —— 滿意按 **Merge** 即公開發佈；不要按 **Close**（不會公開）。\n")
    open(os.path.join(REPO_ROOT, "pr_body.md"), "w", encoding="utf-8").write(body)
    open(os.path.join(REPO_ROOT, "pr_date.txt"), "w", encoding="utf-8").write(stub)
    print(f"✓ 產生 {out}（{plabel}｜估值偏低{nlow}檔｜對帳待查{nrecon}檔｜價格命中{sum(1 for r in rows if r['price'])}/{len(rows)}）")

if __name__=="__main__":
    main()
