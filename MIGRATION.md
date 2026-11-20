# 從舊版升級到目前版本

舊版指 2026-11-20 修正之前的版本（最後一個舊版 commit 為 `77b2c98`）。
**不需要改資料表結構、不需要改既有的設定檔內容**；只有一處資料需要遷移（時區），其餘是行為差異。

## 升級步驟

1. **備份**：`mysqldump` 整個資料庫，另外備份 `setting/` 目錄。
2. **確認 Pi 時區**：`timedatectl` 應顯示 `Asia/Taipei`；不是的話 `sudo timedatectl set-timezone Asia/Taipei`。
   新版所有程式一律寫入「本地時間」。
3. **更新程式**：
   ```bash
   cd /home/pi/Github/AQDC && git pull
   .venv/bin/pip install -r requirements.txt     # 依賴沒有變動，確認即可
   ```
4. **設定檔**：沿用原本的 `setting/AQDC-home.json`、`setting/AQDC-actor.json`，不用改。
   新增的鍵都是選填（見 README）。
   - 若你之前把 `AQDC-home.json` 放在專案根目錄給 `readElectricity.py` 用（舊版讀的是 `./AQDC-home.json`），
     現在統一讀 `./setting/AQDC-home.json`，請確認 `setting/` 內那份是正確的，根目錄的舊檔可以刪除。
5. **更新 service 並重新載入**：
   ```bash
   sudo cp service/AQDC_*.service service/AQDC_*.timer /etc/systemd/system/
   sudo systemctl daemon-reload
   sudo systemctl enable --now AQDC_health.timer
   ```
6. **遷移 `home_electricity` 的舊資料（時區）**——見下節，**只做一次**。
7. **重新燒錄 Arduino**（選做但建議）：用 Arduino IDE 燒錄新的 `readData_JSON.ino`。
   不燒也能運作：舊韌體送的 `0` / `-127` 會被 Python 端的範圍檢查擋掉；
   但 PMS7003 讀不到時仍會送舊值，只有新韌體會改送 `null`。
8. **重啟服務**：
   ```bash
   sudo systemctl restart AQDC_local AQDC_cwa AQDC_actor
   sudo systemctl restart AQDC_electricity   # 有使用才需要
   ```
9. **驗證**：依 README 的「驗證」一節；觀察 `log/actor.log` 一段時間。

## 時區遷移（`home_electricity`）

舊版 `readElectricity.py` 以 UTC 寫入，其他表是本地時間（UTC+8），所以舊資料晚 8 小時。
新版統一為本地時間。選擇其中一種做法：

**做法 A（建議）：把舊資料往後移 8 小時，與其他表對齊**

1. 先停止寫入：`sudo systemctl stop AQDC_electricity`
2. 在 MySQL 執行（`ORDER BY ... DESC` 是為了避免時間欄位為主鍵時，位移過程撞到尚未位移的列）：
   ```sql
   UPDATE home_electricity SET `time` = `time` + INTERVAL 8 HOUR ORDER BY `time` DESC;
   ```
3. 啟動新版：`sudo systemctl start AQDC_electricity`

此語句**只能執行一次**，重複執行會再多移 8 小時；也不要在新版已經寫入資料後才執行（新資料會被一起位移）。
若已經不小心這樣做，用備份還原再重來。

**做法 B：不動舊資料**，只是同一張表內 `time` 會在切換時間點出現 8 小時的跳躍。
如果你的 Grafana 面板為了補償 UTC 在 `home_electricity` 的查詢中寫了 `+ INTERVAL 8 HOUR` 或時區轉換，
遷移（做法 A）後要把那段補償拿掉，否則會多移 8 小時。

## 行為差異（升級後可能注意到的變化）

| 項目 | 舊版 | 新版 |
|---|---|---|
| 在家判斷 | 最新一筆 CO2 > 600 即在家，否則外出 | 近 10 分鐘平均 > 600 在家；平均 < 500 且持續 30 分鐘才外出；之間維持原狀態。外出判定會比以前慢最多約 30 分鐘 |
| 感測器資料過期 | 一直沿用最後一筆 | 超過 15 分鐘視為失效：CO2 失效維持原狀態、濕度失效不自動開關機 |
| 時段邊界 | `start < t < end`（整點那一分鐘漏掉） | `start <= t < end`；`start > end` 視為跨午夜 |
| 改了資料庫裡目前狀態的風速 / 濕度設定 | 要等狀態切換才會套用 | 下一輪（1 分鐘內）就套用 |
| 手動調整機器 | 只在狀態切換時被覆蓋 | 同左（沒有改變） |
| 濕度自動開關機 | 可能短時間反覆開關 | 兩次自動開 / 關至少間隔 10 分鐘 |
| 例外 | 程式崩潰，靠 systemd 重啟並重新登入 | 記錄後下一輪繼續；連續失敗 3 次才重新登入 |
| log | `actor.py` 只有 `print` | `log/actor.log` 與 journal |
| 外部資料抓取 | 失敗後等 60–90 秒、錯誤 log 含 API key | 成功 10 分鐘 / 失敗 1 分鐘重試，log 已遮蔽 API key |
| 感測器異常值 | 照寫入（CO2=0、溫度 -127 等） | 範圍外的整組感測器不寫入，並記錄 `rejected:` |
| `readElectricity.py` DEBUG | 預設開啟 | 預設關閉，`AQDC_DEBUG=1` 才開 |

想要接近舊版的在家判斷，可在 `AQDC-actor.json` 設 `"CO2_WINDOW_MINUTES": 1`、`"CO2_AWAY_PPM": 600`、`"AWAY_MINUTES": 0`。

## 回滾

`git checkout 77b2c98` 後重新 `daemon-reload` 並重啟服務即可。程式不改資料表結構，只有做過「做法 A」時，
`home_electricity` 的舊資料已是本地時間，舊版 `readElectricity.py` 會再以 UTC 寫入（和升級前相同），
若要完全復原請用升級前的備份還原該表。
