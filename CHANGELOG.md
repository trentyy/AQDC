# 修改紀錄

## 2026-11-20 穩定性與正確性修正

依程式審查的建議逐項修正。**未在實機上執行**：開發環境沒有 Python / Arduino / 感測器，
只有純邏輯部分寫了單元測試（`test/test_logic.py`），部署後請依 README 的「驗證」一節確認。

### 新增檔案
| 檔案 | 用途 |
|---|---|
| `common.py` | 共用的設定載入、資料庫連線（含逾時）、log 密鑰遮蔽，取代各程式重複的程式碼 |
| `sensor_parse.py` | 解析 Arduino JSON 並檢查數值範圍（純函式） |
| `actor_logic.py` | 除濕機的時段比對、狀態挑選、在家判斷（純函式） |
| `healthcheck.py`、`service/AQDC_health.*` | 資料新鮮度檢查，過期則記錄並可選擇 webhook 通知 |
| `test/test_logic.py` | 上述純邏輯的單元測試 |
| `CHANGELOG.md`、`MIGRATION.md` | 本紀錄、舊版升級說明 |

### Bug 修正
| 檔案 | 問題 → 修正 |
|---|---|
| `readElectricity.py` | 時間用 `gmtime`（UTC），其他程式用本地時間 → 改為本地時間（**舊資料需遷移**，見 MIGRATION.md） |
| `readWeb.py` | 從 `urllib.error` 匯入 `HTTPError`，抓不到 `requests` 的例外 → 改用 `requests` 的例外，並改為 `raise_for_status()` 後統一處理 |
| `readWeb.py` | `requests.get` 沒有 timeout，對方不回應會永久卡住 → 加 15 秒 timeout |
| `readWeb.py` | `except` 內引用可能未定義的 `cwa_dict`（`NameError`）→ 重寫流程，不再有此狀況 |
| `readWeb.py` | `async` 內呼叫同步 `requests` / `time.sleep`，沒有實際非同步效果 → 改為普通同步迴圈 |
| `readWeb.py` | SQL 以字串拼接，欄位名與值來自外部資料 → 參數化查詢 + 欄位白名單 |
| `readWeb.py` | 例外訊息會把含 API key 的 URL 寫進 log → 以 `redact()` 遮蔽；移除每次輪詢的 `print(json.dumps(data))` |
| `readWeb.py` | EPA 回傳空陣列時 `item` 未定義 → 檢查後回傳 None |
| `readWeb.py` | CWA / EPA 任一失敗會連帶影響另一邊 → 兩個來源各自處理；成功後 10 分鐘、失敗後 1 分鐘重試 |
| `readElectricity.py` | 設定檔路徑 `AQDC-home.json` 與其他程式的 `./setting/` 不一致 → 統一走 `common.py` |
| `readElectricity.py` | 辨識失敗 / 二次確認時沒有 `sleep`，會空轉狂拍照 → 等待 30 秒 |
| `readElectricity.py` | `except` 內 `print(sql)` 時 `sql` 可能未定義；`finally` 內 `camera` 可能未定義 → 修正 |
| `readElectricity.py` | SQL 字串拼接 → 參數化；`DEBUG` 預設改為關閉（`AQDC_DEBUG=1` 開啟） |
| `Arduino/readData_JSON` | `dht_t==NAN` 永遠為 false → 改 `isnan()`，且最多重試 5 次，不再可能無限迴圈 |

### 感測器資料（Sensor）
- **讀取失敗不再送舊值**：PMS7003 讀不到時改送 `null`（原本沿用上一次的值）；MH-Z19B 回 0、DS18B20 回 -127 也送 `null`。
- **數值範圍檢查**（`sensor_parse.py`）：CO2 300–5000、濕度 0–100、溫度 -40–85 等，超出範圍的感測器整組不寫入並記錄 warning。
- **序列埠**：`readline` 加 timeout；積壓多行時只取最新一行（原本會把舊資料全部標上現在時間）；`SerialException`（USB 掉線）自動重連；資料庫錯誤自動重試。
- **四張表寫入同一個交易**，失敗整批 rollback。

### 除濕機控制（`actor.py`）
- **主迴圈錯誤處理**：API / 資料庫例外只記錄並進入下一輪，不再讓程式崩潰；連續失敗 3 次後自動重新登入。啟動時登入失敗也會重試。
- **資料新鮮度**：CO2、濕度資料超過 15 分鐘沒更新視為失效。CO2 失效時維持原在家狀態；濕度失效時不做自動開/關機。
- **在家判斷**（`PresenceDetector`）：取近 10 分鐘平均；平均 > 600 ppm 判定在家，平均 < 500 ppm 且持續 30 分鐘才判定外出，500–600 之間維持原狀態。（原本單點 > 600 即在家）
- **時段比對**：區間改為「起點含、終點不含」（原本整點那一分鐘會漏掉）；支援跨午夜（`start_time > end_time`）。
- **預設狀態明確化**：都不符合時使用 `state` 編號最小的一筆（行為與舊版相同，但不再依賴迴圈變數殘留）；表為空時記錄錯誤並略過該輪。
- **設定套用**：狀態改變，或同一狀態的 `humid_setting` / `set_fan_speed` 被改過時就套用（原本只有狀態改變時才套用）；套用失敗不更新狀態，下一輪重試。
- **重複指令**：同一道指令 3 分鐘內不重送，避免雲端狀態延遲造成重複下指令。
- **壓縮機保護**：濕度自動開/關機之間至少間隔 10 分鐘（電源按鈕強制關機與 `auto_turn_off=0` 開機不受限）。
- **其他**：每輪只開一個資料庫連線；改用 loguru 寫 `./log/actor.log`；修正「高於上限」訊息誤印下限值；移除 `print` 內寫死的 `600`。
- 上述門檻都可在 `AQDC-actor.json` 內選填覆蓋（見 README）。

### 部署
- 所有 service 加上 `RestartSec=10`，避免異常時快速重啟迴圈。
- `.gitignore` 加入 `log/`。
- `setting_example/AQDC-home-default.json` 加入選填的 `healthcheck`。

### 未處理（刻意保留）
- `Arduino`：`pms.passiveMode()` 仍為註解、`autoCalibration()` 仍為開啟、`delay(60000)` 與 SoftwareSerial 輪流 `listen()` 的架構未動——這些會改變硬體行為，需要實機驗證，建議另外測試。
- `readElectricity.py`：七段顯示器 OCR 的裁切座標與閾值仍為寫死；建議長期改用智慧插座 / PZEM-004T 這類可直接回報電壓電流的設備。
- `api/app/main.py`（冰箱 AM2108 API）未審查也未修改；已知會 `print` 含密碼的資料庫連線字串、並以 `debug=True` 啟動。
- 服務間仍以資料庫輪詢溝通（未導入 MQTT / Home Assistant）。

## 2026-11-20（續）Pi 實機部署時發現的問題

- **資料表名稱可設定**：`AQDC-home.json` 新增選填 `table_names`，例如 `{"cwa_Home": "cwa_home", "epa_Home": "epa_home"}`。
  Linux 的 MariaDB 預設區分大小寫（`lower_case_table_names=0`），部署的 Pi 上實際表名是小寫；沒設定則沿用 `cwa_Home` / `epa_Home`。`readWeb.py`、`healthcheck.py` 已套用。
- **EPA 解析修正**：目前使用的端點 `aqx_p_212` 直接回傳 list，而不是 `{"records": [...]}`，舊版會每分鐘丟出 `TypeError`（log 因此膨脹到數百 MB）。
  解析移到 `web_parse.py`，同時支援 list 與 dict，並取最新 `monitordate` 時間點的 PM2.5 / PM10；空值、空字串會略過。
- **CWA 缺測值**：溫度、濕度小於等於 -90（官方以 -99 等代碼表示無資料）整筆捨棄；氣壓缺值只是不存該欄位。
  CWA 的 URL、參數（`Authorization`、`StationId`）與回傳結構（`records.Station[].WeatherElement`）經實機驗證**沒有變動**，沒有查到官方的異動公告，也沒能讀取官方產品說明文件的缺測代碼章節。
- `setting_example` 的 EPA 範例改為 `aqx_p_212` 並加上 `filters=siteid,EQ,24`（固定新竹測站），避免依賴回傳順序。
- `test/test_logic.py` 加入 CWA / EPA 解析測試。
- `actor.py`：登入失敗的重試間隔改為指數退避（60 秒起、最長 15 分鐘）。

### 2026-11-20 rpi4-4g 部署紀錄
- 備份：Pi 上原本未提交的修改已存成分支 `pi-local-changes-20261120`（含小寫表名、`checkAlwaysOff` 的除錯 `print`），再以 `master` 覆蓋。
- `setting/AQDC-home.json`：`host` 由 `192.168.31.15`（無線網卡 IP，Pi 改用有線後連不到）改為 `127.0.0.1`，並加入 `table_names`（小寫）。舊檔備份為 `AQDC-home.json.bak-20261120`。
- 已啟用：`AQDC_cwa`（恢復寫入）、`AQDC_local`（恢復寫入）、`AQDC_health.timer`；`AQDC_actor` 因日立雲端登入失敗無法工作（見下）。
- `AQDC_electricity` 未架設硬體，未安裝；`home_electricity` 資料表不存在，所以不需要時區遷移。
- `actor` 失敗原因：`LibJciHitachi` 登入時 `RuntimeError: An event occurred but wasn't accompanied with data when refreshing RD-200HH1 support code`。
  升級到最新版 1.7.2 結果相同，不是版本問題；通常代表日立雲端沒有回傳設備的 support code（設備離線 / 未連上雲端，或官方 App 正在使用）。

### 2026-11-20 氣象署測站改為「家」與「工作地點」
- 設定檔 `cwa.stations` 可列出多個測站（`id`、`label`、`table`），每個測站各抓各的、各寫各的表；沒有 `stations` 時沿用舊的 `cwa.params.StationId`（寫入 `cwa_Home`）。
- 因為 `cwa_home` 的主鍵只有 `DateTime`，同一觀測時間的兩個測站會互相衝突，所以工作地點寫入結構相同的新表 `cwa_work`（`CREATE TABLE cwa_work LIKE cwa_home`）。
- 資料集改用 `O-A0001-001`（自動氣象站，876 站）：`O-A0003-001` 裡的自動站氣壓是 -99，這個資料集才有氣壓。
- 測站（距離以 WGS84 座標計算）：
  - 家（新竹市東區柴橋路）：**國三S103K**（`CAD090`，新竹市東區），距柴橋路約 0.3～1.3 公里。
  - 工作（國立清華大學）：**新竹市東區**（`C0D660`），距清大約 0.95 公里。
- 回傳的測站代碼必須與請求相符才寫入（`parse_cwa(station_id=...)`）；`healthcheck.py` 會檢查每個測站的表。
- 注意：`cwa_home` 既有歷史資料是「新竹」（`467571`，竹北市局屬站），切換後同一張表會混有兩個測站，以 `StationName` 區分；Grafana 面板若不分測站，會在切換時間點出現落差。

### 2026-11-20 除濕機改為「不在家才運作」，每半小時判定
- `actor.py` 新增選填設定（`AQDC-actor.json`）：
  - `AWAY_ONLY`（預設 false）：true 時在家一律關機，不在家才依濕度控制。
  - `CONTROL_INTERVAL_MINUTES`（預設 0 = 每分鐘）：開關判定間隔，以當天 0 點起算對齊（30 即整點與 30 分各一次）。判定失敗（例如雲端指令失敗）不消耗該時段，下一輪重試。
- 開關條件改為：濕度 **> `humid_upper_limit`** 開機；濕度 **<= `humid_lower_limit`** 關機（原本是 `>=` 與 `<`）。邏輯拆成 `actor_logic.decide_switch`，附單元測試。
- `power=0`（電源按鈕強制關機）仍每分鐘檢查，不受判定間隔限制。
- rpi4-4g 的設定：`AQDC-actor.json` 加入 `AWAY_ONLY: true`、`CONTROL_INTERVAL_MINUTES: 30`；資料庫 `actor_RD-200HH1_botton` 設為 `power=1, auto_turn_off=1`；`actor_RD-200HH1` 中 `in_home=0` 的狀態改為 `humid_setting=50, humid_lower_limit=50, humid_upper_limit=60`（修改前的值記錄在下方部署紀錄）。
  修改前（可用來還原）：`actor_RD-200HH1_botton`：`power=0, auto_turn_off=0`；`actor_RD-200HH1`（state, in_home, humid_setting, lower, upper, fan）：`(0,0,55,60,65,2)`、`(2,0,40,45,55,4)`，其餘 `in_home=1` 的列未改動。`AQDC-actor.json` 備份：`AQDC-actor.json.bak-20261120`。
- 已刪除 rpi4-4g 上 10 個已輪替的 `log/readWeb.20*.log`（約 2.5GB，內容幾乎都是資料庫連不上的錯誤）；使用中的 `readWeb.log` 保留。

### 2026-11-20 Grafana 與 API
- 新增儀表板「AQDC 工作地點」（`grafana/dashboards/aqdc-work.json`，uid `aqdc-work`）：工作地點測站、目前溫度 / 濕度 / 氣壓，以及工作地點與家（國三S103K）的溫度、濕度、氣壓對照曲線，和最近 10 筆觀測。以 provisioning 方式載入（`grafana/provisioning/aqdc.yaml`，複製到 `/etc/grafana/provisioning/dashboards/`）。
- rpi4-4g：Grafana 的 MySQL 資料來源位址由 `192.168.31.15:3306` 改為 `127.0.0.1:3306`（有線 / 無線切換不再影響儀表板）。
- `api/app/main.py`：移除啟動時 `print` 含密碼的資料庫連線字串。
- 日立雲端登入問題（設備需重新設定連網功能）：待使用者回家處理，`actor` 先維持重試。
