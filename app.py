from flask import Flask, request, jsonify
from datetime import datetime
import re
import logging
import os

from fish_data import fish_data
from fish_utils import get_fish_info, convert_period_format  # utils.py 내 함수

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)

# 환경 변수
OPENROUTER_API_KEY = os.environ.get("OPENROUTER_API_KEY")
OPENROUTER_API_URL = "https://openrouter.ai/api/v1/chat/completions"

# 금어기 관련 키워드
TODAY_CLOSED_KEYWORDS = ["현재 금어기", "지금 금어기", "오늘 금어기", "오늘의 금어기", "금어기 어종"]
MONTH_CLOSED_KEYWORD = "월 금어기"

# 어종별 별칭 (소문자 키)
fish_aliases = {
    # 원본 fish_data 키 혹은 별칭들
    "문치가자미": "문치가자미",
    "감성돔": "감성돔",
    "돌돔": "돌돔",
    "참돔": "참돔",
    "넙치": "넙치(광어)",
    "광어": "넙치(광어)",
    "농어": "농어",
    "대구": "대구",
    "도루묵": "도루묵",
    "민어": "민어",
    "방어": "방어",
    "볼락": "볼락",
    "붕장어": "붕장어",
    "조피볼락": "조피볼락(우럭)",
    "우럭": "조피볼락(우럭)",
    "쥐노래미": "쥐노래미",
    "참홍어": "참홍어",
    "갈치": "갈치",
    "고등어": "고등어",
    "참조기": "참조기",
    "말쥐치": "말쥐치",
    "갯장어": "갯장어",
    "미거지": "미거지",
    "청어": "청어",
    "꽃게": "꽃게",
    "대게": "대게",
    "붉은대게": "붉은대게",
    "소라": "제주소라",
    "제주소라": "제주소라",
    "오분자기": "오분자기",
    "전복류": "전복(전복류)",
    "전복": "전복(전복류)",
    "키조개": "키조개",
    "기수재첩": "기수재첩",
    "넓미역": "넓미역",
    "우뭇가사리": "우뭇가사리",
    "톳": "톳",
    "대문어": "대문어",
    "살오징어": "살오징어(오징어)",
    "오징어": "살오징어(오징어)",
    "낙지": "낙지",
    "주꾸미": "주꾸미",
    "쭈꾸미": "주꾸미",
    "참문어": "참문어",
    "해삼": "해삼",
}

# 사용자에게 보여줄 어종명 맵핑
display_name_map = {
    "조피볼락(우럭)": "조피볼락",
    "넙치(광어)": "넙치",
    "살오징어(오징어)": "살오징어",
    "제주소라": "제주소라",
    "전복(전복류)": "전복",
}

# 어종별 이모지 맵핑
fish_emojis = {
    "대게": "🦀",
    "붉은대게": "🦀",
    "오분자기": "🐚",
    "키조개": "🦪",
    "주꾸미": "🐙",
    "대문어": "🐙",
    "참문어": "🐙",
    "꽃게": "🦀",
    "해삼": "🌊",
    "미역":"🌿",
    "넓미역":"🌿",
    "우뭇가사리": "🌿",
    "톳": "🌿",
    "제주소라": "🐚",
    "살오징어(오징어)": "🦑",
    "낙지": "🦑",
}

# 어종별 분류 맵핑
category_map = {
    "갈치": "어류",
    "문치가자미": "어류",
    "감성돔": "어류",
    "돌돔": "어류",
    "참돔": "어류",
    "농어": "어류",
    "대구": "어류",
    "도루묵": "어류",
    "민어": "어류",
    "방어": "어류",
    "볼락": "어류",
    "붕장어": "어류",
    "말쥐치": "어류",
    "쥐노래미": "어류",
    "말쥐치": "어류",
    "고등어": "어류",
    "갯장어": "어류",
    "미거지": "어류",
    "청어": "어류",
    "말쥐치": "어류",
    "참조기": "어류",
    "참홍어": "어류",
    "조피볼락(우럭)": "어류",
    "넙치(광어)": "어류",
    "살오징어(오징어)": "두족류",
    "낙지": "두족류",
    "참문어": "두족류",
    "주꾸미": "두족류",
    "대문어": "두족류",
    "오분자기": "폐류",
    "제주소라": "폐류",
    "키조개": "폐류",
    "전복(전복류)": "폐류",
    "대게": "갑각류",
    "붉은대게": "갑각류",
    "게": "갑각류",
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

def normalize_fish_name(text):
    text = text.lower()
    text = re.sub(r"\(.*?\)", "", text)
    text = re.sub(r"[^\uAC00-\uD7A3a-zA-Z0-9]", "", text)

    all_names = set(fish_data.keys()) | set(fish_aliases.keys())
    for name in sorted(all_names, key=lambda x: -len(x)):
        name_key = re.sub(r"\(.*?\)", "", name.lower())
        name_key = re.sub(r"[^\uAC00-\uD7A3a-zA-Z0-9]", "", name_key)
        if name_key in text:
            canonical = fish_aliases.get(name, name)
            if canonical in fish_data:
                return canonical
    return None

def is_date_in_range(period, today):
    try:
        start_str, end_str = period.split("~")
        start_month, start_day = map(int, start_str.strip().split("."))
        if "익년" in end_str:
            end_str = end_str.replace("익년", "").strip()
            end_month, end_day = map(int, end_str.split("."))
            end_year = today.year + 1
        else:
            end_month, end_day = map(int, end_str.strip().split("."))
            end_year = today.year
        start_date = datetime(today.year, start_month, start_day)
        end_date = datetime(end_year, end_month, end_day)
        return start_date <= today <= end_date
    except Exception as e:
        logger.error(f"is_date_in_range error: {e}")
        return False

def is_month_in_period(period, month):
    try:
        match = re.search(r"(\d{1,2})\.\d{1,2}\s*~\s*(\d{1,2})\.\d{1,2}", period)
        if not match:
            return False
        start_month = int(match.group(1))
        end_month = int(match.group(2))
        if start_month <= end_month:
            return start_month <= month <= end_month
        else:
            return month >= start_month or month <= end_month
    except Exception as e:
        logger.error(f"is_month_in_period error: {e}")
        return False

def group_fishes_by_category(fishes):
    grouped = {"어류": [], "두족류": [], "폐류": [], "갑각류": [], "기타": []}
    for fish in fishes:
        category = category_map.get(fish, "기타")
        grouped[category].append(fish)
    return grouped

def button_label(name):
    return display_name_map.get(name, re.sub(r"\(.*?\)", "", name))

def check_month_in_all_closed_periods(data, month):
    for key, value in data.items():
        if "금어기" in key and value:
            periods = value.values() if isinstance(value, dict) else [value]
            for period in periods:
                if "~" in period:
                    if is_month_in_period(period, month):
                        return True
    return False

def check_today_in_all_closed_periods(data, today):
    for key, value in data.items():
        if "금어기" in key and value:
            periods = value.values() if isinstance(value, dict) else [value]
            for period in periods:
                if "~" in period:
                    if is_date_in_range(period, today):
                        return True
    return False

@app.route("/TAC", methods=["POST"])
def fishbot():
    try:
        body = request.get_json()
        user_input = body.get("userRequest", {}).get("utterance", "").strip()
        logger.info(f"User input: {user_input}")

        today = datetime.today()

        # 오늘 금어기 어종 요청 처리
        if re.search(r"(오늘|지금).*(금어기)", user_input):
            today_closed = set()
            for name, data in fish_data.items():
                if check_today_in_all_closed_periods(data, today):
                    norm = normalize_fish_name(name)
                    if norm:
                        today_closed.add(norm)

            if not today_closed:
                return jsonify({
                    "version": "2.0",
                    "template": {"outputs": [{"simpleText": {"text": f"\ud83d\udcc5 \uc624\ub298({today.month}\uc6d4 {today.day}\uc77c) \uae08\uc5b4\uae30 \uc5b4\uc885\uc740 \uc5c6\uc2b5\ub2c8\ub2e4."}}]}
                })

            grouped = group_fishes_by_category(sorted(today_closed))
            ordered = grouped["\uc5b4\ub8cc"] + grouped["\ub450\uc875\ub958"] + grouped["\ud3ec\ub958"] + grouped["\uac11\uac01\ub958"] + grouped["\uae30\ud0c0"]

            lines = [f"\ud83d\udcc5 \uc624\ub298({today.month}\uc6d4 {today.day}\uc77c) \uae08\uc5b4\uae30 \uc5b4\uc885:"]
            buttons = []
            for fish in ordered:
                disp = display_name_map.get(fish, fish)
                emoji = fish_emojis.get(fish, "\ud83d\udc1f")
                lines.append(f"- {emoji} {disp}")
                buttons.append({"label": button_label(fish), "action": "message", "messageText": disp})

            return jsonify({
                "version": "2.0",
                "template": {
                    "outputs": [{"simpleText": {"text": "\n".join(lines)}}],
                    "quickReplies": buttons
                }
            })

        # \uc6d4 \uae08\uc5b4\uae30 \uc9c8\ubb38 \ucc98\ub9ac
        if MONTH_CLOSED_KEYWORD in user_input:
            match = re.search(r"(\d{1,2})\uc6d4", user_input)
            if not match:
                return jsonify({
                    "version": "2.0",
                    "template": {"outputs": [{"simpleText": {"text": "\uc6d4 \uc815\ubcf4\ub97c \uc778\uc2dd\ud558\uc9c0 \ubabb\ud588\uc2b5\ub2c8\ub2e4. \uc608: '4\uc6d4 \uae08\uc5b4\uae30'"}}]}
                })

            month = int(match.group(1))
            monthly_closed = set()
            for name, data in fish_data.items():
                if check_month_in_all_closed_periods(data, month):
                    norm = normalize_fish_name(name)
                    if norm:
                        monthly_closed.add(norm)

            if not monthly_closed:
                return jsonify({
                    "version": "2.0",
                    "template": {"outputs": [{"simpleText": {"text": f"{month}\uc6d4 \uae08\uc5b4\uae30\uc778 \uc5b4\uc885\uc774 \uc5c6\uc2b5\ub2c8\ub2e4."}}]}
                })

            grouped = group_fishes_by_category(sorted(monthly_closed))
            ordered = grouped["\uc5b4\ub8cc"] + grouped["\ub450\uc875\ub958"] + grouped["\ud3ec\ub958"] + grouped["\uac11\uac01\ub958"] + grouped["\uae30\ud0c0"]

            lines = [f"\ud83d\udcc5 {month}\uc6d4 \uae08\uc5b4\uae30 \uc5b4\uc885:"]
            buttons = []
            for fish in ordered:
                disp = display_name_map.get(fish, fish)
                emoji = fish_emojis.get(fish, "\ud83d\udc1f")
                lines.append(f"- {emoji} {disp}")
                buttons.append({"label": button_label(fish), "action": "message", "messageText": disp})

            return jsonify({
                "version": "2.0",
                "template": {
                    "outputs": [{"simpleText": {"text": "\n".join(lines)}}],
                    "quickReplies": buttons
                }
            })

        # \uac1c\ubcc4 \uc5b4\uc885 \uc9c8\ubb38 \ucc98\ub9ac
        found_fish = normalize_fish_name(user_input)
        logger.info(f"Normalized fish: {found_fish}")

        if found_fish:
            try:
                info = get_fish_info(found_fish, fish_data)
                return jsonify({
                    "version": "2.0",
                    "template": {"outputs": [{"simpleText": {"text": info}}]}
                })
            except Exception as e:
                logger.exception(f"{found_fish} \ucc98\ub9ac \uc624\ub958: {e}")
                return jsonify({
                    "version": "2.0",
                    "template": {
                        "outputs": [{"simpleText": {"text": f"\u26a0\ufe0f '{found_fish}' \uc815\ubcf4\ub97c \ucc98\ub9ac\ud558\ub294 \uc911 \uc624\ub958\uac00 \ubc1c\uc0dd\ud588\uc2b5\ub2c8\ub2e4."}}]
                    }
                })

        # \uc5b4\uc885 \uc778\uc2dd \uc2e4\ud328
        cleaned = re.sub(r"(\uae08\uc5b4\uae30|\uae08\uc9c0\uccb4\uc7a5|\uc54c\ub824\uc8fc\uc138\uc694|\uc54c\ub824|\uc8fc\uc138\uc694|\uc815\ubcf4|\uc5b4\uc885|\uc870\ub9ac|\uc880|)", "", user_input).strip()
        display_name = cleaned if cleaned else user_input
        return jsonify({
            "version": "2.0",
            "template": {
                "outputs": [{
                    "simpleText": {
                        "text": f"\ud83e\udd14 '{display_name}'\uc758 \uae08\uc5b4\uae30 \ubc0f \uae08\uc9c0\uccb4\uc7a5 \uc815\ubcf4\uac00 \uc5c6\uc2b5\ub2c8\ub2e4.\n\uc5b4\uc885 \uc815\ubcf4\ub97c \ub2e4\uc2dc \ud655\uc778\ud574 \uc8fc\uc138\uc694."
                    }
                }]
            }
        })

    except Exception as e:
        logger.exception(f"fishbot \uc804\uccb4 \uc624\ub958: {e}")
        return jsonify({
            "version": "2.0",
            "template": {
                "outputs": [{"simpleText": {"text": "\u26a0\ufe0f \uc54c \uc218 \uc5c6\ub294 \uc624\ub958\uac00 \ubc1c\uc0dd\ud588\uc2b5\ub2c8\ub2e4. \uc7a0\uc2dc \ud6c4 \ub2e4\uc2dc \uc2dc\ub3c4\ud574 \uc8fc\uc138\uc694."}}]
            }
        })

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
