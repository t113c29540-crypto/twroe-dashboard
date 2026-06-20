# -*- coding: utf-8 -*-
"""每日研究圖文產生器（GitHub Actions 雲端每日執行）。
資料：TWSE/TPEx 官方開放資料（免費）。ROE = 股價淨值比 / 本益比。
產出：research/YYYY-MM-DD.html（含內嵌 SVG 圖）、更新 research/index.html、_gen/state.json
本產出為數據彙整，非投資建議。
"""
import json, os, subprocess, statistics, glob

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

def fetch_prices():
    p = {}
    try:
        for r in json.loads(curl("https://openapi.twse.com.tw/v1/exchangeReport/STOCK_DAY_ALL")):
            c=str(r.get("Code","")).strip(); v=num(r.get("ClosingPrice"))
            if v: p[c]=v
    except Exception: pass
    try:
        for r in json.loads(curl("https://www.tpex.org.tw/openapi/v1/tpex_mainboard_daily_close_quotes")):
            c=str(r.get("SecuritiesCompanyCode","")).strip(); v=num(r.get("Close"))
            if v: p[c]=v
    except Exception: pass
    return p

def fetch_pepbr():
    m = {}
    try:
        for r in json.loads(curl("https://openapi.twse.com.tw/v1/exchangeReport/BWIBBU_ALL")):
            m[str(r.get("Code","")).strip()] = (num(r.get("PEratio")), num(r.get("PBratio")))
    except Exception: pass
    try:
        for r in json.loads(curl("https://www.tpex.org.tw/openapi/v1/tpex_mainboard_peratio_analysis")):
            m[str(r.get("SecuritiesCompanyCode","")).strip()] = (num(r.get("PriceEarningRatio")), num(r.get("PriceBookRatio")))
    except Exception: pass
    return m

def trade_date():
    """由 STOCK_DAY_ALL 的 Date(民國) 取得交易日 → YYYY-MM-DD"""
    try:
        d = json.loads(curl("https://openapi.twse.com.tw/v1/exchangeReport/STOCK_DAY_ALL"))
        roc = str(d[0]["Date"])
        return f"{int(roc[:3])+1911:04d}-{roc[3:5]}-{roc[5:7]}"
    except Exception:
        return ""

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
    labs=f'<text x="{P["l"]+iw*0.17}" y="{H-12}" text-anchor="middle" font-size="12" fill="{CC["down"]}">便宜·可分批</text>'
    labs+=f'<text x="{P["l"]+iw*0.505}" y="{H-12}" text-anchor="middle" font-size="12" fill="{CC["goldlt"]}">合理區間</text>'
    labs+=f'<text x="{P["l"]+iw*0.835}" y="{H-12}" text-anchor="middle" font-size="12" fill="{CC["up"]}">偏貴·等回檔</text>'
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
    mx=max(r["avgRoe"] for r in top); iw=W-P["l"]-P["r"]; bw=iw/len(top)*0.66
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

def build_article(date, rows, changes, featured):
    buys=[r for r in rows if r["sig"]=="buy"]
    fairs=[r for r in rows if r["sig"]=="fair"]
    def sigtag(s): return {"buy":('🟢 便宜',CC["down"]),"fair":('🟡 合理',CC["goldlt"]),"exp":('🔴 偏貴',CC["up"]),"na":('—',CC["mut"])}[s]
    head=f"""<!DOCTYPE html><html lang="zh-Hant"><head><meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>台股高ROE長青股 · 每日研究 {date}</title>
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
<h1>台股高 ROE 長青股 · 每日研究</h1>
<p class="sub">交易日 {date}　｜　資料：TWSE／TPEx 官方開放資料（ROE＝股價淨值比 ÷ 本益比）　｜　本文為數據彙整，非投資建議</p>
<div class="kpi"><div>追蹤長青股<b>{len(rows)} 檔</b></div><div>今日🟢便宜<b>{len(buys)} 檔</b></div><div>🟡合理<b>{len(fairs)} 檔</b></div></div>
"""
    # 當日買訊
    s=['<h2>① 當日買訊與估值</h2>']
    if buys:
        s.append('<div class="card"><table><tr><th class="l">名次</th><th class="l">股票</th><th>現價</th><th>便宜價</th><th>距便宜價</th><th>均ROE</th><th>達標</th></tr>')
        for r in sorted(buys,key=lambda r:r["disp"]):
            dp=(r["price"]-r["cheap"])/r["cheap"]*100
            s.append(f'<tr><td class="l">#{r["disp"]}</td><td class="l">{esc(r["name"])} <span class="note">{r["code"]}</span></td><td>{r["price"]:.1f}</td><td>{r["cheap"]:.1f}</td><td style="color:{CC["down"]}">{dp:+.1f}%</td><td>{r["avgRoe"]:.1f}%</td><td>{r["cons"]}</td></tr>')
        s.append('</table></div>')
    else:
        s.append(f'<div class="card" style="color:{CC["mut"]}">今日無長青股跌破便宜價。可續觀察🟡合理區間者，或等待回檔。</div>')
    s.append(f'<p class="note">估值法：以各股歷史本益比／股價淨值比 20 百分位推算「便宜價」、50 百分位推算「合理價」（近16年）。</p>')
    s.append('<h2>② 今日估值位階分布（前50長青股）</h2><div class="card">'+chart_valuation(rows)+'</div>')
    # 異動
    s.append('<h2>③ 前50排行與今日異動</h2>')
    if changes:
        s.append('<div class="card">'+changes+'</div>')
    s.append('<div class="card"><table><tr><th class="l">名次</th><th class="l">股票</th><th>市場</th><th>達標</th><th>均ROE</th><th>現價</th><th>訊號</th></tr>')
    for r in sorted(rows,key=lambda r:r["disp"]):
        tg,cl=sigtag(r["sig"]); pr=f'{r["price"]:.1f}' if r["price"] else '—'
        s.append(f'<tr><td class="l">#{r["disp"]}</td><td class="l">{esc(r["name"])} <span class="note">{r["code"]}</span></td><td>{"上市" if r["mkt"]=="tse" else "上櫃"}</td><td>{r["cons"]}</td><td>{r["avgRoe"]:.1f}%</td><td>{pr}</td><td style="color:{cl}">{tg}</td></tr>')
    s.append('</table></div>')
    # ROE 圖
    s.append('<h2>④ 近16年平均 ROE（前15名）</h2><div class="card">'+chart_roe_bar(rows)+'</div>')
    if featured:
        s.append(f'<h2>⑤ ROE 趨勢快照：{esc(featured["name"])}（{featured["code"]}）</h2>')
        s.append(f'<div class="card">{chart_roe_trend(featured)}<p class="note">金柱＝會計ROE推算（紅＝低於15%門檻）。一致性 {featured["cons"]}、近16年均 {featured["avgRoe"]:.1f}%。</p></div>')
    # 方法
    s.append(f"""<h2>⑥ 研究方法</h2><div class="card" style="font-size:13px;line-height:1.8">
<b>選股：</b>近16年（2010–2025）ROE 年年＞15% 的長青股，以「達標一致性」排序、均ROE 次之。<br>
<b>ROE：</b>＝股價淨值比 ÷ 本益比（＝每股盈餘／每股淨值），資料取自 TWSE／TPEx 官方每年年底全市場本益比與股價淨值比；某年無本益比＝該年虧損／無盈餘，計為未達標（修正景氣循環股偏誤）。<br>
<b>估值：</b>三法（本益比／股價淨值比）歷史百分位推算便宜價（20%）與合理價（50%）。<br>
<b>進場紀律：</b>只在便宜價附近分批；停利於合理價×1.15；賣出多因基本面轉壞（ROE 跌破15%）而非短線套牢。個股最大回撤可達 55–88%，務必分散。</div>""")
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
    data=json.load(open(DATA)); stocks=data["stocks"]
    prices=fetch_prices(); pepbr=fetch_pepbr(); date=trade_date() or "latest"
    rows=[]
    for s in stocks:
        c=s["code"]; price=prices.get(c); per,pbr=pepbr.get(c,(None,None))
        cheap,fair,roe=valuation(s,price,per,pbr) if price else (None,None,None)
        sig="na"
        if price and cheap and fair:
            sig = "buy" if price<=cheap else ("fair" if price<=fair else "exp")
        rows.append({**s,"price":price,"per":per,"pbr":pbr,"cheap":cheap,"fair":fair,"roeNow":roe,"sig":sig})
    # 異動 vs 前次
    prev={}
    if os.path.exists(STATE):
        try: prev=json.load(open(STATE))
        except Exception: prev={}
    prev_sig=prev.get("signals",{}); changes=[]
    new_buy=[r for r in rows if r["sig"]=="buy" and prev_sig.get(r["code"])!="buy"]
    left_buy=[c for c,sg in prev_sig.items() if sg=="buy" and next((r for r in rows if r["code"]==c and r["sig"]=="buy"),None) is None]
    if prev:
        if new_buy: changes.append('🟢 新增買訊：'+("、".join(f'{r["name"]}({r["code"]})' for r in new_buy)))
        if left_buy: changes.append('⬆️ 脫離便宜價：'+("、".join(left_buy)))
        # 漲跌幅前3
        moves=[]
        for r in rows:
            pp=prev.get("prices",{}).get(r["code"])
            if pp and r["price"]: moves.append((((r["price"]-pp)/pp*100), r))
        moves.sort(key=lambda t:-abs(t[0]))
        if moves[:3]:
            changes.append('📊 波動較大：'+("、".join(f'{r["name"]} {d:+.1f}%' for d,r in moves[:3])))
    chg_html="<br>".join(changes) if changes else ("（首次發佈，建立基準）" if not prev else "今日無顯著異動。")
    featured=next((r for r in sorted(rows,key=lambda r:r["disp"]) if r["sig"]=="buy"), None) or next((r for r in rows if r["disp"]==1), rows[0])
    html=build_article(date, rows, chg_html, featured)
    out=os.path.join(RES, f"{date}.html")
    open(out,"w",encoding="utf-8").write(html)
    rebuild_index()
    json.dump({"date":date,"prices":{r["code"]:r["price"] for r in rows if r["price"]},
               "signals":{r["code"]:r["sig"] for r in rows}}, open(STATE,"w"), ensure_ascii=False)
    print(f"✓ 產生 {out}（買訊{sum(1 for r in rows if r['sig']=='buy')}檔，價格命中{sum(1 for r in rows if r['price'])}/{len(rows)}）")

if __name__=="__main__":
    main()
