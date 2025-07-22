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

def filter_periods(periods, today):
    if isinstance(periods, dict):
        valid_periods = {}
        for key, period in periods.items():
            if is_date_in_range(period, today):
                valid_periods[key] = period
        return valid_periods if valid_periods else None
    elif isinstance(periods, str):
        return periods if is_date_in_range(periods, today) else None
    return None

def get_fish_info(fish_name, fish_data, today=None):
    if today is None:
        today = datetime.today()

    fish = fish_data.get(fish_name)
    if not fish:
        return f"'{fish_name}'에 대한 정보가 없습니다."

    금어기 = None
    for key in ["금어기", "유자망_금어기", "근해채낚기_연안복합_정치망_금어기", "지역별_금어기", "금어기_예외"]:
        if key in fish:
            filtered = filter_periods(fish[key], today)
            if filtered:
                if isinstance(filtered, dict):
                    금어기 = "; ".join(f"{k}: {v}" for k, v in filtered.items())
                else:
                    금어기 = filtered
                break
            else:
                # 날짜 필터링이 안 되더라도 내용 있으면 그대로 보여주기
                if isinstance(fish[key], str):
                    금어기 = fish[key]
                    break
                elif isinstance(fish[key], dict):
                    금어기 = "; ".join(f"{k}: {v}" for k, v in fish[key].items())
                    break
    if not 금어기:
        금어기 = "없음"

    금지체장 = None
    if "금지체장" in fish:
        금지체장 = fish["금지체장"]
        if isinstance(금지체장, dict):
            if "기본" in 금지체장:
                금지체장 = 금지체장["기본"]
            else:
                금지체장 = list(금지체장.values())[0]
    else:
        금지체장 = "없음"
    if not 금지체장:
        금지체장 = "없음"

    예외사항 = fish.get("금어기_해역_특이사항") or fish.get("금어기_예외") or fish.get("금어기_특정해역") or fish.get("금어기_추가")
    포획비율 = fish.get("포획비율제한")

    response = f"🚫 금어기: {금어기}\n🚫 금지체장: {금지체장}"
    if 예외사항:
        response += f"\n⚠️ 예외사항: {예외사항}"
    if 포획비율:
        response += f"\n⚠️ 포획비율제한: {포획비율}"
    return response

