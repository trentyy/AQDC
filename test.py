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

        self.isInHome()
        self.state = 0
        self.updateStates()


    def isInHome(self):
        sql = "SELECT `time`, `co2` FROM `home_mhz19b` ORDER BY `time` DESC LIMIT 1;"
        con=pymysql.connect(host=self.HOST, user=self.USER, passwd=self.PW, db=self.DB)
        with con.cursor() as cur:
            cur.execute(sql)
            result = cur.fetchall()
        con.close()
        co2 = result[0][1]
        if co2 > 700:
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
            False


    def showStatus(self):
        device_status = self.api.get_status()
        status = device_status[self.DEVICENAME].status
        print(status)


    def updateStates(self):
        data = ["state", "always_off", "in_home", "start_time", "end_time", "set_humid", "set_fan_speed", "description"]
        
        items =  ["SELECT `"]
        items.append("`,`".join(data))
        items.append("` from `actor_RD-200HH1` ORDER BY `state` DESC")
        print(items)
        sql = "".join(items)
        print(sql)

        # get states in raw data
        con=pymysql.connect(host=self.HOST, user=self.USER, passwd=self.PW, db=self.DB)
        with con.cursor() as cur:
            cur.execute(sql)
            result = cur.fetchall()
            print("result: ", result)
        con.close()

        # parse states data
        self.states = []
        for i in range(len(result)):
            self.states.append(
                {data[j]: result[i][j] for j in range(len(data))}
                )
        print("Current states:")
        print(self.states)

        # get time
        t = datetime.datetime.now()
        hour, minute = t.hour, t.minute
        t = datetime.timedelta(
            hours=t.hour,
            minutes=t.minute
            )
        
        # decide next state
        next_state = 0
        for i in range(len(self.states)):
            state = self.states[i]
            start_time, end_time = state["start_time"], state["end_time"]
            in_home = state["in_home"]
            print(self.isSpecifiedTime(t, start_time, end_time), (self.isInHome() == in_home))
            if self.isSpecifiedTime(t, start_time, end_time) and (self.isInHome() == in_home):
                next_state = state["state"]
                state_config = state
        print("next state: ", next_state)

        # update state setting
        if next_state != self.state:
            self.updateSetting(state_config)
            self.state = next_state


    def updateSetting(self, state_config):
        # data = ["state", "always_off", "in_home", "start_time", "end_time", "set_humid", "set_fan_speed", "description"]
        state_config
        print("set_status: ",
              self.api.set_status(
                status_name="FanSpeed",
                device_name=self.DEVICENAME,
                status_value=state_config["set_fan_speed"]
            )
        )
        print("set_status: ",
        self.api.set_status(
                status_name="HumiditySetting",
                device_name=self.DEVICENAME,
                status_value=state_config["set_humid"]
            )
        )
a = StateMachine()
a.showStatus()
