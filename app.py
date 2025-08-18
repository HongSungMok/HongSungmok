from flask import Flask, request, jsonify
from datetime import datetime, timezone, timedelta
import logging, os, re, calendar
from functools import lru_cache

from fish_data import fish_data
from fish_utils import normalize_fish_name, get_fish_info

app = Flask(__name__)
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ──────────────────────────────────────────────────────────────
# 환경/상수
# ──────────────────────────────────────────────────────────────
KST = timezone(timedelta(hours=9))
MAX_QR = 10

BASE_MENU = [
    {"label": "📅 오늘 금어기", "action": "message", "messageText": "오늘 금어기 알려줘"},
    {"label": "🗓️ 월 금어기", "action": "message", "messageText": "8월 금어기 알려줘"},
    {"label": "❓도움말", "action": "message", "messageText": "도움말"},
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

# ──────────────────────────────────────────────────────────────
# TAC 업종/선적지 정의 (확장 가능 구조)
# ──────────────────────────────────────────────────────────────
TAC_INDUSTRY_MAP = {
    "살오징어": ["근해채낚기","동해구중형트롤","대형트롤","대형선망","쌍끌이대형저인망","근해자망","서남해구쌍끌이중형저인망"],
    "살오징어(오징어)": ["근해채낚기","동해구중형트롤","대형트롤","대형선망","쌍끌이대형저인망","근해자망","서남해구쌍끌이중형저인망"],

    # 앞으로 확장
    "꽃게": ["근해자망","연안자망","연안통발"],
    "고등어": ["대형선망","근해자망"],
}

INDUSTRY_PORTS = {
    "근해채낚기": ["부산","울산","강원","경북","경남","제주","전남","충남"],
    "대형선망": ["부산","경남"],
    "대형트롤": ["부산","경남","전남"],
    "동해구중형트롤": ["강원","경북"],
    "근해자망": ["부산","인천","울산","충남","전북","전남","경북","경남","제주"],
    "쌍끌이대형저인망": ["부산","인천","전남","경남"],
    "서남해구쌍끌이중형저인망": ["경남","전남"],

    # 꽃게, 고등어 업종 예시
    "연안자망": ["인천","충남","전북"],
    "연안통발": ["전남","경남"],
}

# ──────────────────────────────────────────────────────────────
# 매칭 유틸
# ──────────────────────────────────────────────────────────────
def _normalize_for_match(s: str) -> str:
    s = (s or "").strip()
    s = re.sub(r"(업종|선택|카테고리)\s*[:\-]?\s*", "", s)
    s = re.sub(r"\s+", "", s)
    s = re.sub(r"[^0-9A-Za-z가-힣]", "", s)
    return s

def is_industry_select(text: str):
    if not text: return None
    t_raw = text.strip()
    if t_raw in INDUSTRY_PORTS: return t_raw
    t_norm = _normalize_for_match(t_raw)
    for key in INDUSTRY_PORTS:
        if t_norm == _normalize_for_match(key): return key
    return None

def _clean_text(s: str) -> str:
    return _PUNCT_RE.sub("", _CLEAN_RE.sub("", (s or "").strip()))

def is_port_select(text: str):
    if not text: return None
    t_clean = _clean_text(text)
    all_ports = set(p for ps in INDUSTRY_PORTS.values() for p in ps)
    for p in all_ports:
        if t_clean == _clean_text(p): return p
    return None

# ──────────────────────────────────────────────────────────────
# 유틸
# ──────────────────────────────────────────────────────────────
def get_display_name(name: str): return display_name_map.get(name, name)
def get_emoji(name: str): return fish_emojis.get(name, "🐟")
def cap_quick_replies(buttons): return (buttons or [])[:MAX_QR]

def build_response(text, buttons=None):
    tpl = {"version": "2.0","template": {"outputs": [{"simpleText": {"text": text}}]}}
    if buttons: tpl["template"]["quickReplies"] = cap_quick_replies(buttons)
    return tpl

# ──────────────────────────────────────────────────────────────
# 라우트
# ──────────────────────────────────────────────────────────────
@app.route("/TAC", methods=["POST"])
def fishbot():
    req = request.get_json(force=True, silent=True) or {}
    user_text = (req.get("userRequest", {}).get("utterance") or "").strip()
    today = datetime.now(KST)
    logger.info(f"[DEBUG] 사용자 입력: {user_text}")

    # 1) 도움말
    if "도움말" in user_text:
        return jsonify(build_response("🧭 사용법: 어종명을 입력하면 규제를 확인할 수 있습니다.", BASE_MENU))

    # 2) TAC 업종 목록 요청 ("TAC 살오징어")
    m = re.match(r"^TAC\s+(.+)$", user_text) or re.match(r"^(.+)\s+TAC$", user_text)
    if m:
        fish_norm = normalize_fish_name(m.group(1))
        if fish_norm in TAC_INDUSTRY_MAP:
            industries = TAC_INDUSTRY_MAP[fish_norm]
            lines = [f"🚢 {get_display_name(fish_norm)} TAC 업종 🚢","",*industries,"","자세한 내용은 버튼을 눌러주십시오."]
            buttons = [{"label": n,"action":"message","messageText":n} for n in industries]
            return jsonify(build_response("\n".join(lines), buttons))
        return jsonify(build_response(f"'{fish_norm}' TAC 업종 정보가 없습니다.", BASE_MENU))

    # 3) 업종 선택 시 → 선적지 출력
    selected_industry = is_industry_select(user_text)
    if selected_industry:
        ports = INDUSTRY_PORTS.get(selected_industry, [])
        if ports:
            lines = [f"⛱️ {selected_industry} 선적지 목록 ⛱️","",*ports,"","아래 버튼을 눌러주세요."]
            buttons = [{"label": p,"action":"message","messageText":p} for p in ports]
            return jsonify(build_response("\n".join(lines), buttons))
        return jsonify(build_response(f"⛱️ {selected_industry} 선적지 목록 ⛱️\n\n등록된 선적지가 없습니다."))

    # 4) 선적지 선택 시 (임시)
    selected_port = is_port_select(user_text)
    if selected_port:
        lines = [f"📍 선적지: {selected_port}","어선별 조업량 및 소진률 데이터는 추후 연동 예정입니다."]
        return jsonify(build_response("\n".join(lines)))

    # 5) 어종 정보
    fish_norm = normalize_fish_name(user_text)
    if fish_norm in fish_data:
        text, _ = get_fish_info(fish_norm, fish_data)
        # TAC 대상 어종이면 "📊 TAC 업종" 버튼만 붙임
        tac_btns = []
        if fish_norm in TAC_INDUSTRY_MAP:
            tac_btns = [{"label":"📊 TAC 업종","action":"message","messageText":f"TAC {get_display_name(fish_norm)}"}]
        return jsonify(build_response(text, tac_btns))

    # 6) fallback
    return jsonify(build_response("제가 할 수 있는 일이 아니에요.", BASE_MENU))

@app.route("/healthz", methods=["GET"])
def healthz(): return "ok", 200

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)





