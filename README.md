# AQDC — Air Quality Data Collector

收集室內空氣品質（CO2、PM、溫濕度、用電）與戶外氣象 / 空品資料存入 MySQL，
並依在家狀態與濕度自動控制日立除濕機（RD-200HH1）。資料可用 Grafana 顯示。

> 從舊版升級請看 [MIGRATION.md](MIGRATION.md)；修改內容見 [CHANGELOG.md](CHANGELOG.md)。

## 架構

```
Arduino ──USB 序列埠 JSON──▶ readSensor.py ──┐
Pi Camera ─(七段顯示器 OCR)─▶ readElectricity.py ─┤
氣象署 / 環境部 API ────────▶ readWeb.py ─────┼──▶ MySQL ◀── Grafana
                                              │      ▲
                       actor.py ◀─────────────┘      │ 讀 CO2 / 濕度 / 狀態設定
                          └──▶ 日立雲端 API ──▶ 除濕機   healthcheck.py（檢查資料是否過期）
```

| 程式 | 作用 | systemd |
|---|---|---|
| `readSensor.py` | 讀 Arduino（DS18B20、DHT22、PMS7003、MH-Z19B）寫入資料庫 | `AQDC_local` |
| `readWeb.py` | 每 10 分鐘抓氣象署 / 環境部資料 | `AQDC_cwa` |
| `readElectricity.py` | 拍照讀延長線電錶的電壓電流（需要 Pi Camera） | `AQDC_electricity` |
| `actor.py` | 控制除濕機 | `AQDC_actor` |
| `healthcheck.py` | 檢查各表是否太久沒有新資料 | `AQDC_health.timer` |
| `api/` | 冰箱溫濕度（AM2108）的收資料 API，Docker 部署 | docker compose |

共用程式：`common.py`（設定 / 資料庫）、`sensor_parse.py`（資料檢查）、`actor_logic.py`（控制邏輯）。

## 硬體

- Raspberry Pi（伺服器、資料收集、跑所有 Python 服務）
- Arduino Uno + 感測器：DS18B20（溫度）、DHT22（溫濕度）、PMS7003（PM1 / PM2.5 / PM10）、MH-Z19B（CO2）、I2C LCD 2004
- Raspberry Pi Camera（拍延長線的電錶）
- 日立除濕機 RD-200HH1（透過 LibJciHitachi 雲端 API 控制）

## 部署（Raspberry Pi）

### 1. 系統設定

```bash
sudo timedatectl set-timezone Asia/Taipei   # 所有時間戳記都用本地時間，務必設定
sudo apt install -y python3-venv git mariadb-client   # MySQL 可在同機或其他主機
```

### 2. 取得程式與安裝套件

```bash
cd /home/pi/Github
git clone git@github.com:trentyy/AQDC.git && cd AQDC
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
```

`readElectricity.py` 使用系統 Python（需要 `picamera`、`RPi.GPIO`、opencv、pytesseract 等），
另外在系統安裝：`sudo apt install python3-picamera python3-opencv python3-numpy python3-pil python3-matplotlib tesseract-ocr python3-pymysql python3-loguru`
（`picamera` 只支援 Raspberry Pi OS Buster 及更早版本；較新的系統建議改用智慧插座取代這個程式）。

### 3. 設定檔

```bash
mkdir -p setting log pic
cp setting_example/AQDC-home-default.json  setting/AQDC-home.json
cp setting_example/AQDC-actor-default.json setting/AQDC-actor.json
```

編輯這兩個檔案（已被 `.gitignore` 排除，不會進版控；建議 `chmod 600 setting/*`）。
設定目錄預設 `./setting`，可用環境變數 `AQDC_SETTING_DIR` 改位置。

**`AQDC-home.json`**：`host/user/pw/db` 是 MySQL；`cwa` 是[氣象署開放資料](https://opendata.cwa.gov.tw/)（`Authorization` 為你的授權碼、`StationId` 為測站）；
`airtw_epa` 是[環境部開放資料](https://data.moenv.gov.tw/)；`healthcheck.notify_url` 選填，填 webhook 網址就會在資料過期時通知。
`healthcheck.max_age_minutes` 可選填，例如 `{"home_dht22": 5}` 覆蓋各表的容許延遲（分鐘）。
`table_names` 可選填，對應資料表的實際名稱，例如 `{"cwa_Home": "cwa_home", "epa_Home": "epa_home"}`（Linux 的 MySQL 區分大小寫）。

**資料庫位址（`host`）**：資料庫與服務在同一台 Pi 時，請填 `127.0.0.1`，不要填網卡 IP。
同一台 Pi 有線（eth0）與無線（wlan0）的 IP 不同（本專案為 192.168.31.14 / .15），填其中一個會在切換網路後連不到資料庫；
`127.0.0.1` 與網路介面無關。Docker 容器內的服務（`api/`）則填 Docker 閘道位址（見 `docker-compose.yml` 的 `host.docker.internal`）。
從其他電腦連線（Grafana、DB 工具）請用 Tailscale 位址或主機名稱，這類位址也不會隨有線 / 無線切換而變。

**`AQDC-actor.json`**：`EMAIL`、`PASSWORD`、`DEVICENAME` 為日立 App 帳號與設備名稱。以下為**選填**，沒寫就用預設值：

| 鍵 | 預設 | 說明 |
|---|---|---|
| `CO2_HOME_PPM` | 600 | 近期平均 CO2 高於此值 → 在家 |
| `CO2_AWAY_PPM` | 500 | 平均低於此值且持續 `AWAY_MINUTES` → 外出（介於兩者之間維持原狀態） |
| `AWAY_MINUTES` | 30 | 外出判定的持續時間 |
| `CO2_WINDOW_MINUTES` | 10 | CO2 取平均的時間範圍 |
| `SENSOR_STALE_MINUTES` | 15 | 感測器資料超過幾分鐘沒更新就視為失效 |
| `MIN_SWITCH_SECONDS` | 600 | 濕度自動開 / 關機的最短間隔（保護壓縮機） |
| `COMMAND_COOLDOWN_SECONDS` | 180 | 同一道指令的重送間隔 |

### 4. 資料庫

程式用到的資料表（欄位名稱需一致；`fridge_AM2108` 由 `api/` 自動建立）：

| 資料表 | 欄位 |
|---|---|
| `home_ds18b20` | `time`, `temperature` |
| `home_dht22` | `time`, `temperature`, `humidity` |
| `home_pms7003` | `time`, `pm1`, `pm2_5`, `pm10` |
| `home_mhz19b` | `time`, `temperature`, `co2` |
| `home_electricity` | `time`, `Voltage`, `Ampere` |
| `cwa_Home` | `StationName`, `DateTime`, `AirTemperature`, `RelativeHumidity`, `AirPressure` |
| `epa_Home` | `PM2_5`, `PM10`, `time` |
| `actor_RD-200HH1` | `state`, `in_home`, `start_time`, `end_time`, `humid_setting`, `humid_lower_limit`, `humid_upper_limit`, `set_fan_speed`, `description` |
| `actor_RD-200HH1_botton` | `power`, `auto_turn_off`, `auto_enabled`, `auto_start_time`, `auto_end_time`（單列，見下方「自動開關排程」） |

`actor_RD-200HH1` 每列是一個狀態：在 `[start_time, end_time)` 且 `in_home` 相符時套用該列的風速與濕度設定；
`start_time > end_time` 代表跨午夜；都不符合時用 `state` 編號最小的一列。
`cwa_Home`、`epa_Home` 的時間欄位建議設為主鍵 / 唯一鍵，程式用 `INSERT IGNORE` 避免重複。

### 5. Arduino

用 Arduino IDE 安裝函式庫 ArduinoJson（v6）、DallasTemperature、OneWire、DHT、PMS、MHZ19、LiquidCrystal_I2C，
燒錄 `Arduino/readData_JSON/readData_JSON.ino`，以 USB 接到 Pi（預期為 `/dev/ttyACM0`，不同請改 `readSensor.py` 的 `COM_PORT`）。
感測器讀不到時韌體會送 `null`，不會送舊值或錯誤值。

### 6. 啟動服務

```bash
sudo cp service/AQDC_*.service service/AQDC_*.timer /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now AQDC_local AQDC_cwa AQDC_actor AQDC_health.timer
sudo systemctl enable --now AQDC_electricity   # 有接 Pi Camera 才啟動
```

service 內的路徑預設為 `/home/pi/Github/AQDC` 與使用者 `pi`，不同請自行修改。

### 7. 冰箱 API（選用）

```bash
cd api && printf 'DBHOST=...\nUSER=...\nPW=...\nDB=...\n' > .env   # 變數名稱見 api/app/main.py
cd .. && docker compose up -d --build
```

## 驗證

```bash
python3 -m unittest discover -s test -p "test_logic.py"    # 純邏輯單元測試
python3 -m unittest discover -s test -p "test_metrics.py"  # Prometheus 指標（需已安裝 requirements.txt）
journalctl -u AQDC_local -f        # 應每分鐘看到 "saved: [...]"
tail -f log/actor.log              # 應看到狀態切換與下指令的原因
.venv/bin/python healthcheck.py && echo OK   # 各表資料都新鮮則回傳 0
```

## Prometheus 指標（readSensor）

`readSensor.py` 每次成功解析序列埠資料，除了寫入 MySQL，也更新記憶體中的指標並在 `http://<host>:<port>/metrics` 提供
（只用標準函式庫 `http.server`，沒有額外套件）。指標更新與資料庫無關，資料庫失敗時仍會更新。

| 指標 | 標籤 | 來源 |
|---|---|---|
| `aqdc_temperature_celsius` | `sensor="ds18b20"｜"dht22"｜"mhz19b"` | 三張表的 `temperature` |
| `aqdc_humidity_percent` | `sensor="dht22"` | `home_dht22.humidity` |
| `aqdc_co2_ppm` | `sensor="mhz19b"` | `home_mhz19b.co2` |
| `aqdc_pm_ug_per_m3` | `size="pm1"｜"pm2_5"｜"pm10"` | `home_pms7003` |
| `aqdc_last_reading_timestamp_seconds` | `sensor="ds18b20"｜"dht22"｜"mhz19b"｜"pms7003"` | 該感測器最後一次成功讀取的 Unix 時間 |

- 都是 gauge。感測器讀不到（`null`、超出範圍被拒絕）時保留舊值與舊時間戳記，不編造資料；從未讀到過的感測器完全不輸出。
  判斷資料是否過期請看 `aqdc_last_reading_timestamp_seconds`。
- 對照表在 `sensor_metrics.py` 的 `VALUE_METRICS` / `TIMESTAMP_SENSORS`，是明確列舉，不是依欄位名稱產生。
- **位址設定**：預設 `127.0.0.1:9106`。在 `setting/AQDC-home.json` 加 `"metrics": {"host": "<Pi 的 Tailscale IP>", "port": 9106}`，
  或用環境變數 `AQDC_METRICS_HOST` / `AQDC_METRICS_PORT`（優先於設定檔）。部署到 Pi 時請綁 Tailscale IP（`tailscale ip -4`），
  Portal 的 Prometheus 透過 Tailscale 抓取。**不要綁 `0.0.0.0`**——程式會拒絕萬用位址並關閉端點。
- 綁定失敗（例如開機時 Tailscale 尚未就緒）只記錄錯誤並每 30 秒重試，不影響讀感測器的主迴圈；
  `AQDC_local.service` 也加了 `After=/Wants=tailscaled.service`。
- 驗證：`curl http://<Tailscale IP>:9106/metrics`，數值應與各表最新一筆一致。

## 自動開關排程（Portal 可設定）

除濕機的「自動開 / 關」（依濕度、`AWAY_ONLY` 在家關機）只在排程時段內作用，設定放在 `actor_RD-200HH1_botton`（單列）：

| 欄位 | 預設 | 說明 |
|---|---|---|
| `auto_enabled` | 1 | 0 = 完全停用自動開關（例如窗戶沒關時）；優先於排程 |
| `auto_start_time` | `10:00:00` | 排程開始（含） |
| `auto_end_time` | `17:00:00` | 排程結束（不含）；開始 > 結束代表跨午夜；相等代表空時段（永不自動） |

- 排程外或停用時 `actor.py` **完全不自動開關**：不會自動開，也不會自動關（機器開著就維持開著）。
- `power=0`（強制關機）不受排程影響，仍每分鐘檢查——這是緊急開關。風速 / 濕度設定的套用也不受排程影響，只是不碰開關。
- 時間取 Pi 的本地時區；修改後下一輪（最多 1 分鐘）生效，不必重啟。
- 現有資料庫要先加欄位（一次性）：

```sql
ALTER TABLE `actor_RD-200HH1_botton`
  ADD COLUMN `auto_enabled` TINYINT(1) NOT NULL DEFAULT 1,
  ADD COLUMN `auto_start_time` TIME NOT NULL DEFAULT '10:00:00',
  ADD COLUMN `auto_end_time` TIME NOT NULL DEFAULT '17:00:00';
```

- Portal 建議使用專用資料庫帳號，只給這三欄的更新權限（欄位層級授權）：

```sql
CREATE USER 'portal'@'<Portal 連線來源>' IDENTIFIED BY '...';
GRANT SELECT, UPDATE (`auto_enabled`, `auto_start_time`, `auto_end_time`) ON `<db>`.`actor_RD-200HH1_botton` TO 'portal'@'<Portal 連線來源>';
```

## 日誌與維運

- 每個程式寫 `./log/<name>.log`（每月輪替、保留一年），也可用 `journalctl -u <service>` 查看。
- 感測器被拒絕的數值會出現在 `readSensor.log` 的 `rejected:`，經常出現代表接線或感測器有問題。
- `actor.py` 不會每分鐘覆蓋手動操作：只有狀態改變、或資料庫內該狀態的設定被改過時才會下風速 / 濕度指令。
  但電源按鈕設為關閉（`power=0`）時會強制關機。

## 已知限制

見 [CHANGELOG.md](CHANGELOG.md) 的「未處理」：Arduino 的 PMS 被動模式與 MH-Z19B 自動校正、電錶 OCR 的脆弱性、`api/` 尚未審查。

## 參考資料來源

- 空品 https://data.moenv.gov.tw/ 、氣象 https://opendata.cwa.gov.tw/
- [LibJciHitachi](https://github.com/qqaatw/LibJciHitachi)

## 氣象署測站設定

`AQDC-home.json` 的 `cwa.stations` 列出要抓的測站，每個測站寫入各自的資料表（`cwa_Home` 的主鍵只有 `DateTime`，不能混存多個測站）：

```json
"stations": [
    {"id": "CAD090", "label": "home", "table": "cwa_Home"},
    {"id": "C0D660", "label": "work", "table": "cwa_Work"}
]
```

新增測站的資料表前先建表：`CREATE TABLE cwa_work LIKE cwa_home;`（Linux 上請對應實際大小寫，並加進 `table_names`）。
測站代碼可從 `O-A0001-001`（自動氣象站，含氣壓）的回應中依座標找最近的；沒有 `stations` 時使用舊的 `cwa.params.StationId`。

## Grafana 儀表板

`grafana/dashboards/` 放以檔案管理的儀表板（目前有「AQDC 工作地點」，顯示 `cwa_work` 與家的對照）。載入方式：

```bash
sudo mkdir -p /var/lib/grafana/dashboards/aqdc && sudo cp grafana/dashboards/*.json /var/lib/grafana/dashboards/aqdc/   # Grafana 讀不到 /home，要複製過去
sudo cp grafana/provisioning/aqdc.yaml /etc/grafana/provisioning/dashboards/aqdc.yaml
sudo systemctl restart grafana-server
```

儀表板使用 uid `ce6f0117-7784-48fe-9533-b8fd61f4d132` 的 MySQL 資料來源；若你的資料來源 uid 不同，請在 JSON 中全部取代。
資料來源的位址請設成 `127.0.0.1:3306`（與 Grafana 在同一台 Pi 時）。因為是檔案管理（`allowUiUpdates: false`），要修改請改 JSON 檔再重新載入。
