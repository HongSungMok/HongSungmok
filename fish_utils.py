from datetime import datetime

def is_date_in_range(period: str, today: datetime) -> bool:
    try:
        start_str, end_str = period.split("~")
        start_month, start_day = map(int, start_str.split("."))
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
    except Exception:
        return False

def format_period(period: str) -> str:
    try:
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
        return period  # 오류 시 원문 반환

def filter_periods(periods, today):
    if isinstance(periods, dict):
        valid = []
        for period in periods.values():
            if is_date_in_range(period, today):
                valid.append(period)
        return valid if valid else None
    elif isinstance(periods, str):
        return periods if is_date_in_range(periods, today) else None
    return None

def get_fish_info(fish_name, fish_data, today=None):
    if today is None:
        today = datetime.today()

    fish = fish_data.get(fish_name)
    if not fish:
        return f"🐟{fish_name}🐟\n\n🚫 금어기: 없음\n🚫 금지체장: 없음\⚠️ 예외사항: 없음\n⚠️ 포획비율제한: 없음"

    # 금어기
    금어기 = "없음"
    for key in ["금어기", "유자망_금어기", "근해채낚기_연안복합_정치망_금어기", "지역별_금어기", "금어기_예외"]:
        if key in fish:
            filtered = filter_periods(fish[key], today)
            if filtered:
                if isinstance(filtered, list):
                    금어기 = "; ".join(format_period(p) for p in filtered)
                else:
                    금어기 = format_period(filtered)
                break
            else:
                if isinstance(fish[key], str):
                    금어기 = format_period(fish[key])
                    break
                elif isinstance(fish[key], dict):
                    금어기 = "; ".join(format_period(p) for p in fish[key].values())
                    break

    # 금지체장
    금지체장 = "없음"
    if "금지체장" in fish:
        금지체장 = fish["금지체장"]
        if isinstance(금지체장, dict):
            if "기본" in 금지체장:
                금지체장 = 금지체장["기본"]
            else:
                금지체장 = list(금지체장.values())[0]
    if not 금지체장:
        금지체장 = "없음"

    # 예외사항
    예외사항 = (
        fish.get("금어기_해역_특이사항")
        or fish.get("금어기_예외")
        or fish.get("금어기_특정해역")
        or fish.get("금어기_추가")
        or "없음"
    )

    # 포획비율제한
    포획비율 = fish.get("포획비율제한", "없음")

    # 응답 메시지
    response = f"🐟{fish_name}🐟\n\n"
    response += f"🚫 금어기: {금어기}\n"
    response += f"🚫 금지체장: {금지체장}\n"
    response += f"⚠️ 예외사항: {예외사항}\n"
    response += f"⚠️ 포획비율제한: {포획비율}"

    return response