import traceback, time, json, datetime
import pymysql.cursors
# from loguru import logger

from JciHitachi.api import JciHitachiAWSAPI

class StateMachine:
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

        self.updateStates()

    def showStatus(self):
        device_status = self.api.get_status()
        status = device_status[self.DEVICENAME].status
        print(status)

    def updateStates(self):
        data = ["state", "always_off", "in_home", "start_time", "end_time", "set_humid", "set_fan_speed", "description"]
        sql =   "SELECT `" + \
                "`,`".join(data)+\
                "` from `actor_RD-200HH1` ORDER BY `state`"
        con=pymysql.connect(host=self.HOST, user=self.USER, passwd=self.PW, db=self.DB)
        with con.cursor() as cur:
            cur.execute(sql)
            result = cur.fetchall()
        con.close()
        self.states = []
        for i in range(len(result)):
            self.states.append({data[j]: result[i][j] for j in range(len(data))})
        print("Current states:")
        print(self.states)
a = StateMachine()
a.showStatus()
