# 台股高ROE 行動看板 — 雲端部署包

> ✅ **已部署**:https://t113c29540-crypto.github.io/twroe-dashboard/ ｜ repo:https://github.com/t113c29540-crypto/twroe-dashboard

一個 GitHub repo 同時搞定兩件事(全部**免費**):
- **A. PWA 行動看板**(GitHub Pages,HTTPS)→ 手機「加入主畫面」變 App、可離線開啟
- **B. LINE 到價自動推播**(GitHub Actions,7×24)→ 跌到便宜價自動推到你 LINE

```
_deploy/
├─ index.html              行動看板(PWA)
├─ viewer.html             互動圖表閱覽器(排名/逐年ROE/股價區間/估值;滾輪縮放)
├─ manifest.webmanifest    PWA 設定
├─ sw.js                   離線 Service Worker
├─ icon-192/512.png, apple-touch-icon.png   App 圖示
├─ line_alert.py           到價推播(雲端版)
├─ alert_state.json        去重狀態(自動更新)
└─ .github/workflows/line-alert.yml   每5分鐘自動檢查
```

---

## 一次設定(約 15 分鐘)

### 步驟 0：建立 GitHub repo 並上傳
1. 到 https://github.com/new 建一個 **Public** repo(公開→Actions 免費無上限;Secrets 不會外洩)
2. 把 `_deploy/` 內**所有檔案**上傳到 repo 根目錄(含隱藏的 `.github/` 資料夾)
   - 用網頁拖拉上傳,或:`git init && git add . && git commit -m init && git remote add origin <你的repo> && git push -u origin main`

### 步驟 A：開啟 PWA 看板(GitHub Pages)
1. repo → **Settings → Pages**
2. Source 選 **Deploy from a branch**,Branch 選 `main` / `/(root)` → Save
3. 約1分鐘後得到網址:`https://<你的帳號>.github.io/<repo名>/`
4. 手機 Safari 開該網址 → 分享 → **加入主畫面** → 變成 App 圖示(可離線開啟)

### 步驟 B：開啟 LINE 到價推播
1. 建立 LINE Bot 並取得金鑰(詳見下方「LINE 設定」)
2. repo → **Settings → Secrets and variables → Actions → New repository secret**,新增兩個:
   - `LINE_TOKEN`  = 你的 Channel access token
   - `LINE_USER_ID` = 你的 User ID
3. repo → **Actions** 分頁 → 若提示啟用就按啟用 → 點「台股高ROE 到價推播」→ **Run workflow**(手動跑一次測試)
4. 之後**每 5 分鐘**(台北 09:00–14:00 盤中、週一到五)自動檢查,跌到便宜價就推 LINE

> 想先測推播:把 `line_alert.py` 最後改成 `push(...)` 或本機跑 `LINE_TOKEN=xxx LINE_USER_ID=yyy python3 line_alert.py --test`

---

## LINE 設定(取得 TOKEN 與 USER_ID)
> ⚠️ LINE Notify 已於 2025/3 停用,改用官方 **Messaging API**。
1. 到 https://developers.line.biz/console/ 用 LINE 登入
2. 建 Provider → 建一個 **Messaging API** channel
3. 「Messaging API」分頁 → **Issue** 取得 **Channel access token (long-lived)** → 這是 `LINE_TOKEN`
4. 同頁用手機 LINE 掃 QR code,把這個 Bot **加為好友**(沒加好友收不到推播)
5. 「Basic settings」分頁最下方 **Your user ID** → 這是 `LINE_USER_ID`

---

## (選用)Web Push 手機推播(關 App 也能收)
> 有 LINE 推播通常就夠了;想額外加「PWA 推播」再做這段。
1. 本包已內建 VAPID **公鑰**(在 index.html);**私鑰**在我幫你產生的 `VAPID_PRIVATE.pem`
   (位於 `台股20年ROE分析/_build/VAPID_PRIVATE.pem`,**請勿上傳到 repo**)。
2. repo → Settings → Secrets and variables → Actions,再加兩個 secret:
   - `VAPID_PRIVATE`  = 貼上 `VAPID_PRIVATE.pem` 全文(含 `-----BEGIN/END-----` 行)
   - `VAPID_SUBJECT`  = `mailto:你的Email`
3. 用手機開看板(**iPhone 需先「加入主畫面」並從桌面圖示開啟**)→ 按「📲 推播」→ 允許通知
4. 按「📤 **一鍵提交到雲端**」→ 跳到 GitHub 按 **Submit new issue** → 系統(register-sub workflow)**自動把訂閱寫入 `subscriptions.json` 並關閉 issue**(免手動貼)
   - 備援:也可按「📋 複製」手動貼到 `subscriptions.json` 陣列 `[]` 內
5. 之後到價,**LINE 與手機推播都會通知**(即使關閉 App),且內容含**該股新聞**
> iOS 限制:僅「已加入主畫面的 PWA、從圖示開啟」可收 Web Push(iOS 16.4+);Android/桌面 Chrome 直接支援。

---

## 自訂
- 改監看清單 / 便宜價:編輯 `line_alert.py` 的 `WATCH`
- 改檢查頻率 / 時段:編輯 `.github/workflows/line-alert.yml` 的 `cron`
- 看板內容:`index.html` 內 `ANALYZED` 陣列

## 多人 / LINE 群組推播
- `LINE_USER_ID` 可填**逗號分隔**的多個收件人:多位使用者的 userId、或群組 groupId(Bot 需先被加入該群組),例如 `Uxxx,Uyyy,Cgroupzzz`
- 或填 `broadcast`:**廣播**給所有加 Bot 好友的人
- 取得 groupId:需設一個 webhook 接收 LINE 事件(把 Bot 拉進群組後,從事件取得 `source.groupId`)

## 回測績效追蹤
- 每次到價買訊,`line_alert.py` 會把 `{日期, 代號, 訊號價, 便宜價}` 寫入 `signals_log.json`(由 workflow 自動 commit)
- 看板「📈 績效」分頁:讀取 `signals_log.json`,自動算每筆買訊**至今報酬、勝率、平均報酬**,並列出目前符合買訊的股票

## 注意
- GitHub Actions 排程偶爾延遲幾分鐘,屬正常。
- 報價來自證交所經第三方代理,可能延遲;**本工具只通知不下單**,下單請於元大App以憑證親自確認。
- **非投資建議,盈虧自負。**
