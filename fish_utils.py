from datetime import datetime

def is_date_in_range(period: str, today: datetime) -> bool:
    """
    period: "4.1~6.30", "12.1~익년 1.31" 형식의 금어기 기간 문자열
    today: datetime 객체 (오늘 날짜)
    """
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
    except Exception:
        return False

def format_period(period: str) -> str:
    """
    "4.1~6.30" → "4월 1일 ~ 6월 30일"
    "12.1~익년 1.31" → "12월 1일 ~ 익년 1월 31일"
    """
    try:
        start_str, end_str = period.split("~")
        start_month, start_day = map(int, start_str.strip().split("."))
        end_str = end_str.strip()
        if "익년" in end_str:
            end_str = end_str.replace("익년", "").strip()
            end_month, end_day = map(int, end_str.split("."))
            return f"{start_month}월 {start_day}일 ~ 익년 {end_month}월 {end_day}일"
        else:
            end_month, end_day = map(int, end_str.split("."))
            return f"{start_month}월 {start_day}일 ~ {end_month}월 {end_day}일"
    except Exception:
        # 원본 문자열 그대로 반환 (파싱 실패 시)
        return period

def filter_periods(periods, today):
    """
    periods: str 또는 dict(str)
    오늘 날짜(today) 기준으로 현재 해당되는 금어기 기간을 필터링
    반환: 해당 기간 리스트 또는 None
    """
    if isinstance(periods, dict):
        valid_periods = []
        for p in periods.values():
            if is_date_in_range(p, today):
                valid_periods.append(p)
        return valid_periods if valid_periods else None
    elif isinstance(periods, str):
        return periods if is_date_in_range(periods, today) else None
    return None

def get_fish_info(fish_name, fish_data, today=None):
    """
    fish_name: 대표 어종명 (예: '조피볼락(우럭)')
    fish_data: 딕셔너리 원본 데이터
    today: datetime 객체 (없으면 현재 날짜)
    """
    if today is None:
        today = datetime.today()

    fish = fish_data.get(fish_name)
    if not fish:
        # 데이터 없으면 안내 메시지 리턴
        return "🚫 금어기: 없음\n🚫 금지체장: 없음\n⚠️ 예외사항: 없음\n⚠️ 포획비율제한: 없음"

    # 금어기 체크
    금어기 = "없음"
    금어기_keys = [
        "금어기",
        "유자망_금어기",
        "근해채낚기_연안복합_정치망_금어기",
        "지역별_금어기",
        "금어기_예외",
    ]
    for key in 금어기_keys:
        if key in fish:
            filtered = filter_periods(fish[key], today)
            if filtered:
                # 필터링 된 기간이 리스트이면 여러 개 포맷
                if isinstance(filtered, list):
                    금어기 = "; ".join(format_period(p) for p in filtered)
                else:
                    금어기 = format_period(filtered)
                break
            else:
                # 필터링 된 기간이 없으면 전체 기간 출력 (예: 예외사항 등)
                if isinstance(fish[key], str):
                    금어기 = format_period(fish[key])
                    break
                elif isinstance(fish[key], dict):
                    금어기 = "; ".join(format_period(p) for p in fish[key].values())
                    break

    # 금지체장
    금지체장 = "없음"
    if "금지체장" in fish:
        val = fish["금지체장"]
        if isinstance(val, dict):
            # dict 형태면 기본 키 있으면 그거 우선
            금지체장 = val.get("기본", list(val.values())[0])
        else:
            금지체장 = val
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
    포획비율제한 = fish.get("포획비율제한", "없음")

    # 최종 메시지
    response = f"🚫 금어기: {금어기}\n"
    response += f"🚫 금지체장: {금지체장}\n"
    response += f"⚠️ 예외사항: {예외사항}\n"
    response += f"⚠️ 포획비율제한: {포획비율제한}"

    return response