from flask import Flask, request, jsonify
from datetime import datetime
import re
import logging
import os

from fish_data import fish_data
from fish_utils import get_fish_info

logging.basicConfig(level=logging.INFO)

app = Flask(__name__)

OPENROUTER_API_KEY = os.environ.get("OPENROUTER_API_KEY")
OPENROUTER_API_URL = "https://openrouter.ai/api/v1/chat/completions"

# 별칭 → 대표명 매핑
alias_map = {
    "오징어": "살오징어",
    "광어": "넙치",
    "우럭": "조피볼락",
}

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

def normalize_fish_name(name):
    """별칭 → 대표명 변환, 없으면 그대로 반환"""
    return alias_map.get(name, name)

def get_display_name(fish_name):
    """
    출력용 이름
    - 별칭이면 대표명(별칭)
    - 대표명이면 대표명(별칭) 형태(별칭이 있으면)
    - 별칭/대표명 모두 없으면 그대로
    """
    # 입력이 별칭인 경우
    if fish_name in alias_map:
        rep_name = alias_map[fish_name]
        return f"{rep_name}({fish_name})"
    # 입력이 대표명인 경우, 별칭 찾아 표시
    for alias, rep in alias_map.items():
        if rep == fish_name:
            return f"{fish_name}({alias})"
    return fish_name

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

def format_exception_dates(text: str) -> str:
    pattern = r"(\d{1,2}\.\d{1,2}~\d{1,2}\.\d{1,2})"
    def replacer(match):
        return format_period(match.group(1))
    return re.sub(pattern, replacer, text)

def extract_fish_name(user_input, fish_list):
    # fish_list에 포함된 이름 중 입력에 포함된 것을 찾음
    for name in fish_list:
        if name in user_input:
            return name
    # 별칭 제거도 고려하며
    fish_name = user_input
    for suffix in [" 금어기 알려줘", " 금어기", " 알려줘"]:
        if fish_name.endswith(suffix):
            fish_name = fish_name.replace(suffix, "").strip()
            break
    return fish_name

@app.route("/TAC", methods=["POST"])
def fishbot():
    body = request.get_json()
    user_input = body["userRequest"]["utterance"].strip()
    today = datetime.today()
    주요_어종 = list(fish_data.keys())

    if "현재 금어기" in user_input or "오늘 금어기" in user_input:
        result = []
        for name, data in fish_data.items():
            for key in ["금어기", "유자망_금어기", "근해채낚기_연안복합_정치망_금어기", "지역별_금어기", "금어기_예외"]:
                if key in data and filter_periods(data[key], today):
                    result.append(name)
                    break
        if result:
            # 대표명 기준으로 중복 제거
            normalized = {normalize_fish_name(n) for n in result}
            normalized_list = list(normalized)
            answer = f"🌟 오늘 금어기 중인 어종:\n" + ", ".join(sorted(normalized_list))
            buttons = [{"label": name, "action": "message", "messageText": name} for name in normalized_list]
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

    if "월 금어기" in user_input:
        match = re.search(r"(\d{1,2})월", user_input)
        if match:
            month = int(match.group(1))
            raw_result = []
            for name, data in fish_data.items():
                for key in ["금어기", "유자망_금어기", "근해채낚기_연안복합_정치망_금어기", "지역별_금어기", "금어기_예외"]:
                    if key in data:
                        periods = data[key]
                        if isinstance(periods, dict):
                            for p in periods.values():
                                if p.startswith(f"{month}.") or f"~{month}." in p:
                                    raw_result.append(name)
                                    break
                        elif isinstance(periods, str):
                            if periods.startswith(f"{month}.") or f"~{month}." in periods:
                                raw_result.append(name)
                                break
            normalized = {normalize_fish_name(n) for n in raw_result}
            result = list(normalized)

            if result:
                answer = f"📅 {month}월 금어기 어종:\n" + ", ".join(sorted(result))
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

    fish_name_raw = extract_fish_name(user_input, 주요_어종)
    fish_name_rep = normalize_fish_name(fish_name_raw)
    display_name = get_display_name(fish_name_raw)

    info = get_fish_info(fish_name_rep, fish_data)

    return jsonify({
        "version": "2.0",
        "template": {
            "outputs": [{"simpleText": {"text": f"🐟{display_name}🐟\n\n{info}"}}],
            "quickReplies": []
        }
    })

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)