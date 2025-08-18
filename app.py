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

BASE_MENU = [
    {"label": "📅 오늘 금어기", "action": "message", "messageText": "오늘 금어기 알려줘"},
    {"label": "🗓️ 월 금어기",  "action": "message", "messageText": "8월 금어기 알려줘"},
    {"label": "❓도움말",      "action": "message", "messageText": "도움말"},
]

display_name_map = {
    "조피볼락(우럭)": "조피볼락",
    "넙치(광어)": "넙치",
    "살오징어(오징어)": "살오징어",
    "전복(전복류)": "전복",
    "제주소라": "제주소라",
}

fish_emojis = {
    "대게": "🦀", "붉은대게": "🦀", "꽃게": "🦀",
    "오분자기": "🐚", "키조개": "🦪", "제주소라": "🐚",
    "주꾸미": "🐙", "대문어": "🐙", "참문어": "🐙",
    "낙지": "🦑", "살오징어(오징어)": "🦑",
    "해삼": "🌊", "넓미역": "🌿", "우뭇가사리": "🌿", "톳": "🌿",
}

INTENT_TIME_TOKENS = ("오늘", "지금", "현재", "금일", "투데이")

_CLEAN_RE = re.compile(r"\s+")
_PUNCT_RE = re.compile(r"[~!@#\$%\^&\*\(\)\-\_\+\=\[\]\{\}\|\\;:'\",\.<>\/\?·…•—–]")

_MONTH_END = {m: calendar.monthrange(2024, m)[1] for m in range(1, 13)}

# ──────────────────────────────────────────────────────────────────────────────
# TAC 업종/선적지
# ──────────────────────────────────────────────────────────────────────────────
TAC_INDUSTRY_MAP = {
    "살오징어(오징어)": [
        "근해채낚기","동해구중형트롤","대형트롤","대형선망",
        "쌍끌이대형저인망","근해자망","서남해구쌍끌이중형저인망",
    ],
    "살오징어": [
        "근해채낚기","동해구중형트롤","대형트롤","대형선망",
        "쌍끌이대형저인망","근해자망","서남해구쌍끌이중형저인망",
    ],
}

INDUSTRY_PORTS = {
    "근해채낚기": ["부산","울산","강원","경북","경남","제주","전남","충남"],
    "대형선망": ["부산","경남"],
    "대형트롤": ["부산","경남","전남"],
    "동해구중형트롤": ["강원","경북"],
    "근해자망": ["부산","인천","울산","충남","전북","전남","경북","경남","제주"],
    "쌍끌이대형저인망": ["부산","인천","전남","경남"],
    "서남해구쌍끌이중형저인망": ["경남","전남"],
}

def build_tac_entry_button_for(fish_norm: str):
    if fish_norm in TAC_INDUSTRY_MAP:
        return [{"label": "🚢 TAC 업종", "action": "message", "messageText": f"TAC {get_display_name(fish_norm)}"}]
    return []

def is_tac_list_request(text: str):
    if not text:
        return None
    t = (text or "").strip()
    m1 = re.match(r"^TAC\s+(.+)$", t, flags=re.IGNORECASE)
    m2 = re.match(r"^(.+)\s+TAC$", t, flags=re.IGNORECASE)
    target = (m1.group(1).strip() if m1 else (m2.group(1).strip() if m2 else None))
    return normalize_fish_name(target) if target else None

# ──────────────────────────────────────────────────────────────────────────────
# 매칭 유틸
# ──────────────────────────────────────────────────────────────────────────────
def _normalize_for_match(s: str) -> str:
    s = (s or "").strip()
    s = re.sub(r"(업종|선택|선택됨|카테고리)\s*[:\-]?\s*", "", s)
    s = re.sub(r"\s+", "", s)
    s = re.sub(r"[^0-9A-Za-z가-힣]", "", s)
    return s

def is_industry_select(text: str):
    if not text:
        return None
    t_raw = (text or "").strip()
    if t_raw in INDUSTRY_PORTS:
        return t_raw
    t_norm = _normalize_for_match(t_raw)
    for key in INDUSTRY_PORTS.keys():
        if t_norm == _normalize_for_match(key):
            return key
    for key in INDUSTRY_PORTS.keys():
        if _normalize_for_match(key) in t_norm:
            return key
    return None

def _clean_text(s: str) -> str:
    return _PUNCT_RE.sub("", _CLEAN_RE.sub("", (s or "").strip()))

def is_port_select(text: str):
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
# 유틸
# ──────────────────────────────────────────────────────────────────────────────
def get_display_name(name: str) -> str:
    return display_name_map.get(name, name)

def get_emoji(name: str) -> str:
    return fish_emojis.get(name, "🐟")

def cap_quick_replies(buttons):
    return (buttons or [])[:MAX_QR]

def merge_buttons(primary, base=BASE_MENU, cap=MAX_QR):
    seen, out = set(), []
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
    tpl = {"version": "2.0","template": {"outputs": [{"simpleText": {"text": text}}]}}
    buttons_capped = cap_quick_replies(buttons)
    if buttons_capped:
        tpl["template"]["quickReplies"] = buttons_capped
    return tpl

def is_today_ban_query(text: str) -> bool:
    if not text: return False
    t = _CLEAN_RE.sub("", _PUNCT_RE.sub("", (text or "").strip())).replace("의", "")
    return any(tok in t for tok in INTENT_TIME_TOKENS) and ("금어기" in t)

def extract_month_query(text: str):
    if not text: return None
    m1 = re.search(r"(\d{1,2})\s*월.*금어기", text)
    m2 = re.search(r"금어기.*?(\d{1,2})\s*월", text)
    m = m1 or m2
    if not m: return None
    try:
        month = int(m.group(1))
        return month if 1 <= month <= 12 else None
    except: return None

# ──────────────────────────────────────────────────────────────────────────────
# 금어기 계산
# ──────────────────────────────────────────────────────────────────────────────
def _parse_md(token: str):
    token = token.replace("익년", "").strip()
    if "." in token:
        m_str, d_str = token.split(".", 1)
        return int(re.sub(r"\D", "", m_str) or 0), int(re.sub(r"\D", "", d_str) or 1)
    return int(re.sub(r"\D", "", token) or 0), 1

def _in_range(md, start_md, end_md):
    sm, sd = start_md; em, ed = end_md; m, d = md
    if (sm, sd) <= (em, ed):
        return (sm, sd) <= (m, d) <= (em, ed)
    return (m, d) >= (sm, sd) or (m, d) <= (em, ed)

_PARSED_PERIODS = []
def _prepare_periods():
    global _PARSED_PERIODS
    parsed = []
    for name, info in fish_data.items():
        period = (info or {}).get("금어기")
        if not period or "~" not in period: continue
        try:
            start, end = [p.strip() for p in period.split("~", 1)]
            sm, sd = _parse_md(start); em, ed = _parse_md(end)
            if "." not in start: sd = 1
            if "." not in end: ed = _MONTH_END.get(em, 31)
            if 1 <= sm <= 12 and 1 <= em <= 12:
                parsed.append((name, (sm, sd), (em, ed)))
        except: continue
    _PARSED_PERIODS = parsed

_prepare_periods()

@lru_cache(maxsize=370)
def today_banned_fishes_cached(month: int, day: int):
    md = (month, day)
    return [name for name, start_md, end_md in _PARSED_PERIODS if _in_range(md, start_md, end_md)]

def build_fish_buttons(fishes):
    return [{"label": get_display_name(name),"action": "message","messageText": get_display_name(name)} for name in fishes[:MAX_QR]]

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

        if "도움말" in user_text:
            return jsonify(build_response(HELP_TEXT, buttons=BASE_MENU))

        if is_today_ban_query(user_text):
            fishes = today_banned_fishes_cached(today.month, today.day)
            if not fishes:
                return jsonify(build_response(f"📅 오늘({today.month}월 {today.day}일) 금어기 어종은 없습니다.", buttons=BASE_MENU))
            lines = [f"📅 오늘({today.month}월 {today.day}일) 금어기 어종:"] + [f"- {get_emoji(n)} {get_display_name(n)}" for n in fishes]
            return jsonify(build_response("\n".join(lines), buttons=merge_buttons(build_fish_buttons(fishes))))

        month = extract_month_query(user_text)
        if month is not None:
            result = []
            for name, start_md, end_md in _PARSED_PERIODS:
                sm, _ = start_md; em, _ = end_md
                if (sm <= em and sm <= month <= em) or (sm > em and (month >= sm or month <= em)):
                    result.append(name)
            if not result:
                return jsonify(build_response(f"📅 {month}월 금어기 어종은 없습니다.", buttons=BASE_MENU))
            lines = [f"📅 {month}월 금어기 어종:"] + [f"- {get_emoji(n)} {get_display_name(n)}" for n in result]
            return jsonify(build_response("\n".join(lines), buttons=merge_buttons(build_fish_buttons(result))))

        tac_target = is_tac_list_request(user_text)
        if tac_target:
            if tac_target in TAC_INDUSTRY_MAP:
                industries = TAC_INDUSTRY_MAP[tac_target]
                lines = [f"🚢 {get_display_name(tac_target)} TAC 업종 🚢","",*industries,"","자세한 내용은 버튼을 눌러주십시오."]
                tac_buttons = [{"label": n, "action": "message", "messageText": n} for n in industries[:MAX_QR]]
                return jsonify(build_response("\n".join(lines), buttons=merge_buttons(tac_buttons)))
            return jsonify(build_response(f"'{get_display_name(tac_target)}' TAC 업종 정보가 없습니다.", buttons=BASE_MENU))

        selected_industry = is_industry_select(user_text)
        if selected_industry:
            ports = INDUSTRY_PORTS.get(selected_industry, [])
            if ports:
                lines = ["⛱️ 선적지 목록 ⛱️","",*ports,"","아래 버튼을 눌러주세요."]
                port_buttons = [{"label": p,"action": "message","messageText": p} for p in ports[:MAX_QR]]
                return jsonify(build_response("\n".join(lines), buttons=merge_buttons(port_buttons)))
            return jsonify(build_response("⛱️ 선적지 목록 ⛱️\n\n등록된 선적지가 없습니다.", buttons=BASE_MENU))

        selected_port = is_port_select(user_text)
        if selected_port:
            lines = [f"📍 선적지: {selected_port}","어선별 조업량 및 소진률 데이터는 추후 연동 예정입니다."]
            return jsonify(build_response("\n".join(lines), buttons=BASE_MENU))

        fish_norm = normalize_fish_name(user_text)
        text, fish_buttons = get_fish_info(fish_norm, fish_data)
        tac_entry = build_tac_entry_button_for(fish_norm)
        if tac_entry:
            return jsonify(build_response(text, buttons=tac_entry))
        return jsonify(build_response(text, merge_buttons(fish_buttons)))

    except Exception as e:
        logger.error(f"[ERROR] fishbot error: {e}", exc_info=True)
        return jsonify(build_response("⚠️ 오류가 발생했습니다. 잠시 후 다시 시도해 주세요.", buttons=BASE_MENU))

@app.route("/healthz", methods=["GET"])
def healthz():
    return "ok", 200

# ──────────────────────────────────────────────────────────────────────────────
# 엔트리 포인트
# ──────────────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    # ❗️ 개발 테스트 용도 (python app.py)
    # 실제 배포는 gunicorn 권장: gunicorn -w 4 -k gthread -b 0.0.0.0:5000 app:app
    app.run(host="0.0.0.0", port=port)




