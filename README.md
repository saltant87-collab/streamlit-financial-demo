# Streamlit Community Cloud 範例（獨立子專案）

與主專案 `tw_financial_dashboard`（8501）分開；本機請用 **8502**。

**要上線請讀 → [DEPLOY.md](./DEPLOY.md)**（GitHub + share.streamlit.io 逐步說明）。

## 本機啟動

```bash
cd "/Users/laipeiyu/Library/Mobile Documents/com~apple~CloudDocs/股票投資專區/streamlit_cloud_financial_demo"
python3 -m streamlit run app.py --server.port 8502
```

瀏覽器開：**http://127.0.0.1:8502**（請用 `127.0.0.1`，不要開成 8501）

## 若「跑不動」

| 現象 | 處理 |
|------|------|
| `Port 8502 is already in use` | 關掉舊的 Streamlit 終端（Ctrl+C），或改用 `--server.port 8503` |
| 瀏覽器空白 | 確認網址是 **8502**；按 Streamlit 右上角 **Rerun** |
| 紅色「目前是範例 API…」 | **正常**，代表頁面有跑起來，只是尚未接真實資料 |
| 手機連不上 | Mac 與手機同一 Wi‑Fi；防火牆允許 python3；用終端機印的 Network URL |

## 依賴

```bash
python3 -m pip install -r requirements.txt
```
