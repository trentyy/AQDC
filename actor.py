"""AQDC actor：依在家狀態、時段與濕度控制日立除濕機 (RD-200HH1)。

邏輯（時段比對、在家判斷）在 actor_logic.py，這裡負責資料庫與雲端 API。
"""
import time
from datetime import datetime, timedelta

from loguru import logger
from JciHitachi.api import JciHitachiAWSAPI

from actor_logic import PresenceDetector, decide_switch, decision_slot, pick_state
from common import db_connect, load_home_setting, load_setting

logger.add("./log/actor.log", rotation="monthly", encoding="utf-8",
           enqueue=True, retention="1 year")

LOOP_SECONDS = 60
STATE_COLUMNS = ["state", "in_home", "start_time", "end_time",
                 "humid_setting", "humid_lower_limit", "humid_upper_limit",
                 "set_fan_speed", "description"]

# 以下參數都可以在 setting/AQDC-actor.json 內用同名鍵覆蓋，沒寫就用預設值
DEFAULTS = {
    "CO2_HOME_PPM": 600,        # 平均 CO2 高於此值 -> 在家
    "CO2_AWAY_PPM": 500,        # 平均 CO2 低於此值且持續 AWAY_MINUTES -> 外出
    "AWAY_MINUTES": 30,
    "CO2_WINDOW_MINUTES": 10,   # CO2 取最近幾分鐘的平均
    "SENSOR_STALE_MINUTES": 15,  # 感測器資料超過幾分鐘沒更新視為失效
    "MIN_SWITCH_SECONDS": 600,  # 濕度自動開/關機的最短間隔，保護壓縮機
    "COMMAND_COOLDOWN_SECONDS": 180,  # 同一道指令的重送間隔（雲端狀態更新有延遲）
    "AWAY_ONLY": False,         # True: 只在不在家時運作，在家一律關機
    "CONTROL_INTERVAL_MINUTES": 0,  # 開關判定間隔（分鐘），0 = 每輪（每分鐘）判定；整點起算對齊
}


class StateMachine(object):
    def __init__(self) -> None:
        logger.info("initiating...")
        self.FANSPEED = {"silent": 1, "low": 2, "moderate": 3, "high": 4}

        self.home = load_home_setting()
        actor = load_setting("AQDC-actor.json")
        self.EMAIL = actor['EMAIL']
        self.PASSWORD = actor['PASSWORD']
        self.DEVICENAME = actor['DEVICENAME']
        self.opt = {k: actor.get(k, v) for k, v in DEFAULTS.items()}

        self.presence = PresenceDetector(
            home_ppm=self.opt["CO2_HOME_PPM"],
            away_ppm=self.opt["CO2_AWAY_PPM"],
            away_minutes=self.opt["AWAY_MINUTES"],
            window_minutes=self.opt["CO2_WINDOW_MINUTES"],
            stale_minutes=self.opt["SENSOR_STALE_MINUTES"],
        )

        self.api = JciHitachiAWSAPI(self.EMAIL, self.PASSWORD, self.DEVICENAME)
        self.login()

        self.state = None           # 已成功套用的狀態編號
        self.state_config = None
        self.applied_sig = None     # 已成功套用的 (風速, 濕度設定)
        self.last_cmd = {}          # (名稱, 值) -> 上次送出時間
        self.last_switch_value = None
        self.last_switch_change = None
        self.last_slot = None       # 上一次完成開關判定的時段
        logger.info("...initiate finished")

    # ---------- 雲端 API ----------
    def login(self):
        """登入日立雲端；失敗時等待 60 秒、120 秒……最長 15 分鐘後重試，避免長時間頻繁打雲端 API。
        （設備離線或官方 App 開著時，函式庫會丟 RuntimeError "...refreshing ... support code"）"""
        delay = 60
        while True:
            try:
                self.api.login()
                logger.info("login ok")
                return
            except Exception as e:
                logger.error(f"login failed: {e!r}, retry in {delay}s")
                time.sleep(delay)
                delay = min(delay * 2, 900)

    def _send(self, name, value) -> bool:
        """送出一道設定指令；失敗不丟例外，回傳是否成功。
        同一道指令在冷卻時間內不重送（雲端狀態更新較慢，避免重複下指令）。"""
        key = (name, value)
        now = time.monotonic()
        last = self.last_cmd.get(key)
        if last is not None and now - last < self.opt["COMMAND_COOLDOWN_SECONDS"]:
            logger.debug(f"skip {name}={value}: sent {now - last:.0f}s ago")
            return False
        try:
            self.api.set_status(status_name=name, device_name=self.DEVICENAME,
                                status_value=value)
        except Exception as e:
            logger.error(f"set_status {name}={value} failed: {e!r}")
            return False
        self.last_cmd[key] = now
        if name == "Switch":
            self.last_switch_change = now
        logger.info(f"set_status: {name}={value}")
        return True

    # ---------- 讀取資料 ----------
    def refresh(self):
        """一次取得雲端狀態與資料庫的所有資料（單一連線）。"""
        status = self.api.get_status()
        self.device_status = status[self.DEVICENAME].status

        # 手動操作機器也算一次開關變化，納入最短間隔計算
        sw = self.device_status["Switch"]
        if self.last_switch_value is not None and sw != self.last_switch_value:
            self.last_switch_change = time.monotonic()
        self.last_switch_value = sw

        now = datetime.now()
        con = db_connect(self.home)
        try:
            with con.cursor() as cur:
                cur.execute("SELECT `power`,`auto_turn_off` FROM `actor_RD-200HH1_botton`")
                row = cur.fetchone()
                if row is None:
                    raise ValueError("table actor_RD-200HH1_botton is empty")
                self.power, self.auto_turn_off = row

                cur.execute("SELECT `time`,`humidity` FROM `home_dht22` ORDER BY `time` DESC LIMIT 1")
                row = cur.fetchone()
                stale = timedelta(minutes=self.opt["SENSOR_STALE_MINUTES"])
                if row is None or row[1] is None or now - row[0] > stale:
                    logger.warning(f"humidity data missing or stale: {row}")
                    self.humidity = None
                else:
                    self.humidity = row[1]

                cur.execute("SELECT `time`,`co2` FROM `home_mhz19b` ORDER BY `time` DESC LIMIT 30")
                self.co2_samples = list(cur.fetchall())

                cols = "`,`".join(STATE_COLUMNS)
                cur.execute(f"SELECT `{cols}` FROM `actor_RD-200HH1` ORDER BY `state` DESC")
                self.states = [dict(zip(STATE_COLUMNS, r)) for r in cur.fetchall()]
        finally:
            con.close()

    # ---------- 狀態與設定 ----------
    def updateState(self):
        now = datetime.now()
        t = timedelta(hours=now.hour, minutes=now.minute)

        in_home = self.presence.update(self.co2_samples, now)
        if self.presence.stale:
            logger.warning(f"co2 data missing or stale, keep in_home={in_home}")

        state = pick_state(self.states, t, in_home)
        next_state = state["state"]
        self.state_config = state
        sig = (state["set_fan_speed"], state["humid_setting"])

        # 狀態改變，或同一狀態的設定被改過（舊版只會在狀態改變時才套用）才下指令；
        # 其餘時間不干涉，所以手動調整機器不會被每分鐘覆蓋
        if next_state != self.state or sig != self.applied_sig:
            logger.info(f"state {self.state} -> {next_state} (in_home={in_home}), config={state}")
            if self.setDeviceSetting():
                self.state = next_state
                self.applied_sig = sig
            else:
                logger.warning("apply setting failed, will retry next loop")

    def setDeviceSetting(self) -> bool:
        ok = True
        want_fan = self.state_config["set_fan_speed"]
        cur_fan = self.FANSPEED.get(self.device_status["FanSpeed"])
        if cur_fan != want_fan:
            ok = self._send("FanSpeed", want_fan) and ok

        want_humid = self.state_config["humid_setting"]
        if self.device_status["HumiditySetting"] != want_humid:
            ok = self._send("HumiditySetting", want_humid) and ok
        return ok

    # ---------- 開關控制 ----------
    def _switch_interval_ok(self) -> bool:
        if self.last_switch_change is None:
            return True
        return time.monotonic() - self.last_switch_change >= self.opt["MIN_SWITCH_SECONDS"]

    def checkAlwaysOff(self):
        """電源按鈕設為關閉時，強制關機（不受最短間隔限制）。"""
        if self.device_status["Switch"] == 'on' and not self.power:
            logger.info("power button is off -> turn off")
            self._send("Switch", 0)

    def _decision_due(self):
        """是否到了新的判定時段（CONTROL_INTERVAL_MINUTES，預設每分鐘；Pi 上設為 30）。
        回傳 (是否該判定, 時段代號)。"""
        interval = self.opt["CONTROL_INTERVAL_MINUTES"]
        if interval <= 0:
            return True, None
        slot = decision_slot(datetime.now(), interval)
        return slot != self.last_slot, slot

    def autoTurnOffFunction(self) -> bool:
        """依在家狀態與濕度決定開關；回傳是否沒有失敗（失敗時不消耗判定時段，下一輪重試）。"""
        if not self.power:
            return True
        cfg = self.state_config
        is_on = self.device_status['Switch'] == 'on'
        in_home = self.presence.in_home

        action, reason = decide_switch(
            is_on, self.humidity, cfg["humid_lower_limit"], cfg["humid_upper_limit"],
            in_home, away_only=self.opt["AWAY_ONLY"], auto_turn_off=self.auto_turn_off)
        if action is None:
            return True
        # 依濕度開關受最短間隔限制；在家強制關機與 auto_turn_off=0 開機不受限
        if reason == "humidity" and not self._switch_interval_ok():
            logger.debug("switch interval too short, skip")
            return True

        if not self._send("Switch", action):
            return False
        if reason == "home":
            logger.info("someone is home (AWAY_ONLY) -> turn off")
        elif reason == "always_on":
            logger.info("auto_turn_off is 0 -> turn on")
        elif action == 1:
            logger.info(f"humidity {self.humidity} > upper limit {cfg['humid_upper_limit']} -> turn on")
        else:
            logger.info(f"humidity {self.humidity} <= lower limit {cfg['humid_lower_limit']} -> turn off")
        return True

    def run_cycle(self):
        self.refresh()
        self.updateState()
        self.checkAlwaysOff()           # 電源按鈕強制關機：每輪都檢查
        due, slot = self._decision_due()
        if due and self.autoTurnOffFunction():
            self.last_slot = slot


if __name__ == "__main__":
    dehumidifier = StateMachine()
    failures = 0
    while True:
        try:
            dehumidifier.run_cycle()
            failures = 0
        except Exception:
            failures += 1
            logger.exception(f"cycle failed ({failures} in a row)")
            # 連續失敗時重新登入（token 過期是常見原因），之後每 5 次再試一次
            if failures % 5 == 3:
                dehumidifier.login()
        time.sleep(LOOP_SECONDS)
