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

# 기간 내 포함 여부
def is_month_in_period(period, month):
    try:
        match = re.search(r"(\d{1,2})\.\d{1,2}\s*~\s*(\d{1,2})\.\d{1,2}", period)
        if not match:
            return False
        start_month = int(match.group(1))
        end_month = int(match.group(2))
        return start_month <= month <= end_month if start_month <= end_month else month >= start_month or month <= end_month
    except Exception as e:
        logger.error(f"is_month_in_period error: {e}")
        return False

# 월 기준 금어기 확인
def check_month_in_all_closed_periods(data, month):
    for key, value in data.items():
        if "금어기" in key and value:
            periods = value.values() if isinstance(value, dict) else [value]
            for period in periods:
                if "~" in period and is_month_in_period(period, month):
                    return True
    return False

# 어종 그룹 분류
def group_fishes_by_category(fishes):
    grouped = {"어류": [], "두족류": [], "폐류": [], "갑각류": [], "기타": []}
    for fish in fishes:
        category = category_map.get(fish, "기타")
        grouped[category].append(fish)
    return grouped

# 버튼 표시 이름
def button_label(name):
    return display_name_map.get(name, re.sub(r"\(.*?\)", "", name))

@app.route("/TAC", methods=["POST"])
def fishbot():
    try:
        body = request.get_json()
        user_input = body.get("userRequest", {}).get("utterance", "").strip()
        logger.info(f"User input: {user_input}")

        today = datetime.today()

        # 월 금어기 질의
        if MONTH_CLOSED_KEYWORD in user_input:
            match = re.search(r"(\d{1,2})월", user_input)
            if not match:
                return jsonify({
                    "version": "2.0",
                    "template": {"outputs": [{"simpleText": {"text": "월 정보를 인식하지 못했습니다. 예: '4월 금어기'"}}]}
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
                    "template": {"outputs": [{"simpleText": {"text": f"{month}월 금어기인 어종이 없습니다."}}]}
                })

            grouped = group_fishes_by_category(sorted(monthly_closed))
            ordered = grouped["어류"] + grouped["두족류"] + grouped["폐류"] + grouped["갑각류"] + grouped["기타"]

            lines = [f"📅 {month}월 금어기 어종:"]
            buttons = []
            for fish in ordered:
                disp = display_name_map.get(fish, fish)
                emoji = fish_emojis.get(fish, "🐟")
                lines.append(f"- {emoji} {disp}")
                buttons.append({"label": button_label(fish), "action": "message", "messageText": disp})

            return jsonify({
                "version": "2.0",
                "template": {
                    "outputs": [{"simpleText": {"text": "\n".join(lines)}}],
                    "quickReplies": buttons
                }
            })

        # 개별 어종 정보 조회
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
                logger.exception(f"{found_fish} 처리 오류: {e}")
                return jsonify({
                    "version": "2.0",
                    "template": {"outputs": [{"simpleText": {"text": f"⚠️ '{found_fish}' 정보를 처리 중 오류가 발생했습니다."}}]}
                })

        # 어종이 존재하지 않는 경우 → 기본 응답
        cleaned = re.sub(r"(금어기|금지체장|알려줘|알려|주세요|정보|어종|좀|)", "", user_input).strip()
        display_name = cleaned if cleaned else user_input
        return jsonify({
            "version": "2.0",
            "template": {
                "outputs": [{
                    "simpleText": {
                        "text": f"🔍 {display_name} 🔍\n\n🚫 금어기\n전국: 없음\n\n📏 금지체장\n전국: 없음"
                    }
                }]
            }
        })

    except Exception as e:
        logger.exception(f"fishbot 전체 오류: {e}")
        return jsonify({
            "version": "2.0",
            "template": {"outputs": [{"simpleText": {"text": "⚠️ 알 수 없는 오류가 발생했습니다. 잠시 후 다시 시도해 주세요."}}]}
        })

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)