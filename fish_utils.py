import re
import logging
from datetime import datetime
from fish_data import fish_data

logger = logging.getLogger(__name__)

# 어종명 정규화 매핑
fish_name_aliases = {
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
    "쭈구미": "주꾸미",
    "참문어": "참문어",
    "해삼": "해삼",
}

def clean_input(text: str) -> str:
    noise_keywords = [
        "금어기", "금지체장", "금지체중", "체장", "체중", "크기", "사이즈",
        "정보", "알려줘", "좀", "요", "?", ".", " "
    ]
    text = text.lower()
    for kw in noise_keywords:
        text = text.replace(kw, "")
    return text.strip()

def normalize_fish_name(user_input: str) -> str:
    cleaned = clean_input(user_input)
    for alias in sorted(fish_name_aliases.keys(), key=len, reverse=True):
        if alias in cleaned:
            return fish_name_aliases[alias]
    return cleaned

def convert_period_format(period: str) -> str:
    try:
        if not period or "~" not in period:
            return "없음"
        start, end = period.split("~")
        sm, sd = map(int, start.strip().split("."))
        start_fmt = f"{sm}월{sd}일"
        if "익년" in end:
            end = end.replace("익년", "").strip()
            em, ed = map(int, end.split("."))
            end_fmt = f"익년 {em}월{ed}일"
        else:
            em, ed = map(int, end.strip().split("."))
            end_fmt = f"{em}월{ed}일"
        return f"{start_fmt} ~ {end_fmt}"
    except Exception as e:
        logger.warning(f"[convert_period_format] {period} 변환 오류: {e}")
        return period

def get_fish_info(fish_name: str, fish_data: dict):
    fish = fish_data.get(fish_name)
    display_name = fish_name

    emoji = "🐟"
    if "전복" in fish_name or "소라" in fish_name:
        emoji = "🐚"
    elif "오징어" in fish_name:
        emoji = "🦑"
    elif any(x in fish_name for x in ["주꾸미", "문어", "낙지"]):
        emoji = "🐙"
    elif "게" in fish_name:
        emoji = "🦀"
    elif any(x in fish_name for x in ["미역", "우뭇가사리", "톳"]):
        emoji = "🌿"

    header = f"{emoji} {display_name} {emoji}\n\n"

    if not fish:
        body = (
            "🚫 금어기\n"
            "전국: 없음\n\n"
            "📏 금지체장\n"
            "전국: 없음\n\n"
            "⚠️ 예외사항: 없음\n"
            "⚠️ 포획비율제한: 없음"
        )
        buttons = [
            {
                "label": "오늘의 금어기",
                "action": "message",
                "messageText": "오늘 금어기"
            }
        ]
        return header + body, buttons

    # 금어기
    total_ban = convert_period_format(fish.get("금어기"))
    region_bans = [
        (k.replace("_금어기", "").replace("_", " "), v)
        for k, v in fish.items()
        if k.endswith("_금어기") and k != "금어기"
    ]
    printed_keys = {k for k, _ in region_bans}

    # 금지체장 또는 금지체중
    total_size = fish.get("금지체장") or fish.get("금지체중")
    size_type = "📏 금지체장" if "금지체장" in fish else ("⚖️ 금지체중" if "금지체중" in fish else "📏 금지체장")
    region_sizes = [
        (k.replace("_금지체장", "").replace("_금지체중", "").replace("_", " "), v)
        for k, v in fish.items()
        if k.endswith("_금지체장") or k.endswith("_금지체중")
    ]

    # 예외사항
    exception = fish.get("금어기_예외") or fish.get("예외사항") or "없음"
    ratio = fish.get("포획비율제한", "없음")

    # 본문 조립
    body = f"🚫 금어기\n전국: {total_ban}\n"
    for region, period in region_bans:
        body += f"{region}: {convert_period_format(period)}\n"
    body += "\n"

    body += f"{size_type}\n전국: {total_size if total_size else '없음'}\n"
    for region, val in region_sizes:
        body += f"{region}: {val}\n"
    body += "\n"

    # 기타 필드 중복 없이 출력
    extra_keys = [
        "금어기_해역_특이사항", "금어기_특정해역", "금어기_추가",
        "지역별_금어기", "근해채낚기_연안복합_정치망_금어기",
        "근해채낚기, 연안복합, 정치망_금어기"
    ]
    for key in extra_keys:
        label = key.replace("_", " ")
        if key in fish and label not in printed_keys:
            body += f"⚠️ {label}: {convert_period_format(fish[key])}\n"
    body += "\n"

    body += f"⚠️ 예외사항: {exception}\n"
    body += f"⚠️ 포획비율제한: {ratio}"

    return header + body, []

def get_fishes_in_seasonal_ban(fish_data: dict, target_date: datetime = None):
    if target_date is None:
        target_date = datetime.today()
    md = (target_date.month, target_date.day)
    matched = []
    seen = set()

    for name, info in fish_data.items():
        period = info.get("금어기")
        if not isinstance(period, str) or "~" not in period:
            continue
        try:
            start, end = period.split("~")
            sm, sd = map(int, start.strip().split("."))
            if "익년" in end:
                em, ed = map(int, end.replace("익년", "").strip().split("."))
                in_range = md >= (sm, sd) or md <= (em, ed)
            else:
                em, ed = map(int, end.strip().split("."))
                if (sm, sd) <= (em, ed):
                    in_range = (sm, sd) <= md <= (em, ed)
                else:
                    in_range = md >= (sm, sd) or md <= (em, ed)

            if in_range:
                norm = normalize_fish_name(name)
                if norm not in seen:
                    matched.append(norm)
                    seen.add(norm)

        except Exception as e:
            logger.warning(f"[금어기 파싱 오류] {name}: {period} / {e}")
    return matched