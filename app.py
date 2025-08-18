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
# TAC 업종/선적지(살오징어 전용, 확장 가능)
# ──────────────────────────────────────────────────────────────────────────────
TAC_INDUSTRY_MAP = {
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
    # 추후: "꽃게": [...], "고등어": [...]
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

# ──────────────────────────────────────────────────────────────────────────────
# TAC 유틸: 버튼/파싱
# ──────────────────────────────────────────────────────────────────────────────
def get_display_name(name: str) -> str:
    return display_name_map.get(name, name)

def build_tac_entry_button_for(fish_norm: str):
    """TAC 대상 어종이면 [🚢 TAC 업종] 버튼 노출 (어종 상세 화면용)"""
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

def build_tac_industry_buttons(fish_norm: str, industries: list):
    """
    업종 버튼에 '사람이 읽는 형태'로 컨텍스트 포함.
    - 표시/전송: '살오징어 근해채낚기'
    - 내부 파서는 이 형태와 구버전 'TAC_SELECT|...' 둘 다 지원
    """
    disp_fish = get_display_name(fish_norm)
    buttons = []
    for ind in industries[:MAX_QR]:
        human = f"{disp_fish} {ind}"  # 사용자에게 보이는/전송되는 텍스트
        buttons.append({"label": ind, "action": "message", "messageText": human})
    return buttons

_TAC_SELECT_RE = re.compile(r"^TAC_SELECT\|(.+?)\|(.+)$")
def parse_tac_select(text: str):
    """
    업종 버튼 눌림 파싱.
    지원 형태:
      1) '살오징어 근해채낚기' (권장, 사용자 친화)
      2) 'TAC_SELECT|살오징어|근해채낚기' (구버전 호환)
    반환: (fish_norm, industry) 또는 None
    """
    if not text:
        return None
    t = (text or "").strip()

    # 2) 구버전 페이로드
    m = _TAC_SELECT_RE.match(t)
    if m:
        fish_raw, industry_raw = m.group(1).strip(), m.group(2).strip()
        return normalize_fish_name(fish_raw), industry_raw

    # 1) 사람형: '어종 업종' (업종이 공백 포함 가능 → 업종 후보를 사전에서 역탐색)
    for industry in sorted(INDUSTRY_PORTS.keys(), key=len, reverse=True):
        if t.endswith(industry):
            fish_part = t[: -len(industry)].strip()
            # fish_part 끝의 공백 제거 후 normalize
            fish_norm = normalize_fish_name(fish_part)
            if fish_norm in TAC_INDUSTRY_MAP and industry in TAC_INDUSTRY_MAP[fish_norm]:
                return fish_norm, industry
            # display_name으로 적었을 수도 있음
            for k, v in display_name_map.items():
                if v == fish_part:
                    fish_norm = normalize_fish_name(k)
                    if fish_norm in TAC_INDUSTRY_MAP and industry in TAC_INDUSTRY_MAP[fish_norm]:
                        return fish_norm, industry
    return None

# ──────────────────────────────────────────────────────────────────────────────
# 일반 매칭/선적지 유틸
# ──────────────────────────────────────────────────────────────────────────────
def _normalize_for_match(s: str) -> str:
    s = (s or "").strip()
    s = re.sub(r"(업종|선택|선택됨|카테고리)\s*[:\-]?\s*", "", s)
    s = re.sub(r"\s+", "", s)
    s = re.sub(r"[^0-9A-Za-z가-힣]", "", s)
    return s

def is_industry_select_legacy(text: str):
    """(레거시) 업종명 단독으로 들어온 경우 안전 처리"""
    if not text:
        return None
    t_raw = (text or "").strip()
    if t_raw in INDUSTRY_PORTS:
        return t_raw
    t_norm = _normalize_for_match(t_raw)
    for key in INDUSTRY_PORTS.keys():
        if t_norm == _normalize_for_match(key):
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
    all_ports = set(p for ps in INDUSTRY_PORTS.values() for p in ps)
    if t in all_ports:
        return t
    for p in all_ports:
        if t_clean == _clean_text(p):
            return p
    return None

# ──────────────────────────────────────────────────────────────────────────────
# 유틸 (공통)
# ──────────────────────────────────────────────────────────────────────────────
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
    if buttons_capped:
        tpl["template"]["quickReplies"] = buttons_capped
    return tpl

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
# 쿼리 유틸
# ──────────────────────────────────────────────────────────────────────────────
def is_today_ban_query(text: str) -> bool:
    if not text:
        return False
    t = (text or "").strip()
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
                # BASE_MENU 병합하지 않음 (요청사항)
                tac_buttons = build_tac_industry_buttons(tac_target, industries)
                return jsonify(build_response("\n".join(lines), buttons=tac_buttons))
            else:
                return jsonify(build_response(
                    f"'{get_display_name(tac_target)}' TAC 업종 정보가 없습니다.",
                    buttons=BASE_MENU
                ))

        # 2.6) TAC 업종 선택 후 선적지 화면 (사람형 & 구버전 페이로드 모두 파싱)
        parsed = parse_tac_select(user_text)
        if parsed:
            fish_norm, selected_industry = parsed
            ports = INDUSTRY_PORTS.get(selected_industry, [])
            disp_fish = get_display_name(fish_norm)
            if ports:
                lines = [
                    f"⛱️ {disp_fish} {selected_industry} 선적지 ⛱️",
                    "",
                    *ports,
                    "",
                    "아래 버튼을 눌러주세요."
                ]
                port_buttons = [{"label": p, "action": "message", "messageText": p} for p in ports[:MAX_QR]]
                return jsonify(build_response("\n".join(lines), buttons=port_buttons))
            else:
                return jsonify(build_response(
                    f"⛱️ {disp_fish} {selected_industry} 선적지 ⛱️\n\n등록된 선적지가 없습니다."
                ))

        # (옵션) 레거시 업종 단독 입력 처리
        legacy_ind = is_industry_select_legacy(user_text)
        if legacy_ind:
            ports = INDUSTRY_PORTS.get(legacy_ind, [])
            if ports:
                lines = [
                    f"⛱️ 선적지 목록 ⛱️",
                    "",
                    *ports,
                    "",
                    "아래 버튼을 눌러주세요."
                ]
                port_buttons = [{"label": p, "action": "message", "messageText": p} for p in ports[:MAX_QR]]
                return jsonify(build_response("\n".join(lines), buttons=port_buttons))
            else:
                return jsonify(build_response("⛱️ 선적지 목록 ⛱️\n\n등록된 선적지가 없습니다."))

        # 2.7) 선적지 선택 (임시)
        selected_port = is_port_select(user_text)
        if selected_port:
            lines = [
                f"📍 선적지: {selected_port}",
                "어선별 조업량 및 소진률 데이터는 추후 연동 예정입니다."
            ]
            return jsonify(build_response("\n".join(lines)))

        # 3) 특정 어종 정보
        fish_norm = normalize_fish_name(user_text)
        logger.info(f"[DEBUG] 정규화된 어종명: {fish_norm}")
        logger.info(f"[DEBUG] fish_data에 존재?: {'있음' if fish_norm in fish_data else '없음'}")

        text, fish_buttons = get_fish_info(fish_norm, fish_data)

        # 요청사항: 어종 상세엔 BASE_MENU 제거. TAC 대상이면 '🚢 TAC 업종'만 노출
        tac_entry = build_tac_entry_button_for(fish_norm)
        if tac_entry:
            return jsonify(build_response(text, buttons=tac_entry))
        return jsonify(build_response(text, buttons=fish_buttons))

    except Exception as e:
        logger.error(f"[ERROR] fishbot error: {e}", exc_info=True)
        # 에러 시에는 복구 경로 제공을 위해 BASE_MENU 제공
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
    # 프로덕션에서는 gunicorn 권장 (예: gunicorn -w 4 -k gthread -b 0.0.0.0:5000 app:app)
    app.run(host="0.0.0.0", port=port)




