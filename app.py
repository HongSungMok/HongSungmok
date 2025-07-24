from datetime import datetime
from flask import Flask, request, jsonify
import os
import traceback
import re
import logging
from fish_data import fish_data

logging.basicConfig(level=logging.INFO)

app = Flask(__name__)


OPENROUTER_API_KEY = os.environ.get("OPENROUTER_API_KEY")
OPENROUTER_API_URL = "https://openrouter.ai/api/v1/chat/completions"

fish_emojis = {
    "갈치": "🐟",
    "참조기": "🐠",
    "대게": "🦀",
    "붉은대게": "🦀",
    "오분자기": "🐚",
    "키조개": "🦪",
    "주꾸미": "🦑",
    "게": "🦀",
    "해삼": "🌊"
}


context = """
[요약]
[제1조] 목적 – 수산자원의 보호·회복·조성 등 관리 및 어업인의 소득증대 목적
[제2조] 정의 – 수산자원, 총허용어획량, 수산자원조성, 바다목장 정의
[제3조] 수산자원의 조사·연구 – 정부가 자원 상태 조사 책임
[제4조] 수산자원 조성 – 어초·해조장 설치 및 종자 방류 등 조성 가능
[제5조] 허가·등록 – 어업활동을 위한 허가/등록 절차 규정
[제6조] 허가 조건 – 허가 시 어업 방식·장비·어획량 조건 명시 가능
[제7조] 조업 금지 구역 – 어업 종류별 금지구역 예: 외끌이·트롤어업
[제8조] 휴어기 설정 – 자원 상태 등 고려하여 설정 가능
[제9조] 어장 안전관리 – 안전사고 예방 규정
[제10조] 어업 질서 유지 – 자원 보호와 질서 확립에 부합하도록 규제
[제11조] 정밀조사·평가 계획 – 자원 현황 평가 및 회복계획 수립 의무
[제12조] 어획물 등의 조사
  ① 해수부장관 또는 시·도지사는 시장·공판장·어선 등에 출입하여 어획물 종류·어획량 등을 조사할 수 있다.
  ② 조사 관원은 신분증명서를 지니고 제시해야 하며, 승선조사 전 어선주와 사전 협의해야 한다.
[제13조] 조성 정보 제출
  어획 실적·어장환경·어법 등 조사 데이터를 국립수산과학원에 제출해야 한다.
[제14조] 비어업인의 포획 제한
  투망·반두·외줄낚시 등 특정 어구는 비어업인의 사용이 제한됨
[제15조] 중복 자망 사용 승인
  이중 이상의 자망 사용은 별도로 승인 받아야 함
[제16조] 휴어기 설정
  해수부장관은 수산자원 보호를 위해 일정 기간 회피 조업(휴어기)을 설정할 수 있음
[제17조] 어장 안전·환경 보호
  어장 안전사고 예방 및 오염 방지를 위해 어장 환경을 관리해야 함
[제18조] 금지 수단
  폭발물·전기장치 등 금지 수단으로 어획하면 강력한 처벌 대상임

[형벌·벌칙 요약]
[제64조] 2년 이하 징역 또는 2천만 원 이하 벌금:
 • 금어기·금지체장 어업(제14조 위반)
 • 어장 안전·환경 무시(제17조 위반)
 • 휴어기 중 어업(제19조 제2항 위반)
 • 어선 관련 불법 행위(제22조 위반)
 • 폭발물·전류 등 금지수단 사용(제25조 제1항 위반)
 • 유해화학물질 무허가 사용(제25조 제2항 위반)
 • 수산자원 보호 명령 위반, 할당량 초과 어획 등
[제65조] 1천만 원 이하 벌금:
 • 조업금지구역 어업(제15조 위반)
 • 비어업인의 금지 포획(제18조 위반)
 • 2중 자망 무단 사용(제23조 3항 위반)
 • 금지 어구 제작·판매·보관(제24조 위반) 등
[제66조] 500만 원 이하 벌금:
 • 오염행위, 어획량 초과, 명령 불이행 등
[제67조] 300만 원 이하 벌금:
 • 불법 어획물 방류명령 불이행, 허위 보고, 지정 외 거래 등
"""

def is_date_in_range(period: str, today: datetime) -> bool:
    try:
        start_str, end_str = period.split("~")
        start_month, start_day = map(int, start_str.strip().split("."))
        if "익년" in end_str:
            end_str = end_str.replace("익년", "")
            end_month, end_day = map(int, end_str.strip().split("."))
            start_date = datetime(today.year, start_month, start_day)
            end_date = datetime(today.year + 1, end_month, end_day)
        else:
            end_month, end_day = map(int, end_str.strip().split("."))
            start_date = datetime(today.year, start_month, start_day)
            end_date = datetime(today.year, end_month, end_day)
        return start_date <= today <= end_date
    except:
        return False

def filter_periods(periods, today):
    if isinstance(periods, dict):
        valid = {}
        for key, val in periods.items():
            if is_date_in_range(val, today):
                valid[key] = val
        return valid if valid else None
    elif isinstance(periods, str):
        return periods if is_date_in_range(periods, today) else None
    return None

def format_period(period: str) -> str:
    try:
        start_str, end_str = period.split("~")
        start_month, start_day = map(int, start_str.strip().split("."))
        if "익년" in end_str:
            end_str = end_str.replace("익년", "")
            end_month, end_day = map(int, end_str.strip().split("."))
            return f"{start_month}월 {start_day}일 ~ 익년 {end_month}월 {end_day}일"
        else:
            end_month, end_day = map(int, end_str.strip().split("."))
            return f"{start_month}월 {start_day}일 ~ {end_month}월 {end_day}일"
    except:
        return period

def get_fish_info(fish_name, fish_data, today=None):
    if today is None:
        today = datetime.today()
    fish = fish_data.get(fish_name)
    if not fish:
        return f"🚫 금어기: 없음\n🚫 금지체장: 없음"

    금어기 = "없음"
    for key in ["금어기", "유자망_금어기", "근해채낚기_연안복합_정치망_금어기", "지역별_금어기", "금어기_예외"]:
        if key in fish:
            value = filter_periods(fish[key], today)
            if value:
                if isinstance(value, dict):
                    # ○○: 부분 제거, 그냥 날짜만 출력
                    금어기 = "; ".join(format_period(v) for v in value.values())
                else:
                    금어기 = format_period(value)
                break
            elif isinstance(fish[key], dict):
                금어기 = "; ".join(format_period(v) for v in fish[key].values())
                break
            elif isinstance(fish[key], str):
                금어기 = format_period(fish[key])
                break

    금지체장 = fish.get("금지체장") or fish.get("금지체중") or "없음"
    if isinstance(금지체장, dict):
        금지체장 = 금지체장.get("기본") or next(iter(금지체장.values()), "없음")

    예외사항 = fish.get("금어기_해역_특이사항") or fish.get("금어기_예외") or fish.get("금어기_특정해역") or fish.get("금어기_추가")
    포획비율 = fish.get("포획비율제한")

    result = f"🚫 금어기: {금어기}\n🚫 금지체장: {금지체장}"
    if 예외사항:
        result += f"\n⚠️ 예외사항: {예외사항}"
    if 포획비율:
        result += f"\n⚠️ 포획비율제한: {포획비율}"

    return result

def extract_fish_name(user_input, fish_list):
    for name in fish_list:
        if name in user_input:
            return name
    return None

@app.route("/TAC", methods=["POST"])
def fishbot():
    body = request.get_json()
    user_input = body["userRequest"]["utterance"].strip()
    today = datetime.today()
    주요_어종 = list(fish_data.keys())

    # 현재 금어기 중인 어종 요청
    if "현재 금어기" in user_input or "오늘 금어기" in user_input:
        result = []
        for name, data in fish_data.items():
            for key in ["금어기", "유자망_금어기", "근해채낚기_연안복합_정치망_금어기", "지역별_금어기", "금어기_예외"]:
                if key in data:
                    if filter_periods(data[key], today):
                        result.append(name)
                        break
        if result:
            answer = f"🌟 오늘 금어기 중인 어종:\n" + ", ".join(result)
            buttons = [{"label": name, "action": "message", "messageText": name} for name in result]
        else:
            answer = "현재 금어기 중인 어종이 없습니다."
            buttons = []
        return jsonify({
            "version": "2.0",
            "template": {
                "outputs": [{"simpleText": {"text": answer}}],
                "quickReplies": buttons
            }
        })

    # 'X월 금어기 알려줘' 요청
    if "월 금어기" in user_input:
        match = re.search(r"(\d{1,2})월", user_input)
        if match:
            month = int(match.group(1))
            result = []
            for name, data in fish_data.items():
                for key in ["금어기", "유자망_금어기", "근해채낚기_연안복합_정치망_금어기", "지역별_금어기", "금어기_예외"]:
                    if key in data:
                        periods = data[key]
                        if isinstance(periods, dict):
                            for p in periods.values():
                                if p.startswith(f"{month}.") or f"~{month}." in p:
                                    result.append(name)
                                    break
                        elif isinstance(periods, str):
                            if periods.startswith(f"{month}.") or f"~{month}." in periods:
                                result.append(name)
                                break
            if result:
                answer = f"📅 {month}월 금어기 어종:\n" + ", ".join(result)
                buttons = [{"label": name, "action": "message", "messageText": name} for name in result]
            else:
                answer = f"{month}월 금어기 중인 어종이 없습니다."
                buttons = []
            return jsonify({
                "version": "2.0",
                "template": {
                    "outputs": [{"simpleText": {"text": answer}}],
                    "quickReplies": buttons
                }
            })

    # 어종 이름만 입력한 경우
    fish_name = extract_fish_name(user_input, 주요_어종)
    if not fish_name:
        fish_name = user_input.replace(" 금어기", "").strip()

    info = get_fish_info(fish_name, fish_data)
    return jsonify({
        "version": "2.0",
        "template": {
            "outputs": [{"simpleText": {"text": f"🐟{fish_name}🐟\n\n{info}"}}],
            "quickReplies": []
        }
    })

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)