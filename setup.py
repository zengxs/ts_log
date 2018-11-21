from setuptools import setup, find_packages

setup(
    name="ts_log",
    version="0.0.1",
    description="timeseries log module",
    url='https://github.com/zengxs/ts_log',
    author="zengxs",
    author_email="i@zengxs.com",
    packages=['ts_log'],
    install_requires=[
        'requests',
        'influxdb',
        'psutil',
    ]
)

