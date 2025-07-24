from datetime import datetime
import logging

logger = logging.getLogger(__name__)

def is_date_in_range(period: str, today: datetime) -> bool:
    """
    주어진 기간 문자열이 오늘 날짜(today)에 포함되는지 판단.
    period 예: "3.1~4.30", "12.1~익년 2.15"
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
    except Exception as e:
        logger.error(f"is_date_in_range error for period '{period}': {e}")
        return False

def format_period(period: str) -> str:
    """
    '3.1~4.30' -> '3월 1일 ~ 4월 30일'
    '12.1~익년 2.15' -> '12월 1일 ~ 익년 2월 15일'
    """
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
        return period  # 실패 시 원본 그대로 반환

def get_fish_info(fish_name, fish_data, today=None):
    """
    fish_data 내 어종별 금어기, 금지체장, 예외사항, 포획비율제한 정보를
    보기 좋은 텍스트로 만들어 리턴함.

    출력 예시:

    🚫 금어기  
    전국: 없음  
    제주: 7월1일 ~ 8월31일 

    📏 금지체장  
    전국: 없음  
    제주: 각장 4cm 이하

    ⚠️ 예외사항: 없음  
    ⚠️ 포획비율제한: 없음
    """
    if today is None:
        today = datetime.today()

    fish = fish_data.get(fish_name)
    if not fish:
        return (
            f"🚫 금어기\n"
            f"전국: 없음\n\n"
            f"📏 금지체장\n"
            f"전국: 없음\n\n"
            f"⚠️ 예외사항: 없음\n"
            f"⚠️ 포획비율제한: 없음"
        )

    # 금어기 지역별 키 추출 (기본 제외, 특이사항/예외/추가 제외)
    금어기_지역키 = [
        k for k in fish.keys()
        if "금어기" in k and k != "금어기"
        and not k.endswith("_예외")
        and not k.endswith("_특이사항")
        and not k.endswith("_추가")
    ]

    # 금지체장 지역별 키 추출 (기본 제외)
    금지체장_지역키 = [
        k for k in fish.keys()
        if "금지체장" in k and k != "금지체장"
    ]

    # 기본 금어기 및 지역별 금어기 텍스트 준비
    금어기_기본 = fish.get("금어기", "없음")
    금어기_지역별 = []
    for key in 금어기_지역키:
        지역명 = key.replace("_금어기", "").replace("_", " ")
        금어기_지역별.append(f"{지역명}: {fish[key]}")

    # 기본 금지체장 및 지역별 금지체장 텍스트 준비
    금지체장_기본 = fish.get("금지체장", "없음")
    금지체장_지역별 = []
    for key in 금지체장_지역키:
        지역명 = key.replace("_금지체장", "").replace("_", " ")
        금지체장_지역별.append(f"{지역명}: {fish[key]}")

    # 예외사항 및 포획비율제한 추출
    예외사항 = (
        fish.get("금어기_해역_특이사항")
        or fish.get("금어기_예외")
        or fish.get("금어기_특정해역")
        or fish.get("금어기_추가")
        or "없음"
    )
    포획비율 = fish.get("포획비율제한", "없음")

    # 결과 문자열 조립
    response = ""

    response += "🚫 금어기\n"
    response += f"전국: {금어기_기본}\n"
    if 금어기_지역별:
        response += "\n".join(금어기_지역별) + "\n"

    response += "\n"

    response += "📏 금지체장\n"
    response += f"전국: {금지체장_기본}\n"
    if 금지체장_지역별:
        response += "\n".join(금지체장_지역별) + "\n"

    response += "\n"

    response += f"⚠️ 예외사항: {예외사항}\n"
    response += f"⚠️ 포획비율제한: {포획비율}"

    return response

