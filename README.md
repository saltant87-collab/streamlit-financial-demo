# Streamlit Community Cloud 範例（獨立子專案）

與主專案 `tw_financial_dashboard`（8501）分開；本機請用 **8502**。

**要上線請讀 → [DEPLOY.md](./DEPLOY.md)**（GitHub + share.streamlit.io 逐步說明）。

已接上 **MOPS 真實財報**（與主專案相同抓取／指標邏輯，程式在本子資料夾內獨立複本，不影響 `tw_financial_dashboard`）。

Cloud 版區塊（對齊本機 8501 主結構）：

- **一、財報分析**：指標表、**圖表解說**、**風險提醒**
- **二、技術面與籌碼面**：內建 `modules/stock_report_generator.py`（TWSE + Yahoo；海外主機 API 可能失敗）

側欄可開關「圖表解說」「載入技術面／籌碼面」。

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
| 查無財報 | 先確認代號為上市櫃四碼；雲端若 MOPS 失敗會自動改 Yahoo 備援 |
| 手機連不上 | Mac 與手機同一 Wi‑Fi；防火牆允許 python3；用終端機印的 Network URL |

## 依賴

```bash
python3 -m pip install -r requirements.txt
```
