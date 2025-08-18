from flask import Flask, request, jsonify
from datetime import datetime, timezone, timedelta
import logging
import os
import re
import calendar
from functools import lru_cache

from fish_data import fish_data
from fish_utils import (
    normalize_fish_name,
    get_fish_info,
)

app = Flask(__name__)
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ──────────────────────────────────────────────────────────────────────────────
# 환경/상수
# ──────────────────────────────────────────────────────────────────────────────
KST = timezone(timedelta(hours=9))  # 한국 시간대 고정
MAX_QR = 10  # Kakao quickReplies 최대 10개

# 항상 유지할 "기본 메뉴" 버튼 (상황 버튼과 함께 노출)
BASE_MENU = [
    {"label": "📅 오늘 금어기", "action": "message", "messageText": "오늘 금어기 알려줘"},
    {"label": "🗓️ 월 금어기",  "action": "message", "messageText": "8월 금어기 알려줘"},  # 진입용 예시
    {"label": "❓도움말",      "action": "message", "messageText": "도움말"},
]

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

# 성능/안정화: 정규식 사전 컴파일
_CLEAN_RE = re.compile(r"\s+")
_PUNCT_RE = re.compile(r"[~!@#\$%\^&\*\(\)\-\_\+\=\[\]\{\}\|\\;:'\",\.<>\/\?·…•—–]")

# 말일 테이블(윤년 영향 없음: 월의 말일만 필요)
_MONTH_END = {m: calendar.monthrange(2024, m)[1] for m in range(1, 13)}

# ──────────────────────────────────────────────────────────────────────────────
# TAC 업종/선적지(살오징어 전용)
# ──────────────────────────────────────────────────────────────────────────────
TAC_INDUSTRY_MAP = {
    # normalize_fish_name() 결과 키를 포괄적으로 커버
    "살오징어(오징어)": [
        "근해채낚기",
        "동해구중형트롤",
        "대형트롤",
        "대형선망",
        "쌍끌이대형저인망",
        "근해자망",
        "서남해구쌍끌이중형저인망",
    ],
    "살오징어": [
        "근해채낚기",
        "동해구중형트롤",
        "대형트롤",
        "대형선망",
        "쌍끌이대형저인망",
        "근해자망",
        "서남해구쌍끌이중형저인망",
    ],
}

INDUSTRY_PORTS = {
    "근해채낚기": ["부산", "울산", "강원", "경북", "경남", "제주", "전남", "충남"],
    "대형선망": ["부산", "경남"],
    "대형트롤": ["부산", "경남", "전남"],
    "동해구중형트롤": ["강원", "경북"],
    "근해자망": ["부산", "인천", "울산", "충남", "전북", "전남", "경북", "경남", "제주"],
    "쌍끌이대형저인망": ["부산", "인천", "전남", "경남"],
    "서남해구쌍끌이중형저인망": ["경남", "전남"],
}

def build_tac_entry_button_for(fish_norm: str):
    """살오징어면 [🚢 TAC 업종] 버튼 하나만 노출"""
    if fish_norm in TAC_INDUSTRY_MAP:
        return [{"label": "🚢 TAC 업종", "action": "message", "messageText": f"TAC {get_display_name(fish_norm)}"}]
    return []

def is_tac_list_request(text: str):
    """'TAC 살오징어' 또는 '살오징어 TAC' 트리거 감지"""
    if not text:
        return None
    t = (text or "").strip()
    m1 = re.match(r"^TAC\s+(.+)$", t, flags=re.IGNORECASE)
    m2 = re.match(r"^(.+)\s+TAC$", t, flags=re.IGNORECASE)
    target = (m1.group(1).strip() if m1 else (m2.group(1).strip() if m2 else None))
    if not target:
        return None
    return normalize_fish_name(target)

# ──────────────────────────────────────────────────────────────────────────────
# 매칭 유틸 (느슨 매칭)
# ──────────────────────────────────────────────────────────────────────────────
def _normalize_for_match(s: str) -> str:
    # 흔한 접두 안내 문구/기호/공백 제거하여 비교 안정화
    s = (s or "").strip()
    s = re.sub(r"(업종|선택|선택됨|카테고리)\s*[:\-]?\s*", "", s)
    s = re.sub(r"\s+", "", s)                 # 공백 제거
    s = re.sub(r"[^0-9A-Za-z가-힣]", "", s)    # 기호 제거
    return s

def is_industry_select(text: str):
    """업종 버튼/텍스트 선택 여부 판단 (느슨 매칭 + 접두어/기호 제거)"""
    if not text:
        return None
    t_raw = (text or "").strip()

    # 1) 완전 일치
    if t_raw in INDUSTRY_PORTS:
        return t_raw

    # 2) 느슨 일치 (정규화 후 비교)
    t_norm = _normalize_for_match(t_raw)
    for key in INDUSTRY_PORTS.keys():
        if t_norm == _normalize_for_match(key):
            return key

    # 3) 포함형(안내 문구 안에 들어간 경우)
    for key in INDUSTRY_PORTS.keys():
        if _normalize_for_match(key) in t_norm:
            return key

    return None

def _clean_text(s: str) -> str:
    return _PUNCT_RE.sub("", _CLEAN_RE.sub("", (s or "").strip()))

def is_port_select(text: str):
    """선적지 버튼 선택 여부 판단 (느슨 매칭)"""
    if not text:
        return None
    t = (text or "").strip()
    t_clean = _clean_text(t)

    # 전체 포트 목록 평탄화
    all_ports = set(p for ps in INDUSTRY_PORTS.values() for p in ps)
    # 완전 일치
    if t in all_ports:
        return t
    # 느슨 매칭
    for p in all_ports:
        if t_clean == _clean_text(p):
            return p
    return None

# ──────────────────────────────────────────────────────────────────────────────
# 유틸
# ──────────────────────────────────────────────────────────────────────────────
def get_display_name(name: str) -> str:
    return display_name_map.get(name, name)

def get_emoji(name: str) -> str:
    return fish_emojis.get(name, "🐟")

def cap_quick_replies(buttons):
    return (buttons or [])[:MAX_QR]

def merge_buttons(primary, base=BASE_MENU, cap=MAX_QR):
    """상황 버튼(primary) + 기본 메뉴(base)를 합치되, 중복 제거/순서 유지/상한 적용."""
    seen = set()
    out = []
    for btn in (primary or []):
        key = (btn.get("label"), btn.get("messageText"))
        if key not in seen and len(out) < cap:
            out.append(btn); seen.add(key)
    for btn in (base or []):
        key = (btn.get("label"), btn.get("messageText"))
        if key not in seen and len(out) < cap:
            out.append(btn); seen.add(key)
    return out

def build_response(text, buttons=None):
    tpl = {
        "version": "2.0",
        "template": {"outputs": [{"simpleText": {"text": text}}]}
    }
    buttons_capped = cap_quick_replies(buttons)
    logger.info(f"[DEBUG] build_response buttons_count={len(buttons_capped)}")
    if buttons_capped:
        tpl["template"]["quickReplies"] = buttons_capped
    return tpl

def is_today_ban_query(text: str) -> bool:
    if not text:
        return False
    t = (text or "").strip()
    logger.info(f"[DEBUG] raw utterance repr: {t!r}")
    t = _CLEAN_RE.sub("", t)
    t = _PUNCT_RE.sub("", t)
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
# 금어기 계산 (사전 파싱 + 캐시)
# ──────────────────────────────────────────────────────────────────────────────
def _parse_md(token: str):
    token = token.strip()
    token = token.replace("익년", "").strip()
    if "." in token:
        m_str, d_str = token.split(".", 1)
        m = int(re.sub(r"\D", "", m_str) or 0)
        d = int(re.sub(r"\D", "", d_str) or 1)
    else:
        m = int(re.sub(r"\D", "", token) or 0)
        d = 1
    return m, d

def _in_range(md, start_md, end_md):
    sm, sd = start_md
    em, ed = end_md
    m, d = md
    if (sm, sd) <= (em, ed):
        return (sm, sd) <= (m, d) <= (em, ed)
    else:
        return (m, d) >= (sm, sd) or (m, d) <= (em, ed)

_PARSED_PERIODS = []  # [(name, (sm, sd), (em, ed))]

def _prepare_periods():
    global _PARSED_PERIODS
    parsed = []
    for name, info in fish_data.items():
        period = (info or {}).get("금어기")
        if not period or "~" not in period:
            continue
        try:
            start, end = [p.strip() for p in period.split("~", 1)]
            sm, sd = _parse_md(start)
            em, ed = _parse_md(end)
            if "." not in start:
                sd = 1
            if "." not in end:
                ed = _MONTH_END.get(em, 31)
            if not (1 <= sm <= 12 and 1 <= em <= 12):
                logger.warning(f"[WARN] 금어기 월 범위 오류: {name} - {period}")
                continue
            parsed.append((name, (sm, sd), (em, ed)))
        except Exception as ex:
            logger.warning(f"[WARN] 금어기 파싱 실패: {name} - {period} ({ex})")
            continue
    _PARSED_PERIODS = parsed
    logger.info(f"[INFO] 금어기 파싱 완료: {_PARSED_PERIODS.__len__()}건")

_prepare_periods()

@lru_cache(maxsize=370)
def today_banned_fishes_cached(month: int, day: int):
    md = (month, day)
    banned = []
    for name, start_md, end_md in _PARSED_PERIODS:
        try:
            if _in_range(md, start_md, end_md):
                banned.append(name)
        except Exception as ex:
            logger.warning(f"[WARN] 범위 판정 실패: {name} ({ex})")
    return banned

def build_fish_buttons(fishes):
    buttons = []
    for name in fishes[:MAX_QR]:
        disp = get_display_name(name)
        buttons.append({"label": disp, "action": "message", "messageText": disp})
    return buttons

# 도움말 텍스트
HELP_TEXT = (
    "🧭 사용 방법\n"
    "• '오늘 금어기' → 오늘 기준 금어기 어종 목록\n"
    "• '8월 금어기 알려줘' → 해당 월에 금어기인 어종\n"
    "• 어종명을 입력하면 상세 규제(금어기/금지체장 등)를 안내합니다.\n"
)

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

        # 도움말
        if "도움말" in user_text:
            return jsonify(build_response(HELP_TEXT, buttons=BASE_MENU))

        # 1) 오늘 금어기
        if is_today_ban_query(user_text):
            fishes = today_banned_fishes_cached(today.month, today.day)
            if not fishes:
                return jsonify(build_response(
                    f"📅 오늘({today.month}월 {today.day}일) 금어기 어종은 없습니다.",
                    buttons=BASE_MENU
                ))
            lines = [f"📅 오늘({today.month}월 {today.day}일) 금어기 어종:"]
            for name in fishes:
                lines.append(f"- {get_emoji(name)} {get_display_name(name)}")
            buttons = merge_buttons(build_fish_buttons(fishes))
            return jsonify(build_response("\n".join(lines), buttons=buttons))

        # 2) 월별 금어기
        month = extract_month_query(user_text)
        if month is not None:
            result = []
            for name, start_md, end_md in _PARSED_PERIODS:
                sm, _ = start_md
                em, _ = end_md
                if sm <= em:
                    if sm <= month <= em:
                        result.append(name)
                else:
                    if month >= sm or month <= em:
                        result.append(name)

            if not result:
                return jsonify(build_response(
                    f"📅 {month}월 금어기 어종은 없습니다.",
                    buttons=BASE_MENU
                ))

            lines = [f"📅 {month}월 금어기 어종:"]
            for name in result:
                lines.append(f"- {get_emoji(name)} {get_display_name(name)}")

            buttons = merge_buttons(build_fish_buttons(result))
            return jsonify(build_response("\n".join(lines), buttons=buttons))

        # 2.5) TAC 업종 목록: "TAC 살오징어" / "살오징어 TAC"
        tac_target = is_tac_list_request(user_text)
        if tac_target:
            if tac_target in TAC_INDUSTRY_MAP:
                industries = TAC_INDUSTRY_MAP[tac_target]
                lines = [
                    f"🚢 {get_display_name(tac_target)} TAC 업종 🚢",
                    "",
                    *industries,
                    "",
                    "자세한 내용은 버튼을 눌러주십시오."
                ]
                tac_buttons = [{"label": n, "action": "message", "messageText": n} for n in industries[:MAX_QR]]
                return jsonify(build_response("\n".join(lines), buttons=merge_buttons(tac_buttons)))
            else:
                return jsonify(build_response(
                    f"'{get_display_name(tac_target)}' TAC 업종 정보가 없습니다.",
                    buttons=BASE_MENU
                ))

        # 2.6) 업종 선택 후 선적지 화면
        selected_industry = is_industry_select(user_text)
        if selected_industry:
            ports = INDUSTRY_PORTS.get(selected_industry, [])
            if ports:
                lines = [
                    "⛱️ 선적지 목록 ⛱️",
                    "",
                    *ports,
                    "",
                    "아래 버튼을 눌러주세요."
                ]
                port_buttons = [{"label": p, "action": "message", "messageText": p} for p in ports[:MAX_QR]]
                return jsonify(build_response("\n".join(lines), buttons=merge_buttons(port_buttons)))
            else:
                return jsonify(build_response(
                    "⛱️ 선적지 목록 ⛱️\n\n등록된 선적지가 없습니다.",
                    buttons=BASE_MENU
                ))

        # 2.7) 선적지 선택 (임시 응답: 추후 조업량/소진률 연동 지점)
        selected_port = is_port_select(user_text)
        if selected_port:
            lines = [
                f"📍 선적지: {selected_port}",
                "어선별 조업량 및 소진률 데이터는 추후 연동 예정입니다."
            ]
            # TODO: 여기에서 DB/CSV 연동 후 표 출력 로직 추가
            return jsonify(build_response("\n".join(lines), buttons=BASE_MENU))

        # 3) 특정 어종 정보
        fish_norm = normalize_fish_name(user_text)
        logger.info(f"[DEBUG] 정규화된 어종명: {fish_norm}")
        logger.info(f"[DEBUG] fish_data에 존재?: {'있음' if fish_norm in fish_data else '없음'}")

        text, fish_buttons = get_fish_info(fish_norm, fish_data)

        # 살오징어면 '🚢 TAC 업종' 버튼 하나만 노출
        tac_entry = build_tac_entry_button_for(fish_norm)
        if tac_entry:
            return jsonify(build_response(text, buttons=tac_entry))

        # 살오징어 외에는 기존 버튼 + 기본 메뉴 병합
        buttons = merge_buttons(fish_buttons)
        return jsonify(build_response(text, buttons))

    except Exception as e:
        logger.error(f"[ERROR] fishbot error: {e}", exc_info=True)
        # 에러 시에도 기본 메뉴 유지하여 복구 경로 제공
        return jsonify(build_response("⚠️ 오류가 발생했습니다. 잠시 후 다시 시도해 주세요.", buttons=BASE_MENU))

# (선택) 헬스체크
@app.route("/healthz", methods=["GET"])
def healthz():
    return "ok", 200

# ──────────────────────────────────────────────────────────────────────────────
# 엔트리 포인트
# ──────────────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    # 프로덕션에서는 gunicorn 권장 (app:app)
    app.run(host="0.0.0.0", port=port)



