#!/usr/bin/python3

import traceback, time, json
import serial
import pymysql.cursors
from loguru import logger

from datetime import datetime
from picamera import PiCamera
from time import sleep
import RPi.GPIO as GPIO

import os
from PIL import Image
import numpy as np
import pytesseract
import cv2
import matplotlib.pyplot as plt

DEBUG = True

PWM_FREQ = 50
vServoPIN = 12
hServoPIN = 18

# mapping input angle to reasonable number
def ang2dc(angle: int):
    xmin, xmax = -90, 90 # degree
    ymin, ymax = 0.5, 2.5 # ms

    if angle < xmin:
        angle = -90
    elif angle > xmax:
        angle = 90
    y = (angle - xmin) * (ymax - ymin) / (xmax - xmin) + ymin
    return y * 5 # y/20(ms)*100

def capture_pic(move=True):
    filename = ""
    try:
        if move:
            GPIO.setmode(GPIO.BCM)
            GPIO.setup(vServoPIN, GPIO.OUT)
            GPIO.setup(hServoPIN, GPIO.OUT)
            vPWM = GPIO.PWM(vServoPIN, PWM_FREQ)
            hPWM = GPIO.PWM(hServoPIN, PWM_FREQ)
            vdc = ang2dc(0)
            hdc = ang2dc(-40)
            print(vdc, hdc)
            vPWM.start(vdc)
            hPWM.start(hdc)
            sleep(0.5)
            vPWM.stop()
            hPWM.stop()

        camera = PiCamera()
        camera.iso = 500
        camera.vflip = True
        camera.hflip = True
        camera.start_preview()
        sleep(1)
        curtime = datetime.now().isoformat()
        filename = f'./pic/{curtime}.jpg'
        camera.capture(filename)
        camera.stop_preview()
        
    except Exception as e:
        raise e
    finally:
        camera.close()
        if move:
            GPIO.cleanup()
    return filename

def ssRead(src, x, y, w, h, p=3):
    """
    Read seven segment number by cv2.findContours output
    """
    # gen matrix
    ss_status = np.zeros(7, dtype=bool)
    ss_detect_area_x = (
        (x+int((w-p)/2), x+int((w+p)/2)),   # seg 0
        (x+int(w*3/4), x+w),                # seg 1
        (x+int(w*3/4), x+w),                # seg 2
        (x+int((w-p)/2), x+int((w+p)/2)),   # seg 3
        (x, x+int(w/4)),                    # seg 4
        (x, x+int(w/4)),                    # seg 5
        (x+int((w-p)/2), x+int((w+p)/2)),   # seg 6
    )
    ss_detect_area_y = (
        (y, y+int(h/8)),                        # seg 0
        (y+int((h/2-p)/2), y+int((h/2+p)/2)),   # seg 1
        (y+int(h*3/4-p/2), y+int(h*3/4+p/2)),   # seg 2
        (y+int(h*7/8), y+h),                    # seg 3
        (y+int(h*3/4-p/2), y+int(h*3/4+p/2)),   # seg 4
        (y+int(h*1/4-p/2), y+int(h*1/4+p/2)),   # seg 5
        (y+int(h*6/16), y+int(h*10/16)),         # seg 6
    )
    ss_decimal = {
        "0": np.array([1, 1, 1, 1, 1, 1, 0], dtype=bool),
        "1": np.array([0, 1, 1, 0, 0, 0, 0], dtype=bool),
        "2": np.array([1, 1, 0, 1, 1, 0, 1], dtype=bool),
        "3": np.array([1, 1, 1, 1, 0, 0, 1], dtype=bool),
        "4": np.array([0, 1, 1, 0, 0, 1, 1], dtype=bool),
        "5": np.array([1, 0, 1, 1, 0, 1, 1], dtype=bool),
        "6": np.array([1, 0, 1, 1, 1, 1, 1], dtype=bool),
        "7": np.array([1, 1, 1, 0, 0, 0, 0], dtype=bool),
        "8": np.array([1, 1, 1, 1, 1, 1, 1], dtype=bool),
        "9": np.array([1, 1, 1, 1, 0, 1, 1], dtype=bool),
    }    
    ss_hex = {
        "a": np.array([1, 1, 1, 0, 1, 1, 1], dtype=bool),
        "b": np.array([0, 0, 1, 1, 1, 1, 1], dtype=bool),
        "c": np.array([1, 0, 0, 1, 1, 1, 0], dtype=bool),
        "d": np.array([0, 1, 1, 1, 1, 0, 1], dtype=bool),
        "e": np.array([1, 0, 0, 1, 1, 1, 1], dtype=bool),
        "f": np.array([1, 0, 0, 0, 1, 1, 1], dtype=bool),
    }
    # merge ss_dicimal data into ss_hex
    ss_hex.update(ss_decimal)

    # save every mask to check position
    sum_mask = np.zeros(src.shape, dtype=bool)
    # check detect area from seg 0 to seg 6
    for seg in range(7):
        # mask is the detect area in array
        mask = np.zeros(src.shape, dtype=bool)
        for i in range(ss_detect_area_x[seg][0], ss_detect_area_x[seg][1]):
            for j in range(ss_detect_area_y[seg][0], ss_detect_area_y[seg][1]):
                mask[j][i] = True
        # check if it satisfied the threshold
        ratio = (ss_detect_area_x[seg][1] - ss_detect_area_x[seg][0]) * \
                (ss_detect_area_y[seg][1] - ss_detect_area_y[seg][0]) / 2
        if np.sum(np.array(src * mask, dtype=bool)) > ratio:
            ss_status[seg] = True
        # save mask for debugging
        sum_mask += mask

    # deal with 1 situation(width of contour is smaller)
    # if it is 1, the contour result will be a narrow rectangle
    # so I filter it out by w/h ratio and light/dark ratio
    if w / h < 0.38 and w / h > 0.3:
        mask = np.zeros(src.shape, dtype=bool)
        for i in range(x, x+w):
            for j in range(y, y+h):
                mask[j][i] = True
        ratio = 0.9
        if np.sum(np.array(src * mask, dtype=bool)) > ratio:
            return 1, sum_mask
        
    # deal with normal situation
    if DEBUG: print(f"[debug] ss_status:{ss_status}")
    for k, v in ss_decimal.items():
        if (ss_status == v).all():
            return int(k), sum_mask
    else:
        return -1, sum_mask

def preProcess(filename = './test.jpg', alpha = 3, beta = 1):
    
    img = Image.open(filename)

    origin_array = np.asarray(img)[280:580, 700:1000]

    convertScaleAbs_img =  cv2.convertScaleAbs(origin_array, alpha=alpha, beta=beta)

    gray_img = cv2.cvtColor(convertScaleAbs_img, cv2.COLOR_RGB2GRAY)

    kernel = np.ones((5, 5), np.uint8)
    binary = cv2.dilate(gray_img, kernel, iterations=2)
    binary = cv2.erode(binary, kernel, iterations=1)

    ret, binary = cv2.threshold(binary, 240, 255, cv2.THRESH_BINARY)
    if DEBUG:
        demo_img = origin_array.copy()
        plt.subplot(121)
        plt.imshow(binary, cmap="gray")
        
        contour, hierarchy = cv2.findContours(binary, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        for cnt in contour:
            x, y, w, h = cv2.boundingRect(cnt)
            cv2.rectangle(demo_img, (x, y), (x+w, y+h), (0, 255, 0), 5)
            num, detect_area = ssRead(binary, x, y, w, h)
            for i in range(detect_area.shape[0]):
                for j in range(detect_area.shape[1]):
                    if detect_area[i][j]:
                        demo_img[i][j][0] = 0
                        demo_img[i][j][1] = 0
                        demo_img[i][j][2] = 200
        plt.subplot(122)
        plt.imshow(demo_img)
        plt.savefig("".join(filename.split(".jpg")[:-1])+"after_preProcess.jpg", dpi=300)

    return binary

def readVA(binary):
    contour, hierarchy = cv2.findContours(binary, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    result = []
    for cnt in contour:
        x, y, w, h = cv2.boundingRect(cnt)
        num, detect_area = ssRead(binary, x, y, w, h)
        result.append((num, x, y))
    
    result = sorted(result, key=lambda x: x[2])
    V = result[:3]
    A = result[3:]
    try:
        V = sorted(V, key=lambda x: x[1])
        A = sorted(A, key=lambda x: x[1])
        V = "".join([str(x[0]) for x in V])
        A = "".join([str(x[0]) for x in A])
        V, A = int(V), int(A)/10
    except ValueError as e:
        raise e

    return V, A

# log file name
trace = logger.add("./log/readElectricity.log", rotation="monthly", encoding="utf-8", enqueue=True, retention="1 year")


with open("AQDC-home.json", 'r') as f:
    jdata = json.load(f)

HOST = jdata['host']
USER = jdata['user']
PW = jdata['pw']
DB = jdata['db']

con=pymysql.connect(host=HOST, user=USER, passwd=PW, db=DB)

counter = 0

if __name__ == "__main__":
    while True:
        try:
            filename = capture_pic(move=False)
            img = preProcess(filename, alpha=3, beta=1)
            V, A = readVA(img)
            if A < 7:
                os.remove(filename)
                os.remove("".join(filename.split(".jpg")[:-1])+"after_preProcess.jpg")

            # prepare date to store
            curtime = time.strftime("%Y-%m-%d %H:%M:%S", time.gmtime())
            data = {"time": curtime,
                    "Voltage": V,
                    "Ampere": A}
            sql = "INSERT INTO `home_electricity`(`time`,`Voltage`,`Ampere`)"
            sql += f" VALUES ('{curtime}',{V},{A})"

            con.ping(reconnect=True)

            with con.cursor() as cur:
                isNone = False
                for key, value in data.items():
                    if value == None:   isNone = True
                if not isNone:  cur.execute(sql)
            con.commit()
            logger.success(sql)
            sleep(60)
        except ValueError as e:
            logger.debug(e)
        except Exception as e:
            raise e
