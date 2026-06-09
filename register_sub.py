# -*- coding: utf-8 -*-
"""從 GitHub Issue 內容解析 Web Push 訂閱碼,去重後寫入 subscriptions.json。
   由 .github/workflows/register-sub.yml 在有人開 issue 時自動執行。"""
import os, json, re

body = os.environ.get("ISSUE_BODY", "")

# 優先抓 ```json ... ``` 區塊,否則抓含 endpoint 的 JSON 物件
m = re.search(r"```(?:json)?\s*(\{.*\})\s*```", body, re.S) or re.search(r"(\{.*\"endpoint\".*\})", body, re.S)
if not m:
    print("找不到訂閱 JSON,略過。"); raise SystemExit(0)
try:
    sub = json.loads(m.group(1))
except Exception as e:
    print("訂閱 JSON 解析失敗:", e); raise SystemExit(0)
if not sub.get("endpoint"):
    print("無 endpoint,略過。"); raise SystemExit(0)

try:
    subs = json.load(open("subscriptions.json"))
    if not isinstance(subs, list): subs = []
except Exception:
    subs = []

if any(s.get("endpoint") == sub["endpoint"] for s in subs):
    print("訂閱已存在,不重複新增。")
else:
    subs.append(sub)
    json.dump(subs, open("subscriptions.json", "w"), ensure_ascii=False)
    print(f"已新增訂閱,目前共 {len(subs)} 筆。")
