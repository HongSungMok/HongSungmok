from flask import Flask, request, jsonify
from datetime import datetime, timezone, timedelta
import logging
import os
import re

from fish_data import fish_data
from fish_utils import (
    normalize_fish_name,
    get_fish_info,
    get_fishes_in_seasonal_ban,
)

app = Flask(__name__)
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ──────────────────────────────────────────────────────────────────────────────
# 환경/상수
# ──────────────────────────────────────────────────────────────────────────────
KST = timezone(timedelta(hours=9))  # 한국 시간대 고정

# 사용자에게 보여줄 어종명 맵핑
display_name_map = {
    "조피볼락(우럭)": "조피볼락",
    "넙치(광어)": "넙치",
    "살오징어(오징어)": "살오징어",
    "전복(전복류)": "전복",
    "제주소라": "제주소라",
}

# 이모지 매핑
fish_emojis = {
    "대게": "🦀", "붉은대게": "🦀", "꽃게": "🦀",
    "오분자기": "🐚", "키조개": "🦪", "제주소라": "🐚",
    "주꾸미": "🐙", "대문어": "🐙", "참문어": "🐙",
    "낙지": "🦑", "살오징어(오징어)": "🦑",
    "해삼": "🌊", "넓미역": "🌿", "우뭇가사리": "🌿", "톳": "🌿",
}

INTENT_TIME_TOKENS = ("오늘", "지금", "현재", "금일", "투데이")

# ──────────────────────────────────────────────────────────────────────────────
# 유틸 함수
# ──────────────────────────────────────────────────────────────────────────────
def get_display_name(name: str) -> str:
    return display_name_map.get(name, name)


def get_emoji(name: str) -> str:
    return fish_emojis.get(name, "🐟")


def build_response(text, buttons=None):
    logger.info(f"[DEBUG] build_response 호출됨. buttons: {buttons}")
    response = {
        "version": "2.0",
        "template": {
            "outputs": [{"simpleText": {"text": text}}],
            "quickReplies": buttons if buttons else [],
        },
    }
    return response


def is_today_ban_query(text: str) -> bool:
    if not text:
        return False
    logger.info(f"[DEBUG] raw utterance repr: {text!r}")
    t = text.strip()
    t = re.sub(r"\s+", "", t)
    t = re.sub(r"[~!@#\$%\^&\*\(\)\-\_\+\=\[\]\{\}\|\\;:'\",\.<>\/\?·…•—–]", "", t)
    t = t.replace("의", "")
    has_time = any(tok in t for tok in INTENT_TIME_TOKENS)
    has_ban = ("금어기" in t)
    return has_time and has_ban


def extract_month_query(text: str):
    if not text:
        return None
    m1 = re.search(r"(\d{1,2})\s*월.*금어기", text)
    m2 = re.search(r"금어기.*?(\d{1,2})\s*월", text)
    m = m1 or m2
    if not m:
        return None
    try:
        month = int(m.group(1))
        if 1 <= month <= 12:
            return month
    except Exception:
        pass
    return None


# ──────────────────────────────────────────────────────────────────────────────
# 라우트
# ──────────────────────────────────────────────────────────────────────────────
@app.route("/TAC", methods=["POST"])
def fishbot():
    try:
        req = request.get_json(force=True, silent=True) or {}
        user_text = (req.get("userRequest", {}).get("utterance") or "").strip()
        today = datetime.now(KST)
        logger.info(f"[DEBUG] 사용자 입력: {user_text}")

        # 1) 오늘 금어기
        if is_today_ban_query(user_text):
            fishes = get_fishes_in_seasonal_ban(fish_data, today)
            if not fishes:
                return jsonify(build_response(
                    f"📅 오늘({today.month}월 {today.day}일) 금어기 어종은 없습니다.",
                    # 유지 버튼 (원하시면 이 라인 제거 가능)
                    buttons=[{"label": "오늘의 금어기", "action": "message", "messageText": "오늘 금어기"}]
                ))

            lines = [f"📅 오늘({today.month}월 {today.day}일) 금어기 어종:"]
            # 유지 버튼(요청 없으므로 그대로 둠). 필요 없다면 아래 두 줄을 삭제하세요.
            buttons = [{"label": "오늘의 금어기", "action": "message", "messageText": "오늘 금어기"}]

            # 어종 버튼 추가
            for name in fishes:
                disp = get_display_name(name)
                emoji = get_emoji(name)
                lines.append(f"- {emoji} {disp}")
                buttons.append({"label": disp, "action": "message", "messageText": disp})

            return jsonify(build_response("\n".join(lines), buttons=buttons))

        # 2) 월별 금어기
        month = extract_month_query(user_text)
        if month is not None:
            result = []
            for name, info in fish_data.items():
                period = info.get("금어기")
                if not period or "~" not in period:
                    continue
                try:
                    start, end = period.split("~")
                    sm = int(start.strip().split(".")[0])
                    em = int(end.replace("익년", "").strip().split(".")[0])

                    if sm <= em:
                        # 같은 해 안에서 시작~종료
                        if sm <= month <= em:
                            result.append(name)
                    else:
                        # 연도 걸침(예: 11~익년 2)
                        if month >= sm or month <= em:
                            result.append(name)
                except Exception as ex:
                    logger.warning(f"[WARN] 금어기 파싱 실패: {name} - {period} ({ex})")
                    continue

            if not result:
                # ✅ 월 버튼 없이, 어종도 없으니 빈 버튼 배열로 반환
                return jsonify(build_response(f"📅 {month}월 금어기 어종은 없습니다.", buttons=[]))

            lines = [f"📅 {month}월 금어기 어종:"]
            # ✅ 요청사항: "8월 금어기" 같은 월 버튼 제거 → 어종 버튼만 제공
            buttons = []
            for name in result:
                disp = get_display_name(name)
                emoji = get_emoji(name)
                lines.append(f"- {emoji} {disp}")
                buttons.append({"label": disp, "action": "message", "messageText": disp})

            return jsonify(build_response("\n".join(lines), buttons=buttons))

        # 3) 특정 어종 정보
        fish_norm = normalize_fish_name(user_text)
        logger.info(f"[DEBUG] 정규화된 어종명: {fish_norm}")
        logger.info(f"[DEBUG] fish_data에 존재?: {'있음' if fish_norm in fish_data else '없음'}")

        text, buttons = get_fish_info(fish_norm, fish_data)
        logger.info(f"[DEBUG] 응답 텍스트:\n{text}")
        logger.info(f"[DEBUG] 버튼: {buttons}")

        if fish_norm not in fish_data:
            # 미등록 어종 질의 시에도 버튼이 사라지지 않도록 기본 버튼(선택 사항)
            buttons = [{"label": "오늘의 금어기", "action": "message", "messageText": "오늘 금어기"}]

        return jsonify(build_response(text, buttons))

    except Exception as e:
        logger.error(f"[ERROR] fishbot error: {e}", exc_info=True)
        return jsonify(build_response("⚠️ 오류가 발생했습니다. 잠시 후 다시 시도해 주세요."))


# ──────────────────────────────────────────────────────────────────────────────
# 엔트리 포인트
# ──────────────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
