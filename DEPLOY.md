# 部署到 Streamlit Community Cloud

本資料夾是**獨立範例**，與主專案 `tw_financial_dashboard`（本機 8501）分開。  
**Cloudflare Pages 部署不會帶上 Streamlit**；財報動態 app 請走本文件。

---

## 部署前確認（你已完成）

- [x] 本機 `http://127.0.0.1:8502` 能開，畫面出現「範例 API」紅色提示（代表 app 正常）
- [ ] 有 **GitHub** 帳號
- [ ] 有 **Streamlit Community Cloud** 帳號（用 GitHub 登入）：https://share.streamlit.io

---

## 建議路線：獨立 GitHub repo（最省事）

把**本資料夾內容**當成一個小 repo 推上 GitHub，再從 Cloud 選這個 repo。  
好處：`app.py` 在根目錄、`.streamlit/config.toml` 會被讀到、`.github/workflows/wake.yml` 會生效。

### 步驟 1：在 GitHub 建立空 repo

例如名稱：`streamlit-financial-demo`（Public，不要勾 README）。

### 步驟 2：在本機只對「這個資料夾」初始化 Git 並推送

在終端機執行（路徑請照你的 iCloud 位置）：

```bash
cd "/Users/laipeiyu/Library/Mobile Documents/com~apple~CloudDocs/股票投資專區/streamlit_cloud_financial_demo"

git init
git add app.py requirements.txt .python-version .streamlit .gitignore .github README.md DEPLOY.md
git commit -m "Initial Streamlit Community Cloud demo"

git branch -M main
git remote add origin https://github.com/你的帳號/streamlit-financial-demo.git
git push -u origin main
```

> 若不想把整個「股票投資專區」都放上 GitHub，**只推這個子資料夾**即可，主專案可維持不上傳。

### 步驟 3：在 Streamlit Cloud 建立 App

1. 開啟 https://share.streamlit.io → **Create app**
2. **Repository**：選 `你的帳號/streamlit-financial-demo`
3. **Branch**：`main`
4. **Main file path**：`app.py`
5. **App URL (subdomain)**：自訂，例如 `tw-fin-demo` → 網址為 `https://tw-fin-demo.streamlit.app`
6. **Deploy**

第一次約 1～3 分鐘。成功後用瀏覽器開 `https://你的子網域.streamlit.app`。

### 步驟 4：更新喚醒 workflow（可選，減少休眠）

部署成功後，編輯本 repo 的 `.github/workflows/wake.yml`：

- 把 `TODO_REPLACE_WITH_YOUR_STREAMLIT_APP_URL` 改成你的 app 網址，例如 `https://tw-fin-demo.streamlit.app`
- `git commit` + `git push`  
- 在 GitHub repo → **Actions** 確認 workflow 有跑（需 repo 為 Public 或 GitHub Pro 才保證免費 Actions 額度）

### 步驟 5：與 Cloudflare Pages 串接（可選）

Pages 仍管靜態站；財報範例在 `streamlit.app`：

- **最簡單**：在 `綜合入口.html` 加一個連結指向 `https://你的子網域.streamlit.app`
- **嵌入**：`https://你的子網域.streamlit.app?embed=true` 可放 iframe（需之後改主專案 HTML，勿與本 demo repo 混為一體）

主專案 `tw_financial_dashboard/index.html` 線上仍預設不載 8501；接 Cloud 版要另開需求再改。

---

## 替代路線：整包「股票投資專區」一個 GitHub repo

若你希望**整個 iCloud 專案**都在 GitHub：

1. 在專案**根目錄** `git init`（注意：repo 會很大，含 HTML、archive 等）
2. Cloud 建立 app 時 **Main file path** 填：  
   `streamlit_cloud_financial_demo/app.py`
3. 依賴會用**根目錄**的 `requirements.txt`（已有 streamlit、pandas 等）
4. **限制**：
   - Community Cloud **只認 repo 根目錄**的 `.streamlit/config.toml`；子資料夾內的 config **可能不生效**
   - `streamlit_cloud_financial_demo/.github/workflows/wake.yml` **不會跑**（GitHub 只讀根目錄 `.github/workflows/`）

除非有版本控管需求，否則仍建議用上方「獨立小 repo」。

---

## 部署後檢查清單

| 項目 | 預期 |
|------|------|
| 開啟 `https://xxx.streamlit.app` | 與本機 8502 相同畫面（紅色範例 API 提示） |
| Logs（Cloud 後台） | 無 import error |
| 改 `app.py` 後 push | 約 1 分鐘內自動重 deploy |
| 閒置一段時間後再開 | 可能需數秒～十幾秒喚醒（免費方案） |

---

## 常見錯誤

| 現象 | 處理 |
|------|------|
| `ModuleNotFoundError` | 確認 `requirements.txt` 在 **repo 根目錄**（獨立 repo 時即本資料夾根） |
| **Error installing requirements** | 勿在 `packages.txt` 寫 `python-3.11`（那是 apt 套件名）；Python 版請用 **`.python-version`**（內容 `3.11`） |
| 部署成功但白畫面 | 看 Cloud Logs；確認 `app.py` 路徑正確 |
| 私人 repo 無法部署 | 需授權 Streamlit 存取 private repo，或改 Public |
| wake workflow 沒跑 | 確認 workflow 在 **repo 根** `.github/workflows/`，且 URL 已改掉 TODO |

---

## 下一步（接真實財報，非部署必須）

在 `app.py` 的 `fetch_stock_data()` 實作抓取（可參考主專案 `tw_financial_dashboard/financial_scraping.py`，但請**複製邏輯進本 repo**或抽成共用套件，勿在 Cloud 上依賴未上傳的 iCloud 路徑）。

---

## 與本機埠對照

| 環境 | 網址 |
|------|------|
| 本機範例 | http://127.0.0.1:8502 |
| 本機主專案財報 | http://127.0.0.1:8501（`start_hub`） |
| Cloud 範例 | https://你的子網域.streamlit.app |
| Cloudflare Pages 靜態 | 你現有的 `*.pages.dev` |
