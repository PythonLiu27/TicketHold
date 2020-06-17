# coding:utf-8
# !/usr/bin/python
import logging
import time
import json
import traceback

import pymysql
import redis
import requests
from concurrent.futures import ThreadPoolExecutor
from pyquery import PyQuery as pq
from aes_tool import aes_encode

# {'depCity': 'PAR', 'arrCity': 'CAN', 'fromDate': '2020-05-26', 'retDate': '', 'adult': 1, 'child': 0,
#  'flight_nums': 'CZ348'}
# params['passengers'] = [{'name': 'HAN/YUEHENG', 'sex': 'M', 'birthday': '1997-07-11',
#                          'type': '0', 'card_num': 'EE9665104', 'card_type': 'p',
#                          'expire_date': '2029-01-09', 'nation': 'CHN', 'age': '23',
#                          'card_nation': 'CHN'}]
# params['contact'] = {'name': 'HAN/YUEHENG', 'phone': '15801223515', 'email': '851303996@qq.com'}
from captch_tool import Chaojiying_Client
from hold_serveice import HOST
from utils.config_log import config_log
from utils.jixintong_sms import post_sms


class XiamenAirBook(object):

    def __init__(self):
        self.session = requests.session()
        self.carrier = 'MF'
        self.db = pymysql.connect(
            host=HOST,
            port=3306,
            user='root',
            password='wogannimei123',
            db='liuhanchao',
            charset='utf8',
            autocommit=True,
            cursorclass=pymysql.cursors.DictCursor
        )
        self.login_status = False

    def mainjob(self, book_info):
        self.book_id = book_info['id']
        self.set_log(self.book_id, u'刷舱程序启动')
        # 起飞日前-出生日期 = 年龄 （>12 周岁的算成年）
        pnr_info = self.book_robot(book_info)
        logging.info('task result: %s', pnr_info)
        return pnr_info

    def set_log(self, line_id, text):
        """
        添加刷舱日志
        :param line_id:
        :param text:
        :return:
        """
        sql = 'insert into tools_crush_cabin_log (line_id,remarks,create_time) values (%s, "%s", %s)' % (
        line_id, text, int(time.time()))
        with self.db.cursor() as cur:
            cur.execute(sql)

    def captch_code(self, captch_res):
        r_client = Chaojiying_Client()
        # code = r_client.PostPic(captch_res, '1902')["pic_str"]
        # 使用资源包
        code = r_client.PostPic(captch_res, '8001')["pic_str"]
        return code

    # 起飞时的周岁年龄
    def age_to_dep(self, birth_date, dep_date):
        birth_date_year = int(birth_date[:4])
        birth_date_mon = int(birth_date[5:7])
        birth_date_day = int(birth_date[8:])
        dep_date_year = int(dep_date[:4])
        dep_date_mon = int(dep_date[5:7])
        dep_date_day = int(dep_date[8:])
        year_diff = dep_date_year - birth_date_year
        if dep_date_mon > birth_date_mon:
            return year_diff
        elif dep_date_mon < birth_date_mon:
            return year_diff - 1
        else:
            if dep_date_day > birth_date_day:
                return year_diff
            else:
                return year_diff - 1

    def login(self, account, password):
        # home page
        home_url = "https://www.xiamenair.com/zh-cn/"
        home_headers = {
            "Host": "www.xiamenair.com",
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/81.0.4044.138 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.9",
            "Sec-Fetch-Site": "none",
            "Sec-Fetch-Mode": "navigate",
            "Sec-Fetch-Dest": "document",
            "Accept-Encoding": "gzip, deflate, br",
            "Accept-Language": "zh-CN,zh;q=0.9",
        }
        self.session.headers.update(home_headers)
        try:
            self.session.get(url=home_url, verify=False)
        except:
            return False, "home page timeout"
        # login page
        login_page_url = "https://uia.xiamenair.com/external/api/v1/oauth2/authorize?scope=user&response_type=code&client_id=PCWEB&lang=zh_cn&redirect_uri=https://www.xiamenair.com/api/users/ssocallback"
        login_page_headers = {
            "Host": "uia.xiamenair.com",
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/81.0.4044.138 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.9",
            "Sec-Fetch-Site": "same-site",
            "Sec-Fetch-Mode": "navigate",
            "Sec-Fetch-User": "?1",
            "Sec-Fetch-Dest": "document",
            "Referer": "https://www.xiamenair.com/zh-cn/",
            "Accept-Encoding": "gzip, deflate, br",
            "Accept-Language": "zh-CN,zh;q=0.9",
            # "Cookie": "gr_user_id=12d5a80f-0d71-4acc-a200-5208d2526a3d; b014f44b281415f1_gr_session_id=5cdcd298-4a6c-4fea-8d4a-06bc09e8361b; c=LVrKqvMo-1589071566345-cdc00ebfc78f6-748503790; grwng_uid=4110118d-4c99-4b12-a901-b0514591216b; b014f44b281415f1_gr_session_id_5cdcd298-4a6c-4fea-8d4a-06bc09e8361b=true; smidV2=202005100846067d20f9bc82445f2aa19b9c1703e29af4007ce4507bb06f280; _ga=GA1.2.2070157679.1589071567; _gid=GA1.2.194327845.1589071567; _gat_UA-96517318-2=1; _xid=2YSsIJt1R6SFmlqFAf4mJfryHWNofBGD7fJ6yQ4LkFiN32%2FDWmUhCmkSxYJ301lEk8R7p2xegBIzNpKRVe5gow%3D%3D; _fmdata=KFXr4CdC0jRi0TVr5efT8TJdg55spxWcwzKYTCTGq0iaAvXH1IhaSBcVfq8e0i96RHf45dG1EOa9LfXVmOvhFL8h9WWkN97mBogaF3Wv4CU%3D",
        }
        self.session.headers.update(login_page_headers)
        try:
            login_page_res = self.session.get(url=login_page_url, verify=False).content
        except:
            return False, "login page time"
        login_pagetoken = pq(login_page_res)('input[name="pageToken"]').attr("value")
        # login action
        login_url = "https://uia.xiamenair.com/external/api/v1/oauth2/verify"
        account_enc = aes_encode("xiamenair1234567", account)
        password_enc = aes_encode("xiamenair1234567", password)
        captc_url = "https://uia.xiamenair.com/external/api/v1/oauth2/captcha"
        captc_res = self.session.get(url=captc_url, verify=False).content
        captc_code = self.captch_code(captc_res)
        login_data = {
            "pageToken": login_pagetoken,
            "account": account_enc,
            "password": password_enc,
            "code": captc_code,  # todo
            "type": "1",
            "clientId": "PCWEB"
        }
        login_headers = {
            "Host": "uia.xiamenair.com",
            "Connection": "keep-alive",
            "Accept": "application/json, text/javascript, */*; q=0.01",
            "X-Requested-With": "XMLHttpRequest",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/81.0.4044.138 Safari/537.36",
            "Content-Type": "application/json",
            "Origin": "https://uia.xiamenair.com",
            "Sec-Fetch-Site": "same-origin",
            "Sec-Fetch-Mode": "cors",
            "Sec-Fetch-Dest": "empty",
            "Referer": "https://uia.xiamenair.com/external/api/v1/oauth2/authorize?scope=user&response_type=code&client_id=PCWEB&lang=zh_cn&redirect_uri=https://www.xiamenair.com/api/users/ssocallback",
            "Accept-Encoding": "gzip, deflate, br",
            "Accept-Language": "zh-CN,zh;q=0.9",
            # "Cookie": "tongdunyunBlockBox=eyJ2IjoiWGU5UTVETEpjOXJweVRGSExFN1dmS0R2a2l2MDRlbE5iNU5TVGhHQkFqTU5kbExoMkM0cHl6QzZmTjF3RWhhYiIsIm9zIjoid2ViIiwiaXQiOjI5NiwidCI6ImppaXRxTzJQMVZ4SXh4WG9JN1FjOW1OSGtwWnZFM1BTR01SdFpmUGM5b0pjSTljR0pRbUg3TkFJNHRGYWhzTTlqT1QyQy9yNVRna28vVDl5SjVzNkR3PT0ifQ==; shumeiBlockBox=WHJMrwNw1k/EZRD0tRmsjWMzADiX45soDF//ofBzStEgfdfXZ27HGxZztzjK8dI+EZaHyaGT8epZs3hkDyywFG5Qc0MAhbgwyB78mKzLVYtbjBJTcW6cExZSD3EmPbcN1b2GXgZ5AQVI9z8yFKt4xhnAn/hpkAQT0r2AtoEC6BxxkhoMiJ81hY1D9dKCqKxMR7jOJQetZtpRiNVCcw5ywKEKf9slCBICHLk3TZsmXJ6yBFPtOb87IE02lstx30LSbR/t9WW/jIrAFA4nOgFtsiIsUjFtjkIWK1487582755342; SESSION=191ddea5-1d9e-4020-b182-828e830ee4c0; gr_user_id=12d5a80f-0d71-4acc-a200-5208d2526a3d; b014f44b281415f1_gr_session_id=5cdcd298-4a6c-4fea-8d4a-06bc09e8361b; c=LVrKqvMo-1589071566345-cdc00ebfc78f6-748503790; grwng_uid=4110118d-4c99-4b12-a901-b0514591216b; b014f44b281415f1_gr_session_id_5cdcd298-4a6c-4fea-8d4a-06bc09e8361b=true; smidV2=202005100846067d20f9bc82445f2aa19b9c1703e29af4007ce4507bb06f280; _ga=GA1.2.2070157679.1589071567; _gid=GA1.2.194327845.1589071567; org.springframework.web.servlet.i18n.CookieLocaleResolver.LOCALE=zh_CN; BIGipServersvrpool_uia_9080=3607102474.30755.0000; _xid=c0cTEgXK6rx51EscpVbz2RRqmZj9CL9pOdTaHQz4UAw22uQGZIzWI%2Fx4Ds1ilPtngNJAqJZfhCq5E%2Bd0mk9rXQ%3D%3D; _fmdata=KFXr4CdC0jRi0TVr5efT8TJdg55spxWcwzKYTCTGq0iaAvXH1IhaSBcVfq8e0i96RHf45dG1EOa9LfXVmOvhFDSYAUDa3WC4U4XA2zRIiWA%3D",
        }
        self.session.headers.update(login_headers)
        try:
            login_res = self.session.post(url=login_url, json=login_data, verify=False).json()
        except:
            return False, "login timeout"
        login_res_msg = login_res.get("msg", "")
        if login_res_msg != "SUCCESS":
            return False, login_res_msg
        redirect_url = login_res.get("result", {}).get("redirectUrl", "")
        return True, redirect_url

    def search(self, search_data):
        search_url = "https://www.xiamenair.com/api/offers"
        search_headers = {
            "Host": "www.xiamenair.com",
            "Connection": "keep-alive",
            "Pragma": "no-cache",
            "Accept": "application/json, text/plain, */*",
            "Cache-Control": "no-cache",
            "Accept-Language": "zh-cn",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/81.0.4044.138 Safari/537.36",
            "Content-Type": "application/json;charset=UTF-8",
            "Origin": "https://www.xiamenair.com",
            "Sec-Fetch-Site": "same-origin",
            "Sec-Fetch-Mode": "cors",
            "Sec-Fetch-Dest": "empty",
            # "Referer": "https://www.xiamenair.com/zh-cn/nticket.html?tripType=OW&orgCodeArr%5B0%5D=JFK&dstCodeArr%5B0%5D=TSN&orgDateArr%5B0%5D=2020-07-06&dstDate=&isInter=true&adtNum=1&chdNum=0&JFCabinFirst=false&acntCd=",
            "Referer": "https://www.xiamenair.com/zh-cn/nticket.html",
            "Accept-Encoding": "gzip, deflate, br",
            # "Cookie": "BIGipServersvrpool_brandnew_8080=1979712522.36895.0000; sna=zh-cn; JSESSIONID=9c05283e-2746-4c8a-8c49-4d96c38466a4; BIGipServersvrpool_brandnew_9080=486540298.30755.0000; gr_user_id=12d5a80f-0d71-4acc-a200-5208d2526a3d; b014f44b281415f1_gr_session_id=5cdcd298-4a6c-4fea-8d4a-06bc09e8361b; c=LVrKqvMo-1589071566345-cdc00ebfc78f6-748503790; grwng_uid=4110118d-4c99-4b12-a901-b0514591216b; b014f44b281415f1_gr_session_id_5cdcd298-4a6c-4fea-8d4a-06bc09e8361b=true; smidV2=202005100846067d20f9bc82445f2aa19b9c1703e29af4007ce4507bb06f280; _ga=GA1.2.2070157679.1589071567; _gid=GA1.2.194327845.1589071567; lastPage=https%3A%2F%2Fwww.xiamenair.com%2Fzh-cn%2F; UIA_CHECK=15032288072; _fmdata=KFXr4CdC0jRi0TVr5efT8TJdg55spxWcwzKYTCTGq0iaAvXH1IhaSBcVfq8e0i96RHf45dG1EOa9LfXVmOvhFKw1quBq1tHxcOObijFvS10%3D; _xid=lLY7F4u8qzcVvHwaEgCw10K%2BRbtRpKvv4lqITfU2B1JSU6oFxdolXkQ%2BQJ0VBObKdcA79tduhIR9Hc6ykypjRA%3D%3D; atk=019c85a0-a2d9-4272-92dc-745c68841b38; userName=%E7%8B%84%E7%9F%BF; _pk_ses.21.b060=*; _gat_UA-96517318-2=1; _pk_id.21.b060=46e6a476cfb33852.1589071743.1.1589071789.1589071743.",
        }
        self.session.headers.update(search_headers)
        try:
            search_res = self.session.post(url=search_url, json=search_data, verify=False).json()
        except:
            return False, "search timeout"
        return True, search_res

    def verify(self, select_data):
        select_url = "https://www.xiamenair.com/api/caches/selected-offer/post"
        select_headers = {
            "Host": "www.xiamenair.com",
            "Connection": "keep-alive",
            "Pragma": "no-cache",
            "Accept": "application/json, text/plain, */*",
            "Cache-Control": "no-cache",
            "Accept-Language": "zh-cn",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/81.0.4044.138 Safari/537.36",
            "Content-Type": "application/json;charset=UTF-8",
            "Origin": "https://www.xiamenair.com",
            "Sec-Fetch-Site": "same-origin",
            "Sec-Fetch-Mode": "cors",
            "Sec-Fetch-Dest": "empty",
            "Referer": "https://www.xiamenair.com/zh-cn/nticket.html",
            "Accept-Encoding": "gzip, deflate, br",
            # "Cookie": "BIGipServersvrpool_brandnew_8080=1979712522.36895.0000; sna=zh-cn; JSESSIONID=9c05283e-2746-4c8a-8c49-4d96c38466a4; BIGipServersvrpool_brandnew_9080=486540298.30755.0000; gr_user_id=12d5a80f-0d71-4acc-a200-5208d2526a3d; c=LVrKqvMo-1589071566345-cdc00ebfc78f6-748503790; grwng_uid=4110118d-4c99-4b12-a901-b0514591216b; smidV2=202005100846067d20f9bc82445f2aa19b9c1703e29af4007ce4507bb06f280; _ga=GA1.2.2070157679.1589071567; _gid=GA1.2.194327845.1589071567; lastPage=https%3A%2F%2Fwww.xiamenair.com%2Fzh-cn%2F; UIA_CHECK=15032288072; _fmdata=KFXr4CdC0jRi0TVr5efT8TJdg55spxWcwzKYTCTGq0iaAvXH1IhaSBcVfq8e0i96RHf45dG1EOa9LfXVmOvhFKw1quBq1tHxcOObijFvS10%3D; _xid=lLY7F4u8qzcVvHwaEgCw10K%2BRbtRpKvv4lqITfU2B1JSU6oFxdolXkQ%2BQJ0VBObKdcA79tduhIR9Hc6ykypjRA%3D%3D; atk=019c85a0-a2d9-4272-92dc-745c68841b38; userName=%E7%8B%84%E7%9F%BF; b014f44b281415f1_gr_session_id=e6184fad-f951-42af-a9e5-d26cd8ef0005; _pk_ses.21.b060=*; b014f44b281415f1_gr_session_id_e6184fad-f951-42af-a9e5-d26cd8ef0005=true; _pk_id.21.b060=46e6a476cfb33852.1589071743.3.1589078115.1589075662.; _gat_UA-96517318-2=1",
        }
        self.session.headers.update(select_headers)
        try:
            select_res = self.session.post(url=select_url, json=select_data, verify=False)
        except:
            return False, "select post timeout"
        select_res_code = select_res.status_code
        if select_res_code != 201:
            return False, "select post response code %s" % select_res_code
        # select get
        select_get_url = "https://www.xiamenair.com/api/caches/selected-offer/get"
        try:
            select_get_res = self.session.get(url=select_get_url, verify=False).json()
        except:
            return False, "select get timeout"
        return True, select_get_res

    def order(self, order_param_data):
        order_param_url = "https://www.xiamenair.com/api/caches/order-param"
        order_param_headers = {
            "Host": "www.xiamenair.com",
            "Connection": "keep-alive",
            "Pragma": "no-cache",
            "Accept": "application/json, text/plain, */*",
            "Cache-Control": "no-cache",
            "Accept-Language": "zh-cn",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/81.0.4044.138 Safari/537.36",
            "Content-Type": "application/json;charset=UTF-8",
            "Origin": "https://www.xiamenair.com",
            "Sec-Fetch-Site": "same-origin",
            "Sec-Fetch-Mode": "cors",
            "Sec-Fetch-Dest": "empty",
            "Referer": "https://www.xiamenair.com/zh-cn/norder.html?tripType=OW&orgCodeArr%5B0%5D=JFK&dstCodeArr%5B0%5D=TSN&orgDateArr%5B0%5D=2020-07-06&dstDate=&isInter=true&adtNum=1&chdNum=0&JFCabinFirst=false&jcgm=false&acntCd=",
            "Accept-Encoding": "gzip, deflate, br",
            # "Cookie": "sna=zh-cn; BIGipServersvrpool_brandnew_8080=1962935306.36895.0000; JSESSIONID=d898e100-6989-42d3-915f-881f6e1bf063; BIGipServersvrpool_brandnew_9080=486540298.30755.0000; gr_user_id=6c750f90-9f1b-4634-89e0-d17dc202f0b5; c=6AYlmy8A-1589086778492-35e8327a66e3b2127871337; grwng_uid=c7737ac0-c7db-4d9a-82f9-e0635ae39bef; _ga=GA1.2.1456436305.1589086779; _gid=GA1.2.1901900374.1589086779; smidV2=2020051012593895db000fe898f650c9fa99cc22997b63003f4a9022fc30a30; _xid=aqZ0%2FrqU1KmWQlyFrHQk8hPPmfNNFXsIeKne%2Bk3pcPTJZZTky70Ti%2BIlfXKJ08IorqCUoGzfGYf9XTZnEVnXrg%3D%3D; _fmdata=pNVw0TaXZYhsC%2BEYSyrfmd002%2Fqdmgy2XLaHtPdPiDtTwmA%2Bm%2B5I6yWIfCb%2F2lVTpjbs462NxvjGpIhNIsKHUdU5t6gEYmZ8XtqsBg8vLvA%3D; UIA_CHECK=15032288072; b014f44b281415f1_gr_session_id=de0114bd-176e-45d8-bbf5-e2113d4541cd; b014f44b281415f1_gr_session_id_de0114bd-176e-45d8-bbf5-e2113d4541cd=true; atk=30cd1288-c101-4092-ad04-c14654830d55; userName=%E7%8B%84%E7%9F%BF; _pk_ses.21.b060=*; _pk_id.21.b060=02ee8220b45694ee.1589089195.1.1589089807.1589089195.",
        }
        self.session.headers.update(order_param_headers)
        try:
            order_param_res = self.session.post(url=order_param_url, json=order_param_data, verify=False)
        except:
            return False, "order post timeout"
        order_res_code = order_param_res.status_code
        if order_res_code != 201:
            return False, "order post response code %s" % order_res_code
        # order param get
        order_param_get_url = "https://www.xiamenair.com/api/caches/order-param"
        try:
            order_param_get_res = self.session.get(url=order_param_get_url, verify=False).json()
        except:
            return False, "order get timeout"
        return True, order_param_get_res

    def save(self):
        save_url = "https://www.xiamenair.com/api/iorder/save"
        save_data = {}
        save_headers = {
            "Host": "www.xiamenair.com",
            "Connection": "keep-alive",
            "Pragma": "no-cache",
            "Accept": "application/json, text/plain, */*",
            "Cache-Control": "no-cache",
            "Accept-Language": "zh-cn",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/81.0.4044.138 Safari/537.36",
            "Content-Type": "application/json;charset=UTF-8",
            "Origin": "https://www.xiamenair.com",
            "Sec-Fetch-Site": "same-origin",
            "Sec-Fetch-Mode": "cors",
            "Sec-Fetch-Dest": "empty",
            "Referer": "https://www.xiamenair.com/zh-cn/norder-confirm.html?tripType=OW&orgCodeArr%5B0%5D=JFK&dstCodeArr%5B0%5D=TSN&orgDateArr%5B0%5D=2020-07-06&dstDate=&isInter=true&adtNum=1&chdNum=0&JFCabinFirst=false&jcgm=false&acntCd=",
            "Accept-Encoding": "gzip, deflate, br",
            # "Cookie": "sna=zh-cn; BIGipServersvrpool_brandnew_8080=1962935306.36895.0000; JSESSIONID=d898e100-6989-42d3-915f-881f6e1bf063; BIGipServersvrpool_brandnew_9080=486540298.30755.0000; gr_user_id=6c750f90-9f1b-4634-89e0-d17dc202f0b5; c=6AYlmy8A-1589086778492-35e8327a66e3b2127871337; grwng_uid=c7737ac0-c7db-4d9a-82f9-e0635ae39bef; _ga=GA1.2.1456436305.1589086779; _gid=GA1.2.1901900374.1589086779; smidV2=2020051012593895db000fe898f650c9fa99cc22997b63003f4a9022fc30a30; _xid=aqZ0%2FrqU1KmWQlyFrHQk8hPPmfNNFXsIeKne%2Bk3pcPTJZZTky70Ti%2BIlfXKJ08IorqCUoGzfGYf9XTZnEVnXrg%3D%3D; _fmdata=pNVw0TaXZYhsC%2BEYSyrfmd002%2Fqdmgy2XLaHtPdPiDtTwmA%2Bm%2B5I6yWIfCb%2F2lVTpjbs462NxvjGpIhNIsKHUdU5t6gEYmZ8XtqsBg8vLvA%3D; UIA_CHECK=15032288072; b014f44b281415f1_gr_session_id=de0114bd-176e-45d8-bbf5-e2113d4541cd; b014f44b281415f1_gr_session_id_de0114bd-176e-45d8-bbf5-e2113d4541cd=true; atk=30cd1288-c101-4092-ad04-c14654830d55; userName=%E7%8B%84%E7%9F%BF; _pk_ses.21.b060=*; _gat_UA-96517318-2=1; _pk_id.21.b060=02ee8220b45694ee.1589089195.1.1589089959.1589089195.",
        }
        self.session.headers.update(save_headers)
        try:
            save_res = self.session.post(url=save_url, json=save_data, verify=False).json()
            return True, save_res
        except:
            return False, "save timeout"

    def book_robot(self, book_info):
        try:
            # 声明订单信息变量
            logging.info('Task start: %s', book_info)
            account = str(book_info['username'])
            password = str(book_info['password'])
            dep_city = book_info["dep_city"]
            arr_city = book_info["arr_city"]
            from_date = book_info["from_date"]
            ret_date = book_info['ret_date']
            passengers = book_info['passengers']
            adult = len([pas for pas in passengers if pas['ptype'] == 0])
            child = len([pas for pas in passengers if pas['ptype'] == 1])
            flight_nums = book_info["flight_numbers"]
            contact_info = {
                'name': book_info['contact_name'],
                'phone': book_info['contact_phone'],
                'email': book_info['contact_email'],
            }
            # search req
            search_itineraries = [
                        {
                            "departureDate": from_date,
                            "origin": {
                                "airport": {"code": dep_city.upper()}
                            },
                            "destination": {
                                "airport": {"code": arr_city.upper()}
                            },
                            "segments": []
                        }
                    ]
            if ret_date:
                search_itineraries.append(
                    {
                        "departureDate": ret_date,
                        "origin": {
                            "airport": {"code": arr_city.upper()}
                        },
                        "destination": {
                            "airport": {"code": dep_city.upper()}
                        },
                        "segments": []
                    }
                )

            search_data = {
                "ecip": {
                    "shoppingPreference": {
                        "connectionPreference": {
                            "maxConnectionQuantity": 2
                        },
                        "flightPreference": {
                            "cabinCombineMode": "Cabin",
                            "lowestFare": True},
                        "accountCodeSlogan": ""
                    },
                    "cabinClasses": [
                        "Economy",
                        "Business",
                        "First"
                    ],
                    "passengerCount": {
                        "adult": adult,
                        "child": child,
                        "infant": 0
                    },
                    "itineraries": search_itineraries
                },
                "jfCabinFirst": False,
                "dOrI": "I",
                "isJCGM": False
            }
            search_status, search_res = self.search(search_data)
            if not search_status:
                self.set_log(self.book_id, u'搜索超时')
                return {"status": "failed", "msg": "search timeout", "pnr_code": ""}
            search_result = search_res.get("result", "")
            if not search_result:
                self.set_log(self.book_id, search_res.get('msg', 'search not flight'))
                return {"status": "failed", "msg": "search not flight", "pnr_code": ""}

            # 查找目标航线
            air_line = "%s-%s" % (dep_city.upper(), arr_city.upper())
            if ret_date:
                # 往返看的是pack
                egr_key = "pack"
            else:
                # 单程看的是sepa
                egr_key = "sepa"
            target_search_airline_infos = search_result.get("egr", {}).get(egr_key, {}).get(air_line, {})
            if not target_search_airline_infos:
                self.set_log(self.book_id, 'search no flights')
                return {"status": "failed", "msg": "search no flights", "pnr_code": ""}

            flight_nums_split = flight_nums.split('/')
            search_result_segmentDetail = search_result.get("egr", {}).get("segmentDetail", {})
            search_result_sepa = search_result.get("egr", {}).get("sepa", {})
            # 判断航班状态
            invalid_flight = set()
            for route in search_result_sepa:
                for flight in search_result_sepa[route]:
                    flight_num = flight.split('-')[0]
                    if search_result_sepa[route][flight].get('isSoldOut', False):
                        invalid_flight.add(flight_num)
            for flight_num in flight_nums_split:
                if flight_num in invalid_flight:
                    self.set_log(self.book_id, u'航班已售完: %s' % flight_num)
                    return {"status": "failed", "msg": u"航班已售完：%s" % flight_num, "pnr_code": ""}

            # 先整理出有效航班
            segmentdetail_key_num_list = [i.split("-")[0] for i in search_result_segmentDetail.keys()]
            # 再整理目标航班列表
            target_flight_list = []
            for flight_nums_single in flight_nums_split:
                req_f_num = flight_nums_single.split('~')
                for eachreqf in req_f_num:
                    target_flight_list.append(eachreqf)
            # 检查有效航班里是否有目标航班
            if not (set(target_flight_list) <= set(segmentdetail_key_num_list)):
                self.set_log(self.book_id, 'search target flights')
                return {"status": "failed", "msg": "search target flights", "pnr_code": ""}

            # 开始整理 searchdetail 的data
            search_detail_data = search_data

            # 收集分段航班详情
            # 顺便把下边用到的segmentid 收集起来
            segmentid_list = []
            for f_index in range(len(flight_nums_split)):
                segments_list = []
                flight_nums_single = flight_nums_split[f_index]
                req_f_num = flight_nums_single.split(',')
                for target_flight_one in req_f_num:
                    for segmentdetail_key, segmentdetail in search_result_segmentDetail.items():
                        if segmentdetail_key.split("-")[0] == target_flight_one:
                            segments_list.append(search_result_segmentDetail[segmentdetail_key])
                            segmentid_list.append(segmentdetail_key)
                search_detail_data['ecip']['itineraries'][f_index]['segments'] = segments_list

            # search detail
            search_detail_url = "https://www.xiamenair.com/api/offers"
            try:
                search_detail_res = self.session.post(url=search_detail_url, json=search_detail_data, verify=False).json()
            except:
                self.set_log(self.book_id, 'search detail timeout')
                return {"status": "failed", "msg": "search detail timeout", "pnr_code": ""}

            search_detail_result = search_detail_res.get("result", {})
            if not search_detail_result:
                self.set_log(self.book_id, 'search detail return no segment')
                return {"status": "failed", "msg": "search detail return no segment", "pnr_code": ""}

            search_detail_res_ecip = search_detail_result.get("ecip", {})
            itemId = search_detail_result.get("egr", {}).get(egr_key, {}).get(air_line, {}).values()[0].get(
                "groupLowest", {}).get("itemid", "")
            segmentId = ','.join(segmentid_list)

            ################## 把登陆放在search之后，验价之前
            if not self.login_status:
                login_status, redirect_url = self.login(account, password)
                if not login_status:
                    self.set_log(self.book_id, u'登陆失败，%s' % redirect_url)
                    return {"status": "failed", "msg": redirect_url, "pnr_code": ""}
                redirect_headers = {
                    "Host": "www.xiamenair.com",
                    "Connection": "keep-alive",
                    "Upgrade-Insecure-Requests": "1",
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/81.0.4044.138 Safari/537.36",
                    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.9",
                    "Sec-Fetch-Site": "same-site",
                    "Sec-Fetch-Mode": "navigate",
                    "Sec-Fetch-User": "?1",
                    "Sec-Fetch-Dest": "document",
                    "Referer": "https://uia.xiamenair.com/external/api/v1/oauth2/authorize?scope=user&response_type=code&client_id=PCWEB&lang=zh_cn&redirect_uri=https://www.xiamenair.com/api/users/ssocallback",
                    "Accept-Encoding": "gzip, deflate, br",
                    "Accept-Language": "zh-CN,zh;q=0.9",
                    # "Cookie": "sna=zh-cn; BIGipServersvrpool_brandnew_8080=1962935306.36895.0000; JSESSIONID=d898e100-6989-42d3-915f-881f6e1bf063; BIGipServersvrpool_brandnew_9080=486540298.30755.0000; gr_user_id=6c750f90-9f1b-4634-89e0-d17dc202f0b5; c=6AYlmy8A-1589086778492-35e8327a66e3b2127871337; grwng_uid=c7737ac0-c7db-4d9a-82f9-e0635ae39bef; _ga=GA1.2.1456436305.1589086779; _gid=GA1.2.1901900374.1589086779; smidV2=2020051012593895db000fe898f650c9fa99cc22997b63003f4a9022fc30a30; atk=undefined; userName=null; _xid=aqZ0%2FrqU1KmWQlyFrHQk8hPPmfNNFXsIeKne%2Bk3pcPTJZZTky70Ti%2BIlfXKJ08IorqCUoGzfGYf9XTZnEVnXrg%3D%3D; _fmdata=pNVw0TaXZYhsC%2BEYSyrfmd002%2Fqdmgy2XLaHtPdPiDtTwmA%2Bm%2B5I6yWIfCb%2F2lVTpjbs462NxvjGpIhNIsKHUdU5t6gEYmZ8XtqsBg8vLvA%3D; UIA_CHECK=15032288072",
                }
                self.session.headers.update(redirect_headers)
                try:
                    self.session.get(url=redirect_url)
                except:
                    self.set_log(self.book_id, 'redirect timeout')
                    return {"status": "failed", "msg": "redirect timeout", "pnr_code": ""}
                self.login_status=True

            # verify (select offer)
            select_data = {
                "egr": {
                    "searchParam": {
                        "jcgm": False,
                        "dOrI": "i",
                        "adtCount": adult,
                        "chdCount": child,
                        "infCount": 0,
                        "odList": [
                            {
                                "org": dep_city.upper(),
                                "dst": arr_city.upper(),
                                "orgDate": from_date
                            }
                        ],
                        "dstDate": ret_date,
                        "tripType": "RT" if ret_date else "OW"
                    },
                    "selectedOdOnlyContainIdList": [
                        {
                            "segmentId": segmentId,
                            "itemId": itemId
                        }
                    ]
                },
                "ecip": search_detail_res_ecip
            }
            select_status, select_get_res = self.verify(select_data)
            if not select_status:
                self.set_log(self.book_id, u'选择航班错误， %s' % select_get_res)
                return {"status": "failed", "msg": select_get_res, "pnr_code": ""}

            # order param post
            order_param_data = {
                "coupon": {},
                "dOrI": "i",
                "passengerList": [
                    {
                        "anonymousInd": False,
                        "familyName": eachpassenger['name'].split('/')[0],
                        "givenName": eachpassenger['name'].split('/')[1],
                        "name": eachpassenger['name'],
                        # "passengerType": "A",   # A-成人 ， C-儿童
                        "passengerType": "A" if self.age_to_dep(eachpassenger['birthday'], from_date) > 12 else "C",
                        "memberships": None,
                        "birthDate": eachpassenger['birthday'],
                        "citizenShipCountryCode": eachpassenger['nation'],
                        "identityDocuments": [
                            {
                                "name": eachpassenger['name'],
                                "identityDocType": "02",
                                "identityDocId": eachpassenger['card_num'],
                                "expiryDate": eachpassenger['expire_date'],
                                "issuingCountryCode": eachpassenger['card_place'],  # todo 这里需要传送的是国际二字码  CN
                                "genderCode": "01" if eachpassenger['sex'] == "M" else "02"  # 01-men, 02-women
                            }
                        ],
                        "contactInfo": {
                            "phone": contact_info['phone'],
                            "livingAddress": {"cityName": None, "street": None, "postalCode": None, "countryName": "CN",
                                              "counrtyCode": "CN", "countrySubDivisionName": None}
                        }
                    } for eachpassenger in passengers
                ],
                "orderContactInfo": {
                    "name": contact_info["name"],
                    "phone": contact_info["phone"],
                    "email": contact_info["email"]
                },
                "childPriceTypeD": "Y/J/F",
                # "firstRouteStartTime": "2020-07-06",
                # "firstRouteArriveTime": "2020-07-07",
                "firstRouteStartTime": from_date,
                "firstRouteArriveTime": from_date,
                "relationshipMap": None}
            order_param_status, order_param_get_res = self.order(order_param_data)
            if not order_param_status:
                self.set_log(self.book_id, u'添加乘客信息错误 %s' % order_param_get_res)
                return {"status": "failed", "msg": order_param_get_res, "pnr_code": ""}

            # save
            save_status, save_res = self.save()
            if not save_status:
                self.set_log(self.book_id, u'保存生单信息失败， %s' % save_res)
                return {"status": "failed", "msg": save_res, "pnr_code": ""}
            try:
                save_res_paxPnrList = save_res.get("result", {}).get("orderRefData", {}).get("paxPnrList", [])
            except BaseException:
                msg = save_res.get('msg', u'未找到预定PNR信息')
                self.set_log(self.book_id, msg)
                return {"status": "failed", "msg": msg, "pnr_code": ""}
            if not save_res_paxPnrList:
                return {"status": "failed", "msg": "save failed", "pnr_code": ""}

            pnr_code_list = [i["pnr"] for i in save_res_paxPnrList]
            pnr_code = ",".join(pnr_code_list)
            self.set_log(self.book_id, u'生单成功， 生单pnr信息： %s' % pnr_code)
            self.set_log(self.book_id, u'本次刷舱配置关闭')
            sql = 'update tools_crush_cabin set `status`=1 where `id`=%s' % self.book_id
            with self.db.cursor() as cur:
                cur.execute(sql)
            post_sms(contact_info['phone'])
            self.login_status=False
            return {
                "status": "ok",
                "msg": pnr_code,
                "pnr_code": pnr_code,
                "pnr_code_list": pnr_code_list,
            }
        except:
            return {"status": "failed", "msg": traceback.format_exc(), "pnr_code": ""}

def callback():
    client = redis.Redis(host=HOST, port=6379, password='liuhanchao')
    while True:
        robot = XiamenAirBook()
        task = client.lpop(robot.carrier)
        if not task:
            time.sleep(1)
            continue
        robot = XiamenAirBook()
        robot.mainjob(json.loads(task))


# if __name__ == '__main__':
#     robot = XiamenAirBook()
#     print robot.mainjob()

if __name__ == '__main__':
    config_log('xiamenair')
    pool = ThreadPoolExecutor(max_workers=50)
    for i in range(50):
        pool.submit(callback)
    pool.shutdown(wait=True)
    # client = redis.Redis(host=HOST, port=6379, password='liuhanchao')
    # # client = redis.Redis(host='127.0.0.1', port=6379, password='Lefei!123@')
    # robot = XiamenAirBook()
    # now = time.time()
    # while True:
    #     # robot = XiamenAirBook()
    #     task = client.lpop(robot.carrier)
    #     if not task:
    #         time.sleep(1)
    #         continue
    #     robot.mainjob(json.loads(task))
    #     if time.time() - now > 120:
    #        robot = XiamenAirBook()
    #        now = time.time()

