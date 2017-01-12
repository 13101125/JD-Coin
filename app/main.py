import logging
import pickle
import traceback
from pathlib import Path

import requests

from config import config
from job import jobs_all


def main():
    session = make_session()

    print()  # 空一行...

    failed_jobs = []

    for job_class in jobs_all:
        job = job_class(session)

        try:
            job.run()
        except Exception as e:
            logging.error('# 任务运行出错: ' + repr(e))
            traceback.print_exc()

        if not job.job_success:
            failed_jobs.append(job.job_name)

        print()

    print('=================================')
    print('= 任务数: {}; 失败数: {}'.format(len(jobs_all), len(failed_jobs)))

    if len(failed_jobs) > 0:
        print('= 失败的任务: {}'.format(failed_jobs))
    else:
        print('= 全部成功 ~')

    print('=================================')

    save_session(session)


def make_session():
    session = requests.Session()

    session.headers.update({
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; WOW64; rv:50.0) Gecko/20100101 Firefox/50.0'
    })

    data_file = Path(__file__).parent.joinpath('../data/cookies')

    if data_file.exists():
        try:
            bytes = data_file.read_bytes()
            cookies = pickle.loads(bytes)
            session.cookies = cookies
            print('# 从文件加载 cookies 成功.')
        except Exception as e:
            print('# 未能成功载入 cookies, 从头开始~')

    return session


def save_session(session):
    data = pickle.dumps(session.cookies)

    data_dir = Path(__file__).parent.joinpath('../data/')
    data_dir.mkdir(exist_ok=True)
    data_file = data_dir.joinpath('cookies')
    data_file.write_bytes(data)


def debug_patch():
    """
    不验证 HTTPS 证书, 便于使用代理工具进行网络调试...
    """
    from requests import Session

    class XSession(Session):
        def __init__(self):
            super().__init__()
            self.verify = False

    requests.Session = XSession


if __name__ == '__main__':
    if config.debug:
        debug_patch()

    main()
