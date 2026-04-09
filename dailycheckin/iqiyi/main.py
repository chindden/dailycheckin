import json
import os
import re
import time
from urllib.parse import unquote
from uuid import uuid4

import requests

from dailycheckin import CheckIn


class IQIYI(CheckIn):
    name = "爱奇艺"

    def __init__(self, check_item):
        self.check_item = check_item
        self.session = requests.Session()
        self.timeout = 10

    @staticmethod
    def parse_cookie(cookie):
        cookie = cookie or ""
        p00001 = re.findall(r"P00001=(.*?);", cookie)[0] if re.findall(r"P00001=(.*?);", cookie) else ""
        p00002 = re.findall(r"P00002=(.*?);", cookie)[0] if re.findall(r"P00002=(.*?);", cookie) else ""
        p00003 = re.findall(r"P00003=(.*?);", cookie)[0] if re.findall(r"P00003=(.*?);", cookie) else ""
        __dfp = re.findall(r"__dfp=(.*?);", cookie)[0] if re.findall(r"__dfp=(.*?);", cookie) else ""
        __dfp = __dfp.split("@")[0] if __dfp else ""
        qyid = re.findall(r"QC005=(.*?);", cookie)[0] if re.findall(r"QC005=(.*?);", cookie) else ""
        return p00001, p00002, p00003, __dfp, qyid

    @staticmethod
    def safe_mask_username(user_name):
        user_name = user_name or ""
        if not user_name:
            return "未获取到，请检查 Cookie 中 P00002 字段"
        if len(user_name) >= 7:
            return user_name[:3] + "****" + user_name[7:]
        if len(user_name) >= 3:
            return user_name[:3] + "****"
        return user_name

    def request_json(self, method, url, **kwargs):
        try:
            kwargs.setdefault("timeout", self.timeout)
            response = self.session.request(method=method, url=url, **kwargs)
            response.raise_for_status()
            return response.json()
        except requests.RequestException as e:
            print(f"请求失败: {url}, 错误: {e}")
            return {}
        except ValueError as e:
            print(f"JSON 解析失败: {url}, 错误: {e}")
            return {}

    def user_information(self, p00001):
        """
        账号信息查询
        """
        time.sleep(3)
        url = "http://serv.vip.iqiyi.com/vipgrowth/query.action"
        params = {"P00001": p00001}
        res = self.request_json("GET", url, params=params)

        if res.get("code") == "A00000":
            try:
                res_data = res.get("data") or {}
                level = res_data.get("level", 0)
                growthvalue = res_data.get("growthvalue", 0)
                distance = res_data.get("distance", 0)
                deadline = res_data.get("deadline", "非 VIP 用户")
                today_growth_value = res_data.get("todayGrowthValue", 0)
                msg = [
                    {"name": "VIP 等级", "value": level},
                    {"name": "当前成长", "value": growthvalue},
                    {"name": "今日成长", "value": today_growth_value},
                    {"name": "升级还需", "value": distance},
                    {"name": "VIP 到期", "value": deadline},
                ]
            except Exception as e:
                msg = [{"name": "账号信息", "value": f"解析失败: {e}"}]
        else:
            msg = [{"name": "账号信息", "value": res.get("msg", "查询失败")}]
        return msg

    def lottery(self, p00001, award_list=None):
        """
        每天摇一摇
        """
        if award_list is None:
            award_list = []

        url = "https://act.vip.iqiyi.com/shake-api/lottery"
        params = {
            "P00001": p00001,
            "deviceID": str(uuid4()),
            "version": "15.3.0",
            "platform": str(uuid4())[:16],
            "lotteryType": "0",
            "actCode": "0k9GkUcjqqj4tne8",
            "extendParams": json.dumps(
                {
                    "appIds": "iqiyi_pt_vip_iphone_video_autorenew_12m_348yuan_v2",
                    "supportSk2Identity": True,
                    "testMode": "0",
                    "iosSystemVersion": "17.4",
                    "bundleId": "com.qiyi.iphone",
                }
            ),
        }

        res = self.request_json("GET", url, params=params)
        msgs = []

        if res.get("code") == "A00000":
            data = res.get("data") or {}
            award_info = data.get("title", "")
            if award_info:
                award_list.append(award_info)
            time.sleep(3)
            return self.lottery(p00001=p00001, award_list=award_list)

        elif res.get("msg") == "抽奖次数用完":
            if award_list:
                msgs = [{"name": "每天摇一摇", "value": "、".join(award_list)}]
            else:
                msgs = [{"name": "每天摇一摇", "value": res.get("msg", "抽奖次数用完")}]
        else:
            msgs = [{"name": "每天摇一摇", "value": res.get("msg", "接口返回异常")}]

        return msgs

    def draw(self, draw_type, p00001, p00003):
        """
        查询抽奖次数(0) / 抽奖(1)
        :param draw_type: 0 查询次数, 1 抽奖
        :param p00001: 关键参数
        :param p00003: 关键参数
        :return: {status, msg, chance}
        """
        url = "https://iface2.iqiyi.com/aggregate/3.0/lottery_activity"
        params = {
            "lottery_chance": 1,
            "app_k": "b398b8ccbaeacca840073a7ee9b7e7e6",
            "app_v": "11.6.5",
            "platform_id": 10,
            "dev_os": "8.0.0",
            "dev_ua": "FRD-AL10",
            "net_sts": 1,
            "qyid": "2655b332a116d2247fac3dd66a5285011102",
            "psp_uid": p00003,
            "psp_cki": p00001,
            "psp_status": 3,
            "secure_v": 1,
            "secure_p": "GPhone",
            "req_sn": round(time.time() * 1000),
        }
        if draw_type == 1:
            params.pop("lottery_chance", None)

        res = self.request_json("GET", url, params=params)

        if not res.get("code"):
            try:
                chance = int(res.get("daysurpluschance", 0) or 0)
            except Exception:
                chance = 0
            msg = res.get("awardName", "")
            return {"status": True, "msg": msg, "chance": chance}
        else:
            try:
                msg = (res.get("kv") or {}).get("msg") or res.get("errorReason") or res.get("msg") or "未知错误"
            except Exception as e:
                print(f"draw 接口解析异常: {e}")
                msg = "未知错误"

        return {"status": False, "msg": msg, "chance": 0}

    def level_right(self, p00001):
        """
        先查询是否已经为星钻VIP（假设 level >= 7 为星钻）
        如果是：返回有效期
        否则：请求升级接口并返回升级结果
        """
        try:
            url = "http://serv.vip.iqiyi.com/vipgrowth/query.action"
            params = {"P00001": p00001}
            res = self.request_json("GET", url, params=params)

            if res.get("code") == "A00000":
                data = res.get("data") or {}
                level = int(data.get("level", 0) or 0)
                deadline = data.get("deadline", "未知")
                if level >= 7:
                    return [{"name": "V7 免费升级星钻", "value": f"已是星钻VIP，有效期: {deadline}"}]

            post_data = {"code": "k8sj74234c683f", "P00001": p00001}
            res2 = self.request_json("POST", "https://act.vip.iqiyi.com/level-right/receive", data=post_data)
            msg = res2.get("msg", str(res2) if res2 else "接口无返回")
            return [{"name": "V7 免费升级星钻", "value": msg}]
        except Exception as e:
            return [{"name": "V7 免费升级星钻", "value": f"操作异常: {e}"}]

    def give_times(self, p00001):
        url = "https://pcell.iqiyi.com/lotto/giveTimes"
        times_code_list = ["browseWeb", "browseWeb", "bookingMovie"]
        for times_code in times_code_list:
            params = {
                "actCode": "bcf9d354bc9f677c",
                "timesCode": times_code,
                "P00001": p00001,
            }
            self.request_json("GET", url, params=params)

    def lotto_lottery(self, p00001):
        """
        白金抽奖
        原报错大概率出在这里：response.json()["data"]["giftName"]
        当 data 为 None 时会报：'NoneType' object is not subscriptable
        """
        self.give_times(p00001=p00001)
        gift_list = []

        for _ in range(5):
            url = "https://pcell.iqiyi.com/lotto/lottery"
            params = {"actCode": "bcf9d354bc9f677c", "P00001": p00001}
            res = self.request_json("GET", url, params=params)

            data = res.get("data") or {}
            gift_name = data.get("giftName", "")

            if gift_name and "未中奖" not in gift_name:
                gift_list.append(gift_name)

        if gift_list:
            return [{"name": "白金抽奖", "value": "、".join(gift_list)}]
        return [{"name": "白金抽奖", "value": "未中奖"}]

    def main(self):
        p00001, p00002, p00003, dfp, qyid = self.parse_cookie(self.check_item.get("cookie", ""))

        try:
            user_info = json.loads(unquote(p00002, encoding="utf-8")) if p00002 else {}
            user_name = self.safe_mask_username(user_info.get("user_name"))
            nickname = user_info.get("nickname") or "未获取到，请检查 Cookie 中 P00002 字段"
        except Exception as e:
            print(f"获取账号信息失败，错误信息: {e}")
            nickname = "未获取到，请检查 Cookie 中 P00002 字段"
            user_name = "未获取到，请检查 Cookie 中 P00002 字段"

        user_msg = self.user_information(p00001=p00001)
        lotto_lottery_msg = self.lotto_lottery(p00001=p00001)
        level_right_msg = self.level_right(p00001=p00001)

        chance_info = self.draw(draw_type=0, p00001=p00001, p00003=p00003)
        chance = chance_info.get("chance", 0)

        lottery_msgs = self.lottery(p00001=p00001, award_list=[])

        if chance:
            draw_result = []
            for _ in range(chance):
                ret = self.draw(draw_type=1, p00001=p00001, p00003=p00003)
                if ret.get("status") and ret.get("msg"):
                    draw_result.append(ret["msg"])
            draw_msg = ";".join(draw_result) if draw_result else "抽奖失败或无奖励"
        else:
            draw_msg = chance_info.get("msg") or "抽奖机会不足"

        msg = [
            {"name": "用户账号", "value": user_name},
            {"name": "用户昵称", "value": nickname},
            *user_msg,
            {"name": "抽奖奖励", "value": draw_msg},
            *lottery_msgs,
            *level_right_msg,
            *lotto_lottery_msg,
        ]

        return "\n".join([f"{one.get('name')}: {one.get('value')}" for one in msg])


if __name__ == "__main__":
    with open(
        os.path.join(os.path.dirname(os.path.dirname(__file__)), "config.json"),
        encoding="utf-8",
    ) as f:
        datas = json.loads(f.read())

    _check_item = datas.get("IQIYI", [])[0]
    print(IQIYI(check_item=_check_item).main())
