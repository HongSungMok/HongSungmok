from datetime import datetime
import logging
import re

logger = logging.getLogger(__name__)

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

def convert_period_format(period):
    try:
        if period is None:
            return "없음"
        if isinstance(period, str):
            if "고시" in period or "없음" in period:
                return period
            start, end = period.split("~")
            start_m, start_d = start.strip().split(".")
            end = end.strip()
            if "익년" in end:
                end = end.replace("익년", "").strip()
                end_m, end_d = end.split(".")
                return f"{int(start_m)}월{int(start_d)}일 ~ 익년 {int(end_m)}월{int(end_d)}일"
            else:
                end_m, end_d = end.split(".")
                return f"{int(start_m)}월{int(start_d)}일 ~ {int(end_m)}월{int(end_d)}일"
        else:
            return str(period)
    except Exception:
        return str(period)

def format_period_dict(period_dict):
    lines = []
    for region, period in period_dict.items():
        # 콜론 대신 공백으로 구분해서 출력
        lines.append(f"{region} {convert_period_format(period)}")
    return "\n".join(lines)

def get_fish_info(fish_name, fish_data, today=None):
    if today is None:
        today = datetime.today()

    fish = fish_data.get(fish_name)
    if not fish:
        return (
            f"🚫 금어기\n"
            f"전국 없음\n\n"
            f"📏 금지체장\n"
            f"전국 없음\n\n"
            f"⚠️ 예외사항 없음\n"
            f"⚠️ 포획비율제한 없음"
        )

    # 이모지 결정
    if "전복" in fish_name or "소라" in fish_name:
        emoji = "🐚"
    elif "오징어" in fish_name:
        emoji = "🦑"
    elif "문어" in fish_name:
        emoji = "🐙"
    else:
        emoji = "🐟"

    # 금어기 정보
    금어기 = fish.get("금어기", "없음")
    금어기_출력 = ""
    if isinstance(금어기, dict):
        기본_금어기 = 금어기.get("전국", None)
        if 기본_금어기:
            금어기_출력 += f"전국 {convert_period_format(기본_금어기)}\n"
        else:
            금어기_출력 += "전국 없음\n"
        # 전국 제외 지역별 금어기 출력
        for 지역, 기간 in 금어기.items():
            if 지역 == "전국":
                continue
            금어기_출력 += f"{지역} {convert_period_format(기간)}\n"
    else:
        금어기_출력 = f"전국 {convert_period_format(금어기)}\n"

    # 금지체장 정보
    금지체장 = fish.get("금지체장", "없음")
    금지체장_출력 = ""
    if isinstance(금지체장, dict):
        기본_금지체장 = 금지체장.get("전국", None)
        if 기본_금지체장:
            금지체장_출력 += f"전국 {기본_금지체장}\n"
        else:
            금지체장_출력 += "전국 없음\n"
        # 전국 제외 지역별 금지체장 출력
        for 지역, 내용 in 금지체장.items():
            if 지역 == "전국":
                continue
            금지체장_출력 += f"{지역} {내용}\n"
    else:
        금지체장_출력 = f"전국 {금지체장}\n"

    # 예외사항
    예외사항 = fish.get("예외사항", "없음")
    # 포획비율제한
    포획비율 = fish.get("포획비율제한", "없음")

    # 최종 메시지 구성
    response = (
        f"{emoji} {fish_name} {emoji}\n\n"
        f"🚫 금어기\n"
        f"{금어기_출력.strip()}\n\n"
        f"📏 금지체장\n"
        f"{금지체장_출력.strip()}\n\n"
        f"⚠️ 예외사항 {예외사항}\n"
        f"⚠️ 포획비율제한 {포획비율}"
    )

    return response

