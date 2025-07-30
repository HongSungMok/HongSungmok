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
    print(f"원본 텍스트: {text}")  # 디버그용 출력
    text = re.sub(r"\(.*?\)", "", text)
    print(f"괄호 제거 후: {text}")
    text = re.sub(r"[^\uAC00-\uD7A3a-z0-9\s]", "", text)  # 띄어쓰기 유지
    print(f"특수문자 제거 후(띄어쓰기 유지): {text}")

    all_names = set(fish_data.keys()) | set(fish_aliases.keys())
    for name in sorted(all_names, key=lambda x: -len(x)):
        name_key = re.sub(r"\(.*?\)", "", name.lower())
        name_key = re.sub(r"[^\uAC00-\uD7A3a-z0-9\s]", "", name_key)  # 띄어쓰기 유지
        if name_key and name_key in text:
            print(f"매칭된 이름: {name} -> {fish_aliases.get(name, name)}")
            return fish_aliases.get(name, name)
    print("매칭 실패")
    return None

def get_display_name(fish_name):
    return display_name_map.get(fish_name, re.sub(r"\(.*?\)", "", fish_name))

def format_fish_info(fish_name, data):
    emoji = fish_emojis.get(fish_name, "🐟")
    display = get_display_name(fish_name)
    period = data.get("금어기", "없음")
    size = data.get("금지체장", "없음")
    exception = data.get("예외사항", "없음")
    ratio = data.get("포획비율제한", "없음")

    text = (
        f"{emoji} {display} {emoji}\n\n"
        f"🚫 금어기\n전국: {period}\n\n"
        f"📏 금지체장\n전국: {size}\n\n"
        f"⚠️ 예외사항: {exception}\n"
        f"⚠️ 포획비율제한: {ratio}\n"
    )
    return text

def is_date_in_period(period, date):
    try:
        if not period or "~" not in period or "." not in period:
            return False

        if any(x in period for x in ["중", "이내", "이상", "범위"]):
            return False

        start_str, end_str = period.split("~")
        sm_sd = start_str.strip().split(".")
        em_ed = end_str.replace("익년", "").strip().split(".")

        if len(sm_sd) != 2 or len(em_ed) != 2:
            return False

        sm, sd = int(sm_sd[0]), int(sm_sd[1])
        em, ed = int(em_ed[0]), int(em_ed[1])
        ey = date.year + 1 if "익년" in end_str else date.year

        start_date = datetime(date.year, sm, sd)
        end_date = datetime(ey, em, ed)

        return start_date <= date <= end_date
    except Exception as e:
        logger.error(f"is_date_in_period error: {e}")
        return False

def get_fishes_in_today_ban(fish_data, today):
    fishes = []
    for name, data in fish_data.items():
        period = data.get("금어기")
        if period and is_date_in_period(period, today):
            fishes.append(name)
    return fishes

def group_by_category(fish_list):
    grouped = {"어류": [], "두족류": [], "폐류": [], "갑각류": [], "기타": []}
    for f in fish_list:
        category = category_map.get(f, "기타")
        grouped[category].append(f)
    return grouped

def build_response(text, buttons=None):
    response = {
        "version": "2.0",
        "template": {
            "outputs": [{"simpleText": {"text": text}}]
        }
    }
    if buttons:
        response["template"]["quickReplies"] = buttons
    return response

@app.route("/TAC", methods=["POST"])
def fishbot():
    try:
        req = request.get_json()
        user_text = req.get("userRequest", {}).get("utterance", "").strip()
        today = datetime.today()
        logger.info(f"사용자 입력: {user_text}")

        # 오늘 금어기 문의
        if re.search(r"(오늘|지금|현재|금일|투데이).*(금어기)", user_text):
            fishes = get_fishes_in_today_ban(fish_data, today)
            if not fishes:
                return jsonify(build_response(f"📅 오늘({today.month}월 {today.day}일) 금어기 어종은 없습니다."))

            normalized = [normalize_fish_name(f) or f for f in fishes]
            grouped = group_by_category(normalized)
            ordered = grouped["어류"] + grouped["두족류"] + grouped["폐류"] + grouped["갑각류"] + grouped["기타"]

            lines = [f"📅 오늘({today.month}월 {today.day}일) 금어기 어종:"]
            buttons = []
            for f in ordered:
                disp = get_display_name(f)
                emoji = fish_emojis.get(f, "🐟")
                lines.append(f"- {emoji} {disp}")
                buttons.append({"label": disp, "action": "message", "messageText": disp})

            return jsonify(build_response("\n".join(lines), buttons=buttons))

        # 월별 금어기 문의 (ex: 5월 금어기)
        m = re.search(r"(\d{1,2})월.*금어기", user_text)
        if m:
            month = int(m.group(1))
            monthly_fish = []
            for name, data in fish_data.items():
                period = data.get("금어기")
                if not period or "~" not in period:
                    continue
                try:
                    sm = int(period.split("~")[0].strip().split(".")[0])
                    em = int(period.split("~")[1].replace("익년", "").strip().split(".")[0])
                except Exception as e:
                    logger.error(f"월별 금어기 파싱 오류: {e}")
                    continue

                if sm <= em:
                    if sm <= month <= em:
                        monthly_fish.append(name)
                else:
                    # 연말 ~ 익년 넘어가는 경우
                    if month >= sm or month <= em:
                        monthly_fish.append(name)

            if not monthly_fish:
                return jsonify(build_response(f"📅 {month}월 금어기인 어종이 없습니다."))

            normalized = [normalize_fish_name(f) or f for f in monthly_fish]
            grouped = group_by_category(normalized)
            ordered = grouped["어류"] + grouped["두족류"] + grouped["폐류"] + grouped["갑각류"] + grouped["기타"]

            lines = [f"📅 {month}월 금어기 어종:"]
            buttons = []
            for f in ordered:
                disp = get_display_name(f)
                emoji = fish_emojis.get(f, "🐟")
                lines.append(f"- {emoji} {disp}")
                buttons.append({"label": disp, "action": "message", "messageText": disp})

            return jsonify(build_response("\n".join(lines), buttons=buttons))

# 어종명 인식 및 상세정보 조회
fish_norm = normalize_fish_name(user_text)
if fish_norm and fish_norm in fish_data:
    text = format_fish_info(fish_norm, fish_data[fish_norm])
    return jsonify(build_response(text))

try:
        # 어종명 인식 및 상세정보 조회
        fish_norm = normalize_fish_name(user_text)
        if fish_norm and fish_norm in fish_data:
            text = format_fish_info(fish_norm, fish_data[fish_norm])
            return jsonify(build_response(text))

        # 어종 인식 실패 또는 데이터 없을 때만 버튼과 안내문
        disp_name = get_display_name(fish_norm) if fish_norm else user_text
        body = (
            f"🐟 {disp_name} 🐟\n\n"
            "🚫 금어기\n전국: 없음\n\n"
            "📏 금지체장\n전국: 없음\n\n"
            "⚠️ 예외사항: 없음\n"
            "⚠️ 포획비율제한: 없음\n\n"
            "✨ 오늘의 금어기를 알려드릴까요?"
        )
        buttons = [
            {
                "label": "오늘의 금어기",
                "action": "message",
                "messageText": "오늘 금어기"
            }
        ]
        return jsonify(build_response(body, buttons=buttons))

    except Exception as e:
        logger.error(f"fishbot error: {e}")
        return jsonify(build_response("⚠️ 오류가 발생했습니다. 잠시 후 다시 시도해 주세요."))

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)