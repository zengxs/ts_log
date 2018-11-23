import logging
import os
import socket
import threading
import time
from collections import namedtuple
from queue import Empty as QueueEmptyException
from queue import Queue

import psutil
import requests
from influxdb.line_protocol import make_lines

TsRequest = namedtuple('TsRequest', ['endpoint', 'data'])

__influx_endpoint = None
__log_queue = None


class ArgumentError(ValueError):
    pass


def get_nanosecond_timestamp():
    """ 返回当前时间的 19 位时间戳 """
    return int(time.time() * (10**9))


def push_ts_data(measurement,
                 tags,
                 fields,
                 time=None,
                 endpoint=None,
                 wait=True):
    """
    :type measurement: str
    :param measurement: 数据被保存的 measurement
    :type tags: dict
    :param tags: 存入数据的标签
    :type fields: dict
    :param fields: 存入数据的值
    :type time: int
    :param time: 19 位时间戳 
    :type endpoint: str
    :param endpoint: influx 的 endpoint;
        如为 None 则使用 install_monitor 初始化的 endpoint
    :type wait: bool
    :param wait: 入队时是否阻塞，如为 False 且队列已满可能会抛出异常
    """
    global __log_queue, __influx_endpoint

    # 校验参数
    for _, v in fields.items():
        if v:
            break
    else:
        raise ArgumentError

    point = {
        'time': time or get_nanosecond_timestamp(),
        'measurement': measurement,
        'tags': tags,
        'fields': fields,
    }
    request = TsRequest(
        endpoint=endpoint or __influx_endpoint,
        data=make_lines({
            'points': [point],
        }))
    put = __log_queue.put if wait else __log_queue.put_nowait
    put(request)


def __push_data_to_influx(block_timeout=1):
    """ 推送时序数据
    """
    global __log_queue
    logger = logging.getLogger('influx_pushd')
    while True:
        try:
            req = __log_queue.get(timeout=block_timeout)  # type: TsRequest
            r = requests.post(
                req.endpoint, data=req.data, timeout=block_timeout)
            if not r.ok:
                logger.warning(r.headers)
        except QueueEmptyException as e:
            logger.debug('Catched a queue Empty excetion')
        except Exception as e:
            logger.exception(e)


def install_monitor(spider_name,
                    host=socket.gethostname(),
                    influx_endpoint='http://127.0.0.1:8086/write?db=spiders',
                    heartbeat_interval=1,
                    queue_size=4096,
                    push_consumers=1,
                    without_heartbeat=False):
    """ 安装进程监控器
    监视进程的cpu占用与内存占用

    :param spider_name: 爬虫唯一名称 (不同爬虫使用不同名称)
    :param host: 本机 hostname (简易使用本机内网IP, 如 10.1.1.127)
    :param influx_endpoint: influxdb 接口地址
    :param influx_measurement: 数据被保存的 measurement，通常无需更改
    :param heartbeat_interval: 上报心跳包的间隔时间 (seconds)
    :param queue_size: 队列大小 (默认 4096)
    :param push_consumers: 日志推送线程数
    :param without_heartbeat: 是否自动发送心跳包
    """
    global __log_queue, __influx_endpoint
    if __log_queue is None:
        __log_queue = Queue(maxsize=queue_size)
    __influx_endpoint = influx_endpoint
    heartbeat_logger = logging.getLogger('heartbeat')

    def heartbeat(interval=10):
        while True:
            try:
                current_pid = os.getpid()
                current_process = psutil.Process(current_pid)
                cpu_percent = current_process.cpu_percent(interval)
                mem_usage = current_process.memory_full_info().uss
                heartbeat_logger.info(
                    f'PID({current_pid}) {spider_name}, {host}, {cpu_percent}%, {mem_usage} Bytes'
                )
                push_ts_data(
                    measurement='heartbeat',
                    tags={
                        'spider-name': spider_name,
                        'host': host,
                    },
                    fields={
                        'cpu_percent': cpu_percent,
                        'mem_usage': mem_usage,
                    },
                    time=get_nanosecond_timestamp())
            except Exception as e:
                heartbeat_logger.exception(e)

    if not without_heartbeat:
        heartbeat_thread = threading.Thread(
            target=heartbeat, args=(heartbeat_interval, ))
        heartbeat_thread.setDaemon(True)
        heartbeat_thread.start()

    for i in range(push_consumers):
        bg_push_thread = threading.Thread(target=__push_data_to_influx)
        bg_push_thread.setDaemon(True)
        bg_push_thread.start()


if __name__ == '__main__':
    """ 测试代码 """
    logging.basicConfig(
        level=logging.DEBUG,
        format='[%(asctime)-15s][%(levelname)s][%(name)s] %(message)s')
    install_monitor('test', heartbeat_interval=1)
    while True:
        push_ts_data(
            'responses',
            tags={
                'status_code': 222,
                'spider-name': 'test'
            },
            fields={
                'reason': 'HTTP OK',
                'cost': 12.3
            },
            time=get_nanosecond_timestamp())
        time.sleep(1)
