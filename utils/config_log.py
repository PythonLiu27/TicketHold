# -*- coding:utf-8 -*-
"""
日志记录
"""
import logging


def config_log(log_name):
    """
    日志文件配置
    :return:
    """
    level = logging.INFO
    fmt = '%(asctime)s - %(levelname)s - %(message)s - %(thread)d'
    logging.basicConfig(filename='/var/log/{log_name}.log'.format(log_name=log_name), level=level, format=fmt)
    console = logging.StreamHandler()
    console.setLevel(level)
    console.setFormatter(logging.Formatter(fmt))
    logging.getLogger('').addHandler(console)
