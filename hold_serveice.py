# -*- coding:utf-8 -*-

"""
从配置中读取刷舱配置信息， 并写入对应的redis队列
"""
import datetime
import json
import logging
import platform
import time
# import MySQLdb
import pymysql
import redis

from utils.config_log import config_log

HOST = '47.100.232.150' if platform.dist()[0] != 'centos' else 'localhost'


class HoldService(object):
    """
    刷舱配置程序
    """
    def __init__(self):
        self.db = pymysql.connect(
            host = HOST,
            port = 3306,
            user = 'root',
            password='wogannimei123',
            db = 'liuhanchao',
            charset='utf8',
            autocommit=True,
            cursorclass=pymysql.cursors.DictCursor
        )
        self.redis = redis.Redis(host='127.0.0.1', port=6379, password='Lefei!123@')

    def main(self):
        """
        主程序
        :return:
        """
        sql = 'select * from view_crush_cabin'
        try:
            with self.db.cursor() as cur:
                cur.execute(sql)
                result = cur.fetchall()
        except BaseException:
            logging.exception('get hold config error')
            return
        logging.info('get hold task: %s', result)
        if not result:
            return
        today = datetime.datetime.now().strftime('%Y-%m-%d')
        for record in result:
            record['from_date'] = record['from_date'].strftime('%Y-%m-%d')
            record['ret_date'] = record['ret_date'].strftime('%Y-%m-%d') if record['ret_date'] else ''
            if not record['ret_date']:
                # sql = 'insert into tools_crush_cabin_log (line_id, remarks, create_time) values (%s, "%s", %s)' % (
                # record['id'], u'暂不支持往返行程', int(time.time()))
                # with self.db.cursor() as cur:
                #     cur.execute(sql)
                continue
            if today > record['from_date'] or (record['ret_date'] and record['from_date'] > record['ret_date']):
                logging.info('hold config %s has been expired!', record['id'])
                continue
            pas_sql = 'select * from tools_crush_cabin_passenger where line_id=%s' % record['id']
            with self.db.cursor() as cur:
                cur.execute(pas_sql)
                passengers = cur.fetchall()
                for p in passengers:
                    p['birthday'] = p['birthday'].strftime('%Y-%m-%d')
                    p['expire_date'] = p['expire_date'].strftime('%Y-%m-%d')
                if not passengers:
                    logging.info('hold config %s no passenger set', record['id'])
                    continue
                record['passengers'] = passengers
                self.redis.lpush(record['carrier'], json.dumps(record))
        logging.info('process hold task finish!')

if __name__ == '__main__':
    config_log('hold_service')
    HOLD = HoldService()
    HOLD.main()

