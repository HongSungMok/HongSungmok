from flask import Flask, request, jsonify
from datetime import datetime, timezone, timedelta
import logging
import os
import re
import calendar

from fish_data import fish_data
from fish_utils import (
    normalize_fish_name,
    get_fish_info,
    # get_fishes_in_seasonal_ban,  # 속도/의존성 이슈 방지 위해 내부 구현 사용
)

app = Flask(__name__)
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ──────────────────────────────────────────────────────────────────────────────
# 환경/상수
# ──────────────────────────────────────────────────────────────────────────────
KST = timezone(timedelta(hours=9))  # 한국 시간대 고정
MAX_QR = 10  # Kakao quickReplies 최대 10개

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

def cap_quick_replies(buttons):
    """Kakao 제한(<=10) 보장"""
    return (buttons or [])[:MAX_QR]

def build_response(text, buttons=None):
    buttons_capped = cap_quick_replies(buttons)
    logger.info(f"[DEBUG] build_response buttons_count={len(buttons_capped)}")
    return {
        "version": "2.0",
        "template": {
            "outputs": [{"simpleText": {"text": text}}],
            "quickReplies": buttons_capped,
        },
    }

def is_today_ban_query(text: str) -> bool:
    if not text:
        return False
    t = (text or "").strip()
    logger.info(f"[DEBUG] raw utterance repr: {t!r}")
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
# 금어기 계산(오늘 기준, 초고속 로직)
# ──────────────────────────────────────────────────────────────────────────────
def _parse_md(token: str):
    """'M.D' 또는 'M' 형태를 (month, day)로. day가 없으면 1(시작), 말일(종료)로 상위에서 처리."""
    token = token.strip()
    token = token.replace("익년", "").strip()
    if "." in token:
        m_str, d_str = token.split(".", 1)
        m = int(m_str)
        d = int(re.sub(r"\D", "", d_str) or 1)
    else:
        m = int(re.sub(r"\D", "", token))
        d = 1
    return m, d

def _in_range(md, start_md, end_md):
    """월/일만으로 범위 포함 여부(연도 걸침 지원)."""
    sm, sd = start_md
    em, ed = end_md
    m, d = md
    if (sm, sd) <= (em, ed):
        return (sm, sd) <= (m, d) <= (em, ed)
    else:
        # 연도 걸침
        return (m, d) >= (sm, sd) or (m, d) <= (em, ed)

def today_banned_fishes(today_dt):
    """fish_data의 '금어기'를 빠르게 판독해 오늘 포함 어종 리스트 반환."""
    m = today_dt.month
    d = today_dt.day
    md = (m, d)
    banned = []

    for name, info in fish_data.items():
        period = (info or {}).get("금어기")
        if not period or "~" not in period:
            continue
        try:
            start, end = [p.strip() for p in period.split("~", 1)]

            sm, sd = _parse_md(start)
            em, ed = _parse_md(end)

            # 일자가 빠진 경우 보정(시작=1일, 종료=말일)
            if "." not in start:
                sd = 1
            if "." not in end:
                # 말일
                ed = calendar.monthrange(2024, em)[1]  # 연도 무관, 말일만 필요

            if _in_range(md, (sm, sd), (em, ed)):
                banned.append(name)
        except Exception as ex:
            logger.warning(f"[WARN] 금어기 파싱 실패: {name} - {period} ({ex})")
            continue

    return banned

def build_fish_buttons(fishes):
    buttons = []
    for name in fishes:
        disp = get_display_name(name)
        buttons.append({"label": disp, "action": "message", "messageText": disp})
        if len(buttons) >= MAX_QR:
            break
    return buttons

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
            fishes = today_banned_fishes(today)
            if not fishes:
                return jsonify(build_response(
                    f"📅 오늘({today.month}월 {today.day}일) 금어기 어종은 없습니다.",
                    buttons=[]  # 버튼 없음
                ))

            # 텍스트는 모두 표시, 버튼은 최대 10개까지만
            lines = [f"📅 오늘({today.month}월 {today.day}일) 금어기 어종:"]
            for name in fishes:
                lines.append(f"- {get_emoji(name)} {get_display_name(name)}")
            buttons = build_fish_buttons(fishes)

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
                    start, end = [p.strip() for p in period.split("~", 1)]
                    sm = int(_parse_md(start)[0])
                    em = int(_parse_md(end)[0])

                    if sm <= em:
                        if sm <= month <= em:
                            result.append(name)
                    else:
                        if month >= sm or month <= em:
                            result.append(name)
                except Exception as ex:
                    logger.warning(f"[WARN] 금어기 파싱 실패: {name} - {period} ({ex})")
                    continue

            if not result:
                return jsonify(build_response(f"📅 {month}월 금어기 어종은 없습니다.", buttons=[]))

            lines = [f"📅 {month}월 금어기 어종:"]
            for name in result:
                lines.append(f"- {get_emoji(name)} {get_display_name(name)}")
            buttons = build_fish_buttons(result)  # 월 버튼 제거, 어종 버튼만(최대 10)

            return jsonify(build_response("\n".join(lines), buttons=buttons))

        # 3) 특정 어종 정보
        fish_norm = normalize_fish_name(user_text)
        logger.info(f"[DEBUG] 정규화된 어종명: {fish_norm}")
        logger.info(f"[DEBUG] fish_data에 존재?: {'있음' if fish_norm in fish_data else '없음'}")

        text, buttons = get_fish_info(fish_norm, fish_data)
        # 안전장치: 혹시 get_fish_info가 10개 넘게 돌려줄 수 있으니 제한
        buttons = cap_quick_replies(buttons)

        return jsonify(build_response(text, buttons))

    except Exception as e:
        logger.error(f"[ERROR] fishbot error: {e}", exc_info=True)
        return jsonify(build_response("⚠️ 오류가 발생했습니다. 잠시 후 다시 시도해 주세요.", buttons=[]))

# ──────────────────────────────────────────────────────────────────────────────
# 엔트리 포인트
# ──────────────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)  # ✅ 외부 바인딩
