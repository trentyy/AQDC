import traceback
import time
import json
import datetime
import pymysql.cursors
from datetime import timedelta
# from loguru import logger

from JciHitachi.api import JciHitachiAWSAPI

class StateMachine(object):
    def __init__(self) -> None:
        self.FANSPEED = {"silent" : 1, "low" : 2, "moderate" : 3, "high" : 4}

        with open("./setting/AQDC-home.json", 'r') as f:
            jdata = json.load(f)

        self.HOST = jdata['host']
        self.USER = jdata['user']
        self.PW = jdata['pw']
        self.DB = jdata['db']

        with open("./setting/AQDC-actor.json", 'r') as f:
            jdata = json.load(f)
        self.EMAIL = jdata['EMAIL']
        self.PASSWORD = jdata['PASSWORD']
        self.DEVICENAME = jdata['DEVICENAME']

        flag = False

        self.api = JciHitachiAWSAPI(self.EMAIL, self.PASSWORD, self.DEVICENAME)
        self.api.login()

        self.state = 0
        self.state_config = None
        self.updateConfig()
        self.updateState(isBooting=True)


    def isInHome(self):
        sql = "SELECT `time`, `co2` FROM `home_mhz19b` ORDER BY `time` DESC LIMIT 1;"
        con=pymysql.connect(host=self.HOST, user=self.USER, passwd=self.PW, db=self.DB)
        with con.cursor() as cur:
            cur.execute(sql)
            result = cur.fetchall()
        con.close()
        co2 = result[0][1]
        if co2 > 600:
            return True
        else:
            return False


    def isSpecifiedTime(
            self,
            curTime:timedelta,
            startTime: timedelta,
            endTime: timedelta,):
        if startTime < curTime < endTime:
            return True
        else:
            return False


    def updateConfig(self):
        device_status = self.api.get_status()
        self.device_status = device_status[self.DEVICENAME].status

        con = pymysql.connect(host=self.HOST, user=self.USER, passwd=self.PW, db=self.DB)
        sql = "SELECT `power`,`auto_turn_off` from `actor_RD-200HH1_botton`"
        with con.cursor() as cur:
            cur.execute(sql)
            result = cur.fetchall()
        self.power, self.auto_turn_off = result[0]
        sql = "SELECT `time`,`humidity` from `home_dht22` ORDER BY `time` DESC limit 1"
        with con.cursor() as cur:
            cur.execute(sql)
            result = cur.fetchall()
            self.humidity = result[0][1]
        con.close()

        data = ["state", "in_home", "start_time", "end_time",
                "humid_setting", "humid_lower_limit", "humid_upper_limit",
                "set_fan_speed", "description"]
        
        items =  ["SELECT `"]
        items.append("`,`".join(data))
        items.append("` from `actor_RD-200HH1` ORDER BY `state` DESC")
        sql = "".join(items)

        # get states in raw data
        con = pymysql.connect(host=self.HOST, user=self.USER, passwd=self.PW, db=self.DB)
        with con.cursor() as cur:
            cur.execute(sql)
            result = cur.fetchall()
        con.close()

        # parse states data
        self.states = []
        for i in range(len(result)):
            self.states.append(
                {data[j]: result[i][j] for j in range(len(data))}
                )


    def updateState(self, isBooting=False):
        # get time
        t = datetime.datetime.now()
        t = datetime.timedelta(
            hours=t.hour,
            minutes=t.minute
            )
        
        # decide next state
        next_state = 0
        for i in range(len(self.states)):
            state = self.states[i]
            start_time, end_time = state["start_time"], state["end_time"]
            
            if (self.isSpecifiedTime(t, start_time, end_time) and
                (self.isInHome() == state["in_home"])):
                next_state = state["state"]
                self.state_config = state
        print(f"current state:{self.state}, next state: {next_state}")
        print(f"self.state_config:{self.state_config}")

        # update state setting
        if (next_state != self.state) or isBooting:
            self.setDeviceSetting()
            self.state = next_state


    def setDeviceSetting(self):
        curFanSpeed = self.FANSPEED[self.device_status["FanSpeed"]]
        FanSpeedSetting = self.state_config["set_fan_speed"]

        if curFanSpeed != FanSpeedSetting:
            self.api.set_status(
                status_name="FanSpeed",
                device_name=self.DEVICENAME,
                status_value=FanSpeedSetting
            )

        curHumiditySetting = self.device_status["HumiditySetting"]
        HumiditySetting = self.state_config["humid_setting"]
        if curHumiditySetting != HumiditySetting:
            self.api.set_status(
                status_name="HumiditySetting",
                device_name=self.DEVICENAME,
                status_value=self.state_config["humid_setting"]
            )


    def checkAlwaysOff(self):
        if self.device_status["Switch"] == 'on' and not self.power:
            self.api.set_status(status_name="Switch", device_name=self.DEVICENAME, status_value=0)


    def autoTurnOffFunction(self):
        if not self.power:
            return

        if self.state_config["humid_lower_limit"] > self.humidity:
            if self.device_status['Switch'] == 'on':
                self.api.set_status(status_name="Switch", device_name=self.DEVICENAME, status_value=0)
        elif self.state_config["humid_upper_limit"] <= self.humidity:
            if self.device_status['Switch'] == 'off':
                self.api.set_status(status_name="Switch", device_name=self.DEVICENAME, status_value=1)


if __name__ == "__main__":
    dehumidifier = StateMachine()

    while(True):
        dehumidifier.updateConfig()
        dehumidifier.updateState()
        dehumidifier.checkAlwaysOff()
        dehumidifier.autoTurnOffFunction()
        time.sleep(60)
