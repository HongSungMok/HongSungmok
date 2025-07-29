import re
import logging
from datetime import datetime

logger = logging.getLogger(__name__)


def convert_period_format(period):
    """'6.1~8.31' -> '6월1일 ~ 8월31일' 등으로 포맷 변환"""
    try:
        if not period:
            return "없음"
        if isinstance(period, str):
            if "고시" in period or "없음" in period or "~" not in period:
                return period

            start, end = period.split("~", 1)
            start_m, start_d = start.strip().split(".")
            start_fmt = f"{int(start_m)}월{int(start_d)}일"

            end = end.strip()
            if "익년" in end:
                end = end.replace("익년", "").strip()
                match = re.match(r"(\d+)\.(\d+)(.*)", end)
                if match:
                    end_m, end_d, extra = match.groups()
                    end_fmt = f"익년 {int(end_m)}월{int(end_d)}일{extra.strip()}"
                else:
                    end_fmt = end
            else:
                match = re.match(r"(\d+)\.(\d+)(.*)", end)
                if match:
                    end_m, end_d, extra = match.groups()
                    end_fmt = f"{int(end_m)}월{int(end_d)}일{extra.strip()}"
                else:
                    end_fmt = end
            return f"{start_fmt} ~ {end_fmt}"
        return str(period)
    except Exception as e:
        logger.error(f"[convert_period_format error] {e}")
        return str(period)


def get_fish_info(fish_name, fish_data):
    fish = fish_data.get(fish_name)
    if not fish:
        return (
            f"🚫 금어기\n전국: 없음\n\n"
            f"📏 금지체장\n전국: 없음\n\n"
            f"⚠️ 예외사항: 없음\n"
            f"⚠️ 포획비율제한: 없음"
        )

    # 이모지
    emoji = "🐟"
    if "전복" in fish_name or "소라" in fish_name:
        emoji = "🐚"
    elif "오징어" in fish_name:
        emoji = "🦑"
    elif "주꾸미" in fish_name or "문어" in fish_name or "낙지" in fish_name:
        emoji = "🐙"
    elif "게" in fish_name:
        emoji = "🦀"
    elif "미역" in fish_name or "우뭇가사리" in fish_name or "톳" in fish_name:
        emoji = "🌿"

    # 금어기
    금어기_전국 = fish.get("금어기")
    금어기_지역별 = [
        (k.rsplit("_", 1)[0].replace(",", ", "), v)
        for k, v in fish.items()
        if k.endswith("_금어기") and k != "금어기"
    ]

    # 금지체장/체중
    금지기준_전국 = fish.get("금지체장") or fish.get("금지체중")
    기준_이름 = "📏 금지체장" if "금지체장" in fish else ("⚖️ 금지체중" if "금지체중" in fish else "📏 금지체장")
    금지기준_지역별 = [
        (k.rsplit("_", 1)[0].replace(",", ", "), v)
        for k, v in fish.items()
        if k.endswith("_금지체장") or k.endswith("_금지체중")
    ]

    예외사항 = fish.get("금어기_예외", fish.get("예외사항", "없음"))
    포획비율 = fish.get("포획비율제한", "없음")

    res = f"{emoji} {fish_name} {emoji}\n\n"

    # 금어기
    res += f"🚫 금어기\n전국: {convert_period_format(금어기_전국) if 금어기_전국 else '없음'}\n"
    for region, period in 금어기_지역별:
        res += f"{region}: {convert_period_format(period)}\n"
    res += "\n"

    # 금지체장/체중
    res += f"{기준_이름}\n전국: {금지기준_전국 if 금지기준_전국 else '없음'}\n"
    for region, value in 금지기준_지역별:
        res += f"{region}: {value}\n"
    res += "\n"

    res += f"⚠️ 예외사항: {예외사항}\n"
    res += f"⚠️ 포획비율제한: {포획비율}"

    return res


def get_fishes_in_seasonal_ban(fish_data, target_date=None):
    """
    특정 날짜에 금어기에 해당하는 어종 목록 반환
    """
    if target_date is None:
        target_date = datetime.today()

    month_day = (target_date.month, target_date.day)
    matched_fishes = []

    for fish_name, fish in fish_data.items():
        period = fish.get("금어기")
        if not period or "~" not in period:
            continue
        try:
            start_str, end_str = period.split("~")
            start_m, start_d = map(int, start_str.strip().split("."))
            end_str = end_str.strip()

            if "익년" in end_str:
                end_m, end_d = map(int, end_str.replace("익년", "").strip().split("."))
                # 익년 처리: 시작 월이 더 클 경우만 유효
                in_range = (
                    (month_day >= (start_m, start_d)) or
                    (month_day <= (end_m, end_d))
                )
            else:
                end_m, end_d = map(int, end_str.strip().split("."))
                if (start_m, start_d) <= (end_m, end_d):
                    in_range = (start_m, start_d) <= month_day <= (end_m, end_d)
                else:
                    # 예외: 11.15 ~ 3.31 같이 연도 걸치는 금어기
                    in_range = month_day >= (start_m, start_d) or month_day <= (end_m, end_d)

            if in_range:
                matched_fishes.append(fish_name)
        except Exception as e:
            logger.warning(f"[금어기 파싱 오류] {fish_name}: {period} / {e}")
            continue

    return matched_fishes
