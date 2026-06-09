# -*- coding: utf-8 -*-
"""台股高ROE — 雲端到價推播(GitHub Actions 版,免費7x24)。
讀 GitHub Secrets: LINE_TOKEN / LINE_USER_ID。--once 檢查一次即離開(供cron)。
跨次去重: alert_state.json(由 workflow commit 回 repo)。僅通知,不下單。"""
import os, sys, json, datetime, ssl, urllib.request, urllib.parse, urllib.error

TOKEN   = os.environ.get("LINE_TOKEN", "")
USER_ID = os.environ.get("LINE_USER_ID", "")
STATE   = "alert_state.json"

def _open(req, timeout=15):
    """正常驗證 SSL;若環境有 SSL 攔截代理(企業網路)則退回不驗證。"""
    try:
        return urllib.request.urlopen(req, timeout=timeout)
    except urllib.error.URLError as e:
        if "CERTIFICATE" in str(e) or isinstance(getattr(e, "reason", None), ssl.SSLError):
            return urllib.request.urlopen(req, timeout=timeout, context=ssl._create_unverified_context())
        raise

# 監看清單:代號 -> (名稱, 市場tse/otc, 便宜價)。可自行增刪。
WATCH = {
    "5904": ("寶雅","otc",386), "2707": ("晶華","tse",158), "2912": ("統一超","tse",262),
    "8083": ("瑞穎","otc",151), "3034": ("聯詠","tse",306), "9910": ("豐泰","tse",70),
    "5903": ("全家","otc",221), "1580": ("新麥","otc",132), "1476": ("儒鴻","tse",360),
    "2330": ("台積電","tse",762), "5274": ("信驊","otc",1424),
}

def http_get(url, headers=None, timeout=15):
    req = urllib.request.Request(url, headers=headers or {"User-Agent":"Mozilla/5.0"})
    with _open(req, timeout) as r:
        return r.read().decode("utf-8","ignore")

def get_prices():
    ex = "|".join(f"{m}_{c}.tw" for c,(_,m,_) in WATCH.items())
    url = f"https://mis.twse.com.tw/stock/api/getStockInfo.jsp?ex_ch={ex}&json=1&delay=0"
    try:
        data = json.loads(http_get(url, {"User-Agent":"Mozilla/5.0","Referer":"https://mis.twse.com.tw/"}))
        out = {}
        for m in data.get("msgArray", []):
            z = m.get("z"); y = m.get("y")
            px = float(z) if z not in (None,"-","") else (float(y) if y not in (None,"-","") else None)
            if px: out[m.get("c")] = px
        return out
    except Exception as e:
        print("price err:", e); return {}

def yahoo(code, mkt):
    return f"https://tw.stock.yahoo.com/quote/{code}.{'TWO' if mkt=='otc' else 'TW'}/news"

import re, html as _html
def get_news(name):
    """抓該股一則最新新聞(標題, 連結)。失敗回 (None, None)。"""
    try:
        q = urllib.parse.quote(name + " 股價")
        rss = f"https://news.google.com/rss/search?q={q}&hl=zh-TW&gl=TW&ceid=TW:zh-Hant"
        x = http_get(rss, timeout=12)
        m = re.search(r"<item>.*?<title>(.*?)</title>.*?<link>(.*?)</link>", x, re.S)
        if m:
            title = _html.unescape(re.sub(r"<[^>]+>", "", m.group(1))).strip()
            return title[:60], m.group(2).strip()
    except Exception as e:
        print("news err:", e)
    return None, None

def _line_post(path, payload):
    req = urllib.request.Request("https://api.line.me/v2/bot/message/" + path,
        data=json.dumps(payload).encode(), method="POST",
        headers={"Authorization": f"Bearer {TOKEN}", "Content-Type": "application/json"})
    with _open(req, 15) as r: return r.status

def push(text):
    """多人/群組:LINE_USER_ID 可填逗號分隔的多個 userId/groupId;填 broadcast 則廣播給所有好友。"""
    if not TOKEN:
        print("[未設定 LINE_TOKEN] 訊息:\n" + text); return
    msg = [{"type": "text", "text": text}]
    targets = [t.strip() for t in USER_ID.split(",") if t.strip()]
    if not targets:
        print("[未設定 LINE_USER_ID] 訊息:\n" + text); return
    if targets == ["broadcast"]:
        try: print("LINE broadcast", _line_post("broadcast", {"messages": msg}))
        except Exception as e: print("broadcast err:", e)
        return
    for t in targets:                    # 逐一推播(支援多位使用者與群組)
        try: print(f"LINE push {t[:6]}…", _line_post("push", {"to": t, "messages": msg}))
        except Exception as e: print("push err:", e)

# ===== Web Push(手機關App也能收;讀 subscriptions.json + VAPID 私鑰)=====
_WEB = {"init": False, "subs": [], "ready": False}
def _web_init():
    if _WEB["init"]: return
    _WEB["init"] = True
    try: _WEB["subs"] = json.load(open("subscriptions.json"))
    except Exception: _WEB["subs"] = []
    pem = os.environ.get("VAPID_PRIVATE", "")
    if pem and _WEB["subs"]:
        open("vapid_private.pem", "w").write(pem); _WEB["ready"] = True

def web_push(title, body, url):
    _web_init()
    if not _WEB["ready"]: return
    try:
        from pywebpush import webpush
    except ImportError:
        print("pywebpush 未安裝,略過 Web Push"); return
    payload = json.dumps({"title": title, "body": body, "url": url})
    claims = {"sub": os.environ.get("VAPID_SUBJECT", "mailto:alert@example.com")}
    for s in list(_WEB["subs"]):
        try:
            webpush(subscription_info=s, data=payload, vapid_private_key="vapid_private.pem", vapid_claims=claims)
            print("webpush ok")
        except Exception as e:
            print("webpush err:", str(e)[:90])

def load_state():
    try: return json.load(open(STATE))
    except: return {}
def save_state(s):
    json.dump(s, open(STATE,"w"), ensure_ascii=False)

def log_signal(code, name, mkt, price, cheap):
    """記錄每次買訊(進場參考)到 signals_log.json,供看板回測績效追蹤。"""
    try: log = json.load(open("signals_log.json"))
    except Exception: log = []
    if not isinstance(log, list): log = []
    log.append({"date": datetime.date.today().isoformat(), "code": code, "name": name,
                "mkt": mkt, "price": price, "cheap": cheap})
    json.dump(log, open("signals_log.json", "w"), ensure_ascii=False)

def check():
    today = datetime.date.today().isoformat()
    st = load_state()
    if st.get("date") != today: st = {"date": today, "alerted": []}
    prices = get_prices()
    changed = False
    for code,(name,mkt,cheap) in WATCH.items():
        px = prices.get(code)
        if px is None: continue
        below = px <= cheap
        if below and code not in st["alerted"]:
            st["alerted"].append(code); changed = True
            nt, nl = get_news(name)
            news_line = f"\n📰 {nt}\n{nl}" if nt else f"\n📰 {yahoo(code,mkt)}"
            push(f"🟢 到價買訊\n{name}({code}) 現價 {px} ≤ 便宜價 {cheap}\n"
                 f"可考慮分批買進(請自行確認基本面與風險){news_line}\n— 台股高ROE看板")
            wp_body = f"{name}({code}) {px} ≤ 便宜價 {cheap},可分批買進" + (f"\n📰 {nt}" if nt else "")
            web_push("🟢 台股高ROE 到價買訊", wp_body, nl or yahoo(code, mkt))
            log_signal(code, name, mkt, px, cheap)   # 記錄買訊供回測績效追蹤
            print(f"ALERT {name}{code} {px}<= {cheap}")
        else:
            print(f"  {name}{code}: {px} (便宜價 {cheap}){' 已通知' if code in st['alerted'] else ''}")
    if changed: save_state(st)

if __name__ == "__main__":
    if "--test" in sys.argv:
        push("✅ 台股高ROE 雲端推播測試成功!到價時會像這樣通知你。")
    else:
        check()
