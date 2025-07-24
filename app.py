from flask import Flask, request, jsonify
from datetime import datetime
import re
import logging
import os

from fish_data import fish_data
from fish_utils import get_fish_info  # fish_data 기반 정보 포맷 함수

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)

OPENROUTER_API_KEY = os.environ.get("OPENROUTER_API_KEY")
OPENROUTER_API_URL = "https://openrouter.ai/api/v1/chat/completions"

# 키워드 상수
TODAY_CLOSED_KEYWORDS = ["현재 금어기", "오늘 금어기", "오늘의 금어기", "금어기 어종"]
MONTH_CLOSED_KEYWORD = "월 금어기"

# 별칭 및 표시명 통합 딕셔너리 (소문자 키)
fish_aliases = {
    '우럭': '조피볼락(우럭)',
    '광어': '넙치(광어)',
    '오징어': '살오징어(오징어)',
    '전복': '전복(전복류)',
    '전복류': '전복(전복류)',
    '볼락': '볼락',
    '조피볼락': '조피볼락(우럭)',
    '소라': '제주소라',
    '제주소라': '제주소라',
}

display_name_map = {
    "조피볼락(우럭)": "조피볼락(우럭)",
    "넙치(광어)": "넙치(광어)",
    "살오징어(오징어)": "살오징어(오징어)",
    "제주소라": "제주소라(소라)"
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
    "해삼": "🌊",
    "제주소라": "🐚",
    "살오징어(오징어)": "🦑",
}

category_map = {
    "갈치": "어류",
    "말쥐치": "어류",
    "참조기": "어류",
    "참홍어": "어류",
    "조피볼락(우럭)": "어류",
    "넙치(광어)": "어류",

    "살오징어(오징어)": "두족류",
    "낙지": "두족류",
    "참문어": "두족류",
    "쭈꾸미": "두족류",
    "대문어": "두족류",

    "오분자기": "폐류",
    "제주소라(소라)": "폐류",
    "키조개": "폐류",
    "전복(전복류)": "폐류",

    "대게": "게류",
    "붉은대게": "게류",
    "게": "게류",

    "해삼": "기타",
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
            end_str = end_str.replace("익년", "").strip()
            end_month, end_day = map(int, end_str.split("."))
            start_date = datetime(today.year, start_month, start_day)
            end_date = datetime(today.year + 1, end_month, end_day)
        else:
            end_month, end_day = map(int, end_str.strip().split("."))
            start_date = datetime(today.year, start_month, start_day)
            end_date = datetime(today.year, end_month, end_day)
        return start_date <= today <= end_date
    except Exception as e:
        logger.error(f"is_date_in_range error for period '{period}': {e}")
        return False

def is_month_in_period(period: str, month: int) -> bool:
    try:
        # '숫자.숫자~숫자.숫자' 형태만 추출
        match = re.search(r"(\d{1,2})\.\d{1,2}\s*~\s*(\d{1,2})\.\d{1,2}", period)
        if not match:
            return False
        start_month = int(match.group(1))
        end_month = int(match.group(2))
        if start_month <= end_month:
            return start_month <= month <= end_month
        else:
            # 예) 11월~2월 같이 연도 넘는 경우
            return month >= start_month or month <= end_month
    except Exception as e:
        logger.error(f"is_month_in_period error for period '{period}': {e}")
        return False

def normalize_fish_name(name):
    return fish_aliases.get(name.strip().lower(), name.strip())

def extract_fish_name(user_input, fish_names):
    # fish_names는 대표 표준명 리스트 (ex: '조피볼락(우럭)')
    for name in fish_names:
        if name in user_input:
            return name
    for alias in fish_aliases:
        if alias in user_input:
            return fish_aliases[alias]
    return None

def get_display_name(name):
    return display_name_map.get(name, name)

@app.route("/TAC", methods=["POST"])
def fishbot():
    body = request.get_json()
    user_input = body.get("userRequest", {}).get("utterance", "").strip()
    logger.info(f"Received user input: {user_input}")

    today = datetime.today()
    fish_names = list(fish_data.keys())

    # 오늘 금어기 질문 처리
    if any(k in user_input for k in TODAY_CLOSED_KEYWORDS):
        closed_today = []
        for name, data in fish_data.items():
            for key in data:
                if "금어기" in key:
                    period = data[key]
                    periods = period.values() if isinstance(period, dict) else [period]
                    if any(is_date_in_range(p, today) for p in periods):
                        closed_today.append(name)
                        break

        closed_today_norm = sorted(set(normalize_fish_name(f) for f in closed_today))
        fish_grouped = {"어류": [], "폐류": [], "게류": [], "기타": []}
        for fish in closed_today_norm:
            cat = category_map.get(fish, "기타")
            fish_grouped[cat].append(fish)

        ordered_list = fish_grouped["어류"] + fish_grouped["폐류"] + fish_grouped["게류"] + fish_grouped["기타"]

        if not ordered_list:
            return jsonify({
                "version": "2.0",
                "template": {
                    "outputs": [{"simpleText": {"text": f"오늘({today.month}월 {today.day}일) 금어기인 어종이 없습니다."}}]
                }
            })

        lines = [f"📅 오늘({today.month}월 {today.day}일) 금어기인 어종:"]
        buttons = []
        for fish in ordered_list:
            disp = get_display_name(fish)
            emoji = fish_emojis.get(fish, "🐟")
            lines.append(f"- {emoji} {disp}")
            buttons.append({"label": disp, "action": "message", "messageText": disp})

        return jsonify({
            "version": "2.0",
            "template": {
                "outputs": [{"simpleText": {"text": "\n".join(lines)}}],
                "quickReplies": buttons
            }
        })

    # 월 금어기 질문 처리
    if MONTH_CLOSED_KEYWORD in user_input:
        match = re.search(r"(\d{1,2})월", user_input)
        if not match:
            return jsonify({
                "version": "2.0",
                "template": {
                    "outputs": [{"simpleText": {"text": "월 정보를 인식하지 못했습니다. 예: '4월 금어기'"} }],
                    "quickReplies": []
                }
            })
        month = int(match.group(1))

        monthly_closed = []
        for name, data in fish_data.items():
            for key in data:
                if "금어기" in key:
                    period = data[key]
                    if isinstance(period, dict):
                        periods = [p for p in period.values() if isinstance(p, str) and p.strip()]
                    elif isinstance(period, str) and period.strip():
                        periods = [period]
                    else:
                        periods = []
                    if any(is_month_in_period(p, month) for p in periods):
                        monthly_closed.append(name)
                        break

        if not monthly_closed:
            return jsonify({
                "version": "2.0",
                "template": {
                    "outputs": [{"simpleText": {"text": f"{month}월 금어기인 어종이 없습니다."}}]
                }
            })

        closed_norm = sorted(set(normalize_fish_name(n) for n in monthly_closed))
        fish_grouped = {"어류": [], "폐류": [], "게류": [], "기타": []}
        for fish in closed_norm:
            cat = category_map.get(fish, "기타")
            fish_grouped[cat].append(fish)

        ordered_list = fish_grouped["어류"] + fish_grouped["폐류"] + fish_grouped["게류"] + fish_grouped["기타"]

        lines = [f"📅 {month}월 금어기 어종:"]
        buttons = []
        for fish in ordered_list:
            disp = get_display_name(fish)
            emoji = fish_emojis.get(fish, "🐟")
            lines.append(f"- {emoji} {disp}")
            buttons.append({"label": disp, "action": "message", "messageText": disp})

        return jsonify({
            "version": "2.0",
            "template": {
                "outputs": [{"simpleText": {"text": "\n".join(lines)}}],
                "quickReplies": buttons
            }
        })

    # 어종 상세정보 요청 처리
    fish_name_raw = extract_fish_name(user_input, fish_names)
    if fish_name_raw is None:
        return jsonify({
            "version": "2.0",
            "template": {
                "outputs": [{"simpleText": {"text": "죄송합니다, 해당 어종을 찾을 수 없습니다. 다시 입력해주세요."}}],
                "quickReplies": []
            }
        })

    fish_name_rep = normalize_fish_name(fish_name_raw)
    display_name = get_display_name(fish_name_rep)
    emoji = fish_emojis.get(fish_name_rep, "🐟")
    info = get_fish_info(fish_name_rep, fish_data, today)

    return jsonify({
        "version": "2.0",
        "template": {
            "outputs": [{"simpleText": {"text": f"{emoji} {display_name} {emoji}\n\n{info.strip()}"}}],
            "quickReplies": []
        }
    })


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)