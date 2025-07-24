from datetime import datetime
import logging

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

def format_period(period: str) -> str:
    try:
        if "고시" in period or "없음" in period:
            return period
        start_str, end_str = period.split("~")
        start_month, start_day = map(int, start_str.strip().split("."))
        end_str = end_str.strip()
        if "익년" in end_str:
            end_str = end_str.replace("익년", "")
            end_month, end_day = map(int, end_str.split("."))
            return f"{start_month}월 {start_day}일 ~ 익년 {end_month}월 {end_day}일"
        else:
            end_month, end_day = map(int, end_str.split("."))
            return f"{start_month}월 {start_day}일 ~ {end_month}월 {end_day}일"
    except Exception:
        return period

def get_fish_info(fish_name, fish_data, today=None):
    if today is None:
        today = datetime.today()

    fish = fish_data.get(fish_name)
    if not fish:
        return (
            f"🚫 금어기\n전국: 없음\n\n"
            f"📏 금지체장\n전국: 없음\n\n"
            f"⚠️ 예외사항: 없음\n"
            f"⚠️ 포획비율제한: 없음"
        )

    # 이모지 설정
    if "전복" in fish_name:
        emoji = "🐚"
    elif "오징어" in fish_name:
        emoji = "🦑"
    elif "문어" in fish_name:
        emoji = "🐙"
    else:
        emoji = "🐟"

    response = f"{emoji} {fish_name} {emoji}\n\n"

    # 금어기
    금어기_기본 = format_period(fish.get("금어기", "없음"))
    금어기_lines = [f"🚫 금어기", f"전국: {금어기_기본}"]

    for key in sorted(fish.keys()):
        if key.endswith("_금어기") and not any(x in key for x in ["예외", "특이사항", "추가"]):
            지역 = key.replace("_금어기", "").replace("_", " ")
            값 = format_period(fish[key]) if fish[key] != "없음" else "없음"
            금어기_lines.append(f"{지역}: {값}")
    response += "\n".join(금어기_lines) + "\n\n"

    # 금지체장
    금지체장_기본 = fish.get("금지체장", "없음")
    금지체장_lines = [f"📏 금지체장", f"전국: {금지체장_기본}"]

    for key in sorted(fish.keys()):
        if key.endswith("_금지체장"):
            지역 = key.replace("_금지체장", "").replace("_", " ")
            금지체장_lines.append(f"{지역}: {fish[key]}")
    response += "\n".join(금지체장_lines) + "\n\n"

    # 예외사항
    예외사항 = (
        fish.get("금어기_해역_특이사항")
        or fish.get("금어기_예외")
        or fish.get("금어기_특정해역")
        or fish.get("금어기_추가")
        or "없음"
    )
    포획비율 = fish.get("포획비율제한", "없음")

    response += f"⚠️ 예외사항: {예외사항}\n"
    response += f"⚠️ 포획비율제한: {포획비율}"

    return response
