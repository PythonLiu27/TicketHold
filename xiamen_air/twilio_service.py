# -*- coding: utf-8 -*-

# Download the helper library from https://www.twilio.com/docs/python/install
from twilio.rest import Client


# Your Account Sid and Auth Token from twilio.com/console
# DANGER! This is insecure. See http://twil.io/secure
ACCOUNT_SID = 'ACf0ede23087f3267cd9543cfa1ff5d1d0'
AUTH_TOKEN = '0e372cdbdd3c3ae4ef7e8a34c84ce182'
# ACCOUNT_SID = 'ACc91f1bb91d363ef95b6e5da1889d1839'
# AUTH_TOKEN = 'd13630dc5a435a344be2eb2ab11cdf68'

def sms_post(phone_num, content):
    """
    使用twilio发送短信
    :param phone_num:
    :param content:
    :return:
    """
    client = Client(ACCOUNT_SID, AUTH_TOKEN)

    message = client.messages.create(
      body=content,
      from_='+12029331088',
      to='+86%s' % phone_num
  )
    print message.status
    print(message.sid)

if __name__ == '__main__':
    # sms_post('13716526790', u'oops， BKK-CNX AK001 WANGXUE has been order ，expire time 30 minutes')
    sms_post('15511623530', u'SHA-TYO 2020-06-30 LIU/HANCHAO Order Success, This PNR(HKYTGB) will expire in 30 minutes, please handle it as soon as possible' )
    # sms_post('15511623530', u'刷舱提醒 SHA-TYO 2020-06-30- LIU/HANCHAO~DAI/YANGHAO已占舱成功，占舱PNR: H7KHYT，占舱有效期30分钟，请尽快支付！')

# client = Client(ACCOUNT_SID, AUTH_TOKEN)
# message = client.messages \
#                 .create(
#                      body="Join Earth's mightiest heroes. Like Kevin Bacon.",
#                      from_='+12057840486',
#                      to='+8615511623530'
#                  )
#
# print(message.sid)
# print(message.status)