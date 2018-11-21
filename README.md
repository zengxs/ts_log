# 监控代码
安装：
~~~sh
pip install git+https://github.com/zengxs/ts_log.git
~~~

基本用法：
~~~py
from ts_log import install_monitor
install_monitor(
    'test',  # 爬虫名称
    host='10.1.2.10',  # 本机地址
    influx_endpoint='http://10.1.1.127:8086/write?db=spiders',  # 监控数据库服务器地址
    heartbeat_interval=1,  # 心跳间隔
)
~~~

监控其他数据：
~~~py
import time
from ts_log import push_ts_data

push_ts_data(
    measurement='responses',
    tags={
        'spider-name': 'test',
        'host': '10.1.1.10',
        'status_code': 200,
    },
    fields={
        'cost_time': 10.23,  # 10.23ms
        'reason': 'OK',
    },
    time=int(time.time() * (10 ** 9)))
~~~

