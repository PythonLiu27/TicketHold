# -*- coding:utf-8 -*-
import logging
from urllib import quote, urlencode

import requests

USERNAME = 'xfhangkong'
PASSWORD = 'xfhk8888'

URL = 'http://service2.winic.org/service.asmx/SendMessages?'
URL_SMS = 'http://service.winic.org:8009/sys_port/gateway/index.asp?'


def post_sms(phone_num):
    """
    使用吉信通发送通知短信
    :param phone_nnum:
    :param content:
    :return:
    """
    content = quote(u'占舱提醒！ 订单已占位成功， 请尽快处理，以免PNR失效！'.encode('gb2312'))
    data = """id=%s&pwd=%s&to=%s&content=%s&time=""" % (
        USERNAME, PASSWORD, phone_num, content
    )
    try:
        resp = requests.get(URL_SMS+data, timeout=30).content
        logging.info('sent msg resp: %s', resp)
    except BaseException:
        logging.exception('sent sms error')


# post_sms('15511623530', u'占舱提醒！ 订单已占位成功， 请尽快处理，以免PNR失效！'.encode('gb2312'))

