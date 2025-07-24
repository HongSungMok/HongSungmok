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
    "낙지": "🦑",
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

def normalize_fish_name(name):
    name = name.strip().lower()
    return fish_aliases.get(name, name).strip()

def get_representative_fish_names():
    """fish_data 키 전부를 대표명으로 변환해 중복 없이 리스트 반환"""
    rep_set = set()
    for key in fish_data.keys():
        rep = normalize_fish_name(key)
        rep_set.add(rep)
    return list(rep_set)

def button_label(name):
    """대표명에서 괄호 제거: '살오징어(오징어)' -> '살오징어'"""
    return re.sub(r"\(.*?\)", "", name)

def convert_period_format(period):
    try:
        start, end = period.split("~")
        start_m, start_d = start.strip().split(".")
        end_m, end_d = end.strip().split(".")
        return f"{int(start_m)}월{int(start_d)}일 ~ {int(end_m)}월{int(end_d)}일"
    except Exception:
        return period

def format_period_dict(period_dict):
    lines = []
    for region, period in period_dict.items():
        lines.append(f"{region}: {convert_period_format(period)}")
    return "\n".join(lines)

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
        logger.error(f"is_month_in_period error for period '{period}': {e}")
        return False

def get_fish_info(fish_name, fish_data, today):
    # fish_name은 대표명 (예: '넙치(광어)')
    # fish_data 키는 원본 키라서 대표명과 매칭되는 모든 원본 키에 대해 info 수집 후 통합
    # 예: '넙치(광어)' → '넙치', '광어' 두 키 정보 모두 합침

    # 대표명에서 괄호 안 별칭 추출
    alias_match = re.search(r"\((.*?)\)", fish_name)
    aliases = []
    if alias_match:
        aliases.append(alias_match.group(1))
    base_name = re.sub(r"\(.*?\)", "", fish_name)

    keys_to_check = [base_name] + aliases

    combined = {}
    # 여러 키 중 정보가 있을 경우, 우선순위로 병합 (금어기, 금지체장 등)
    for key in keys_to_check:
        key = key.strip()
        data = fish_data.get(key)
        if not data:
            continue
        for k, v in data.items():
            if k not in combined:
                combined[k] = v
            else:
                # 금어기, 금지체장 같이 중복 항목이 있으면 병합 또는 우선순위 처리
                if isinstance(v, str) and isinstance(combined[k], str):
                    if k == "금어기" or k == "금지체장":
                        # 중복 금어기 병합 시 쉼표로 연결(중복 제거)
                        parts = set(map(str.strip, combined[k].split(',')))
                        parts.update(map(str.strip, v.split(',')))
                        combined[k] = ", ".join(sorted(parts))
                # dict 병합 등 필요시 확장 가능

    lines = []

    # 금어기 표시
    closed = combined.get("금어기", "정보없음")
    if closed == "정보없음":
        lines.append("🚫 금어기: 정보없음")
    else:
        lines.append(f"🚫 금어기: {convert_period_format(closed)}" if isinstance(closed, str) else "🚫 금어기:")
        if isinstance(closed, dict):
            lines.append(format_period_dict(closed))

    # 금지체장 표시
    size_limit = combined.get("금지체장", None)
    if size_limit:
        if isinstance(size_limit, dict):
            lines.append("\n📏 금지체장:")
            lines.append(format_period_dict(size_limit))
        else:
            lines.append(f"\n📏 금지체장: {size_limit}")
    else:
        lines.append("\n📏 금지체장: 없음")

    # 예외사항
    exceptions = combined.get("예외사항", "없음")
    lines.append(f"\n⚠️ 예외사항: {exceptions}")

    # 포획비율 제한
    ratio = combined.get("포획비율제한", "없음")
    lines.append(f"⚠️ 포획비율제한: {ratio}")

    return "\n".join(lines)

def group_fishes_by_category(fishes):
    grouped = {"어류": [], "두족류": [], "폐류": [], "게류": [], "기타": []}
    for fish in fishes:
        category = category_map.get(fish, "기타")
        grouped.setdefault(category, []).append(fish)
    return grouped

@app.route("/TAC", methods=["POST"])
def fishbot():
    body = request.get_json()
    user_input = body.get("userRequest", {}).get("utterance", "").strip()
    logger.info(f"Received user input: {user_input}")

    today = datetime.today()

    # 1) 오늘 금어기 요청 처리
    if any(k in user_input for k in TODAY_CLOSED_KEYWORDS):
        closed_today = []
        seen = set()
        for name, data in fish_data.items():
            for key in data:
                if "금어기" in key:
                    period = data[key]
                    periods = period.values() if isinstance(period, dict) else [period]
                    if any(is_date_in_range(p, today) for p in periods):
                        norm = normalize_fish_name(name)
                        if norm not in seen:
                            closed_today.append(norm)
                            seen.add(norm)
                        break

        if not closed_today:
            return jsonify({
                "version": "2.0",
                "template": {"outputs": [{"simpleText": {"text": f"오늘({today.month}월 {today.day}일) 금어기인 어종이 없습니다."}}]}
            })

        normalized = sorted(set(closed_today))
        grouped = group_fishes_by_category(normalized)
        ordered = grouped["어류"] + grouped["두족류"] + grouped["폐류"] + grouped["게류"] + grouped["기타"]

        lines = [f"📅 오늘({today.month}월 {today.day}일) 금어기인 어종:"]
        buttons = []
        for fish in ordered:
            disp = display_name_map.get(fish, fish)
            emoji = fish_emojis.get(fish, "🐟")
            lines.append(f"- {emoji} {disp}")
            buttons.append({"label": button_label(disp), "action": "message", "messageText": disp})

        return jsonify({
            "version": "2.0",
            "template": {
                "outputs": [{"simpleText": {"text": "\n".join(lines)}}],
                "quickReplies": buttons
            }
        })

    # 2) 월 금어기 요청 처리
    if MONTH_CLOSED_KEYWORD in user_input:
        match = re.search(r"(\d{1,2})월", user_input)
        if not match:
            return jsonify({
                "version": "2.0",
                "template": {"outputs": [{"simpleText": {"text": "월 정보를 인식하지 못했습니다. 예: '4월 금어기'"}}]}
            })
        month = int(match.group(1))

        monthly_closed = []
        seen = set()
        for name, data in fish_data.items():
            for key in data:
                if "금어기" in key:
                    period = data[key]
                    periods = period.values() if isinstance(period, dict) else [period]
                    if any(is_month_in_period(p, month) for p in periods):
                        norm = normalize_fish_name(name)
                        if norm not in seen:
                            monthly_closed.append(norm)
                            seen.add(norm)
                        break

        if not monthly_closed:
            return jsonify({
                "version": "2.0",
                "template": {"outputs": [{"simpleText": {"text": f"{month}월 금어기인 어종이 없습니다."}}]}
            })

        normalized = sorted(set(monthly_closed))
        grouped = group_fishes_by_category(normalized)
        ordered = grouped["어류"] + grouped["두족류"] + grouped["폐류"] + grouped["게류"] + grouped["기타"]

        lines = [f"📅 {month}월 금어기 어종:"]
        buttons = []
        for fish in ordered:
            disp = display_name_map.get(fish, fish)
            emoji = fish_emojis.get(fish, "🐟")
            lines.append(f"- {emoji} {disp}")
            buttons.append({"label": button_label(disp), "action": "message", "messageText": disp})

        return jsonify({
            "version": "2.0",
            "template": {
                "outputs": [{"simpleText": {"text": "\n".join(lines)}}],
                "quickReplies": buttons
            }
        })

    # 3) 특정 어종 상세정보 요청 처리
    # fish_data 키 (원본 이름) 목록
    fish_names = list(fish_data.keys())

    # 입력에서 어종명 추출 (별칭 및 원본 키 모두 검색)
    found_fish = None
    lowered_input = user_input.lower()
    for key in fish_names:
        if key in user_input:
            found_fish = key
            break
    if not found_fish:
        for alias, rep in fish_aliases.items():
            if alias in lowered_input:
                found_fish = alias
                break

    if not found_fish:
        return jsonify({
            "version": "2.0",
            "template": {"outputs": [{"simpleText": {"text": "죄송합니다, 해당 어종을 찾을 수 없습니다. 다시 입력해주세요."}}]}
        })

    rep_name = normalize_fish_name(found_fish)
    disp_name = display_name_map.get(rep_name, rep_name)
    emoji = fish_emojis.get(rep_name, "🐟")
    info = get_fish_info(rep_name, fish_data, today)

    return jsonify({
        "version": "2.0",
        "template": {
            "outputs": [{"simpleText": {"text": f"{emoji} {disp_name} {emoji}\n\n{info.strip()}"}}],
            "quickReplies": []
        }
    })

if __name__ == "__main__":
    import os
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)