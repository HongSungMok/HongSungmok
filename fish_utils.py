from datetime import datetime
import logging
import re

logger = logging.getLogger(__name__)

def convert_period_format(period):
    """'6.1~6.30', '5.1~9.15 중 46일 이상' 등을 '6월1일 ~ 6월30일' 식으로 변환"""
    try:
        if period is None:
            return "없음"
        if isinstance(period, str):
            if "고시" in period or "없음" in period:
                return period
            if "~" not in period:
                return period  # '~' 없는 경우 그대로 반환

            start, end = period.split("~", 1)

            # 시작일 처리
            start_m, start_d = start.strip().split(".")
            start_formatted = f"{int(start_m)}월{int(start_d)}일"

            end = end.strip()

            # 종료일에서 '익년' 처리 및 조건문자 처리
            suffix = ""
            if "익년" in end:
                end = end.replace("익년", "").strip()
                match = re.match(r"(\d+)\.(\d+)(.*)", end)
                if match:
                    end_m, end_d, extra = match.groups()
                    suffix = f"익년 {int(end_m)}월{int(end_d)}일{extra.strip()}"
                else:
                    suffix = end
            else:
                match = re.match(r"(\d+)\.(\d+)(.*)", end)
                if match:
                    end_m, end_d, extra = match.groups()
                    suffix = f"{int(end_m)}월{int(end_d)}일{extra.strip()}"
                else:
                    suffix = end

            return f"{start_formatted} ~ {suffix}"
        else:
            return str(period)
    except Exception as e:
        logger.error(f"convert_period_format error: {e}")
        return str(period)

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

    response = ""  # 변수 초기화

    # 어종에 따라 이모지 선택
    if "전복" in fish_name or "소라" in fish_name:
        emoji = "🐚"
    elif "오징어" in fish_name:
        emoji = "🦑"
    elif "문어" in fish_name:
        emoji = "🐙"
    else:
        emoji = "🐟"

    # 금어기 전국 및 지역별 추출
    금어기_전국 = fish.get("금어기", "없음")
    금어기_지역별 = []
    for key, value in fish.items():
        if key.endswith("_금어기") and key != "금어기":
            지역명 = key.rsplit("_", 1)[0]
            지역명 = 지역명.replace(",", ", ")
            금어기_지역별.append((지역명, value))

    # 금지체장 전국 및 지역별 추출
    금지체장_전국 = fish.get("금지체장", "없음")
    금지체장_지역별 = []
    for key, value in fish.items():
        if key.endswith("_금지체장") and key != "금지체장":
            지역명 = key.rsplit("_", 1)[0]
            지역명 = 지역명.replace(",", ", ")
            금지체장_지역별.append((지역명, value))

    # 예외사항 및 포획비율 제한
    예외사항 = fish.get("금어기_예외", fish.get("예외사항", "없음"))
    포획비율 = fish.get("포획비율제한", "없음")

    # 응답 조합 시작
    response += f"{emoji} {fish_name} {emoji}\n\n"

    # 금어기 출력
    response += "🚫 금어기\n"
    response += f"전국: {convert_period_format(금어기_전국)}\n"
    for region, period in 금어기_지역별:
        response += f"{region}: {convert_period_format(period)}\n"

    response += "\n"

    # 금지체장 출력
    response += "📏 금지체장\n"
    response += f"전국: {금지체장_전국 if 금지체장_전국 else '없음'}\n"
    for region, size in 금지체장_지역별:
        response += f"{region}: {size}\n"

    response += "\n"

    # 예외사항 및 포획비율 제한 출력
    response += f"⚠️ 예외사항: {예외사항}\n"
    response += f"⚠️ 포획비율제한: {포획비율}"

    return response

