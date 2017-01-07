import logging
import time
import traceback
from urllib.parse import urlparse, parse_qs

import config
import util
from qq import JDQQ
from qqlib import LogInError


class Daka:
    job_name = '小白卡钢镚打卡'

    index_url = 'https://bk.jd.com/m/money/index.html'
    login_url = 'https://plogin.m.jd.com/cgi-bin/m/qqlogin'
    sign_url = 'https://bk.jd.com/m/money/home/daka.html'
    test_url = 'https://bk.jd.com/m/money/home/getUserInfo.html'
    job_gb_url = 'https://bk.jd.com/m/money/home/recDoJobMoney.html?pcId=82'

    def __init__(self, session):
        self.session = session
        self.client_id = ''
        self.redirect_uri = ''
        self.state = ''
        self.g_tk = 0
        self.job_success = False

    def run(self):
        print('##### Job start: {}'.format(self.job_name))

        is_login = self.is_login()
        print('# 登录状态: {}'.format(is_login))

        if not is_login:
            print('# 进行登录...')
            try:
                self.login()
                is_login = True
                print('# 登录成功')
            except Exception as e:
                print('# 登录失败: {}'.format(e))

        if is_login:
            if self.is_signed():
                self.job_success = True
            else:
                self.job_success = self.sign()

        print('##### Job End.')

    def is_login(self):
        r = self.session.get(self.test_url)

        if r.history and '/login' in r.url:
            return False
        else:
            return True

    def login_data(self):
        """
        在登录时需要附加的数据 (方便其他类继承...)
        """
        return {'appid': 100, 'returnurl': self.test_url}

    def login(self):
        r = self.session.get(self.login_url, params=self.login_data())
        # 请求后, 会进行两次跳转, 最终会跳转到 "QQ帐号安全登录" 页面
        # https://graph.qq.com/oauth/show?which=Login&display=pc&response_type=code&client_id=100273020&redirect_uri=https%3A%2F%2Fplogin.m.jd.com%2Fcgi-bin%2Fm%2Fqqcallback%3Fsid%3Dq8m7xgogbro69ucqegmearcmofs8zbcq&state=sp6r8u0z
        params = parse_qs(urlparse(r.url).query)

        try:
            self.client_id = params['client_id'][0]
            self.redirect_uri = params['redirect_uri'][0]

            if 'state' in params:
                # state 可能不存在, 比如在登录 web 版京东时
                self.state = params['state'][0]

        except Exception as e:
            raise Exception('缺少 client_id、redirect_uri 或 state 参数：' + str(e))

        self.login_qq()
        self.login_jd()

    def login_qq(self):
        """
        使用帐号密码进行登录
        """
        qq = JDQQ(config.qq['account'], config.qq['password'], self.session)

        try:
            qq.login()
            self.g_tk = qq.g_tk()

        except LogInError as e:
            raise LogInError('# 登录 QQ 失败: {}'.format(e))

    def login_jd(self):
        """
        使用第三方登录系统(QQ)登录京东
        """
        data = {
            'response_type': 'code',
            'client_id': self.client_id,
            'redirect_uri': self.redirect_uri,
            'state': self.state,
            'src': '1',
            'g_tk': self.g_tk,
            'auth_time': int(time.time())
        }

        r = self.session.post('https://graph.qq.com/oauth2.0/authorize', data=data)
        last_location = urlparse(r.url)

        if 'jd.com' not in last_location.netloc:
            logging.error('# 通过 QQ 登录京东失败.')
            logging.error('## Last page url: ' + r.url)
            logging.error('## Last page content: \n' + r.text)
            raise Exception('通过 QQ 登录京东失败.')

        logging.debug('# 通过 QQ 登录京东成功.')
        return True

    def is_signed(self):
        r = self.session.get(self.index_url)
        signed = False

        if r.ok:
            sign_pattern = r'dakaed:\s*(\w+)'
            days_pattern = r'dakaNum:\s*(\d+)'

            try:
                signed = ('true' == util.find_value(sign_pattern, r.text))
                sign_days = int(util.find_value(days_pattern, r.text))
                print('# 今日已打卡: {}; 打卡天数: {}'.format(signed, sign_days))

            except Exception as e:
                logging.error('# 返回数据结构可能有变化, 获取打卡数据失败: {}'.format(e))
                traceback.print_exc()

        return signed

    def sign(self):
        r = self.session.get(self.sign_url)
        sign_success = False

        if r.ok:
            as_json = r.json()
            sign_success = as_json['success']
            message = as_json['resultMessage']

            if not sign_success and as_json['resultCode'] == '0003':
                # 已打卡 7 次, 需要先去 "任务" 里完成领一个钢镚的任务...
                print('# 已打卡 7 次, 去完成领钢镚任务...')
                pick_success = self.pick_gb()

                if pick_success:
                    # 钢镚领取成功, 重新开始打卡任务
                    return self.sign()

                else:
                    message = '钢镚领取任务未成功完成.'

            print('# 打卡成功: {}; Message: {}'.format(sign_success, message))

        else:
            print('# 打卡失败: Status code: {}; Reason: {}'.format(r.status_code, r.reason))

        return sign_success

    def pick_gb(self):
        # 任务列表在 https://bk.jd.com/m/money/doJobMoney.html 中看
        # 领钢镚的任务的 id 是 82
        r = self.session.get(self.job_gb_url)
        pick_success = False

        try:
            as_json = r.json()
            pick_success = as_json['success']
            message = as_json['resultMessage']
            print('# 钢镚领取成功: {}; Message: {}'.format(pick_success, message))

        except Exception as e:
            logging.error('# 领钢镚 -> 钢镚领取失败: {}'.format(e))
            traceback.print_exc()

        return pick_success
