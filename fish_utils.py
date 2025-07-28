import re
import logging

logger = logging.getLogger(__name__)

def convert_period_format(period):
    """
    금어기 기간 문자열을 사람이 읽기 좋은 형식으로 변환
    예: '6.1~8.31' -> '6월1일 ~ 8월31일'
    '익년' 처리 포함
    """
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

    # 이모지 선정
    emoji = "🐟"
    if "전복" in fish_name or "소라" in fish_name:
        emoji = "🐚"
    elif "오징어" in fish_name:
        emoji = "🦑"
    elif "주꾸미" in fish_name or "문어" in fish_name or "낙지" in fish_name:
        emoji = "🐙"
    elif "게" in fish_name or "대게" in fish_name or "꽃게" in fish_name:
        emoji = "🦀"
    elif "미역" in fish_name or "우뭇가사리" in fish_name or "톳" in fish_name:
        emoji = "🌿"

    # 금어기(전국 및 지역별)
    금어기_전국 = fish.get("금어기", None)
    금어기_지역별 = [
        (k.rsplit("_", 1)[0].replace(",", ", "), v)
        for k, v in fish.items()
        if k.endswith("_금어기") and k != "금어기"
    ]

    # 금지체장 또는 금지체중 (전국 및 지역별)
    금지기준_전국 = fish.get("금지체장") or fish.get("금지체중") or None
    기준_이름 = "📏 금지체장" if "금지체장" in fish else ("⚖️ 금지체중" if "금지체중" in fish else "📏 금지체장")
    금지기준_지역별 = [
        (k.rsplit("_", 1)[0].replace(",", ", "), v)
        for k, v in fish.items()
        if k.endswith("_금지체장") or k.endswith("_금지체중")
    ]

    예외사항 = fish.get("금어기_예외", fish.get("예외사항", "없음"))
    포획비율 = fish.get("포획비율제한", "없음")

    res = f"{emoji} {fish_name} {emoji}\n\n"

    # 전국 금어기 출력 (없으면 '전국: 없음')
    if 금어기_전국:
        res += f"🚫 금어기\n전국: {convert_period_format(금어기_전국)}\n"
    else:
        res += f"🚫 금어기\n전국: 없음\n"

    # 지역별 금어기 출력
    for region, period in 금어기_지역별:
        res += f"{region}: {convert_period_format(period)}\n"
    res += "\n"

    # 전국 금지체장/체중 출력 (없으면 '전국: 없음')
    if 금지기준_전국:
        res += f"{기준_이름}\n전국: {금지기준_전국}\n"
    else:
        res += f"{기준_이름}\n전국: 없음\n"

    # 지역별 금지체장/체중 출력
    for region, value in 금지기준_지역별:
        res += f"{region}: {value}\n"
    res += "\n"

    res += f"⚠️ 예외사항: {예외사항}\n"
    res += f"⚠️ 포획비율제한: {포획비율}"

    return res