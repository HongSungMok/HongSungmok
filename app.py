from flask import Flask, request, jsonify
from datetime import datetime, timezone, timedelta
import logging, os, re, calendar
from functools import lru_cache

from fish_data import fish_data
from fish_utils import normalize_fish_name, get_fish_info

# TAC 메타데이터
from TAC_data import (
    TAC_DATA,
    is_tac_species,
    get_display_name as tac_display,
    get_industries,
    get_ports,
    all_industries_union,
    all_ports_union,
)

# 운영 데이터
from TAC_data_sources import (
    get_weekly_report,
    get_depletion_rows,
    get_weekly_vessel_catch,
    get_season_vessel_catch,
)

app = Flask(__name__)
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ──────────────────────────────────────────────────────────────────────────────
# 환경/상수
# ──────────────────────────────────────────────────────────────────────────────
KST = timezone(timedelta(hours=9))
MAX_QR = 10

display_name_map = {
    "조피볼락(우럭)": "조피볼락",
    "넙치(광어)": "넙치",
    "전복(전복류)": "전복",
    "제주소라": "제주소라",
}

fish_emojis = {
    "대게": "🦀", "붉은대게": "🦀", "꽃게": "🦀",
    "오분자기": "🐚", "키조개": "🦪", "제주소라": "🐚",
    "주꾸미": "🐙", "대문어": "🐙", "참문어": "🐙",
    "낙지": "🦑", "살오징어": "🦑",
    "해삼": "🌊", "넓미역": "🌿", "우뭇가사리": "🌿", "톳": "🌿",
}

BASE_MENU = [
    {"label": "📅 오늘 금어기", "action": "message", "messageText": "오늘 금어기 알려줘"},
    {"label": "🗓️ 월 금어기",  "action": "message", "messageText": "8월 금어기 알려줘"},
    {"label": "❓도움말",      "action": "message", "messageText": "도움말"},
]

INTENT_TIME_TOKENS = ("오늘", "지금", "현재", "금일", "투데이")
_CLEAN_RE = re.compile(r"\s+")
_PUNCT_RE = re.compile(r"[~!@#\$%\^&\*\(\)\-\_\+\=\[\]\{\}\|\\;:'\",\.<>\/\?·…•—–]")
_MONTH_END = {m: calendar.monthrange(2024, m)[1] for m in range(1, 13)}

# ──────────────────────────────────────────────────────────────────────────────
# 주차/기간 유틸
# ──────────────────────────────────────────────────────────────────────────────
def week_range_and_index_for(date: datetime):
    delta_to_sat = (date.weekday() - 5) % 7
    sat = (date - timedelta(days=delta_to_sat)).date()
    fri = sat + timedelta(days=6)
    thu = sat + timedelta(days=5)

    first_day = thu.replace(day=1)
    first_thu = first_day
    while first_thu.weekday() != 3:  # Thu=3
        first_thu += timedelta(days=1)

    week_idx = 1 + (thu - first_thu).days // 7
    return sat, fri, thu.month, week_idx, thu.year

def fmt_period_line(sat, fri):
    return f"({sat.strftime('%Y.%m.%d')}~{fri.strftime('%m.%d')})"

def season_label_from_year(y: int):
    a = y % 100
    b = (y + 1) % 100
    return f"({a:02d}~{b:02d}년 어기)"

# ──────────────────────────────────────────────────────────────────────────────
# 공용 유틸
# ──────────────────────────────────────────────────────────────────────────────
def cap_quick_replies(buttons):
    return (buttons or [])[:MAX_QR]

def build_response(text, buttons=None):
    tpl = {"version":"2.0","template":{"outputs":[{"simpleText":{"text":text}}]}}
    if buttons:
        tpl["template"]["quickReplies"] = cap_quick_replies(buttons)
    return tpl

def fmt_num(v):
    if v is None:
        return "-"
    if isinstance(v, (int, float)):
        return f"{v:,.1f}" if (isinstance(v, float) and v != int(v)) else f"{int(v):,}"
    return str(v)

# ──────────────────────────────────────────────────────────────────────────────
# TAC 키 해결
# ──────────────────────────────────────────────────────────────────────────────
from TAC_data import get_aliases as tac_aliases
def resolve_tac_key(fish_norm: str):
    if is_tac_species(fish_norm):
        return fish_norm
    for sp, meta in TAC_DATA.items():
        disp = meta.get("display")
        aliases = set(meta.get("aliases", []))
        if fish_norm == sp or fish_norm == disp or fish_norm in aliases:
            return sp
    return None

def display_name(fish_norm: str) -> str:
    sp = resolve_tac_key(fish_norm)
    if sp:
        return tac_display(sp)
    return display_name_map.get(fish_norm, fish_norm)

def get_emoji(name: str) -> str:
    return fish_emojis.get(name, "🐟")

# ──────────────────────────────────────────────────────────────────────────────
# TAC 버튼/파서
# ──────────────────────────────────────────────────────────────────────────────
def is_tac_list_request(text: str):
    if not text: return None
    t = text.strip()
    m1 = re.match(r"^TAC\s+(.+)$", t, re.IGNORECASE)
    m2 = re.match(r"^(.+)\s+TAC$", t, re.IGNORECASE)
    target = (m1.group(1).strip() if m1 else (m2.group(1).strip() if m2 else None))
    return normalize_fish_name(target) if target else None

def build_tac_entry_button_for(fish_norm: str):
    sp = resolve_tac_key(fish_norm)
    if sp:
        return [{"label":"🚢 TAC 업종","action":"message","messageText":f"TAC {display_name(sp)}"}]
    return []

def build_tac_industry_buttons(fish_norm: str):
    sp = resolve_tac_key(fish_norm) or fish_norm
    inds = get_industries(sp)
    disp_fish = display_name(sp)
    return [{"label": ind, "action": "message", "messageText": f"{disp_fish} {ind}"} for ind in inds[:MAX_QR]]

def build_port_buttons(fish_norm: str, industry: str):
    sp = resolve_tac_key(fish_norm) or fish_norm
    ports = get_ports(sp, industry)
    disp = display_name(sp)
    return [{"label": p, "action": "message", "messageText": f"{disp} {industry} {p}"} for p in ports[:MAX_QR]]

def build_port_detail_buttons(fish_norm: str, industry: str, port: str):
    sp = resolve_tac_key(fish_norm) or fish_norm
    disp = display_name(sp)

    # 항상 "<어종> <업종> <선적지> <의도>" 형태로 붙여줌
    buttons = [
        {
            "label": "📈 소진현황",
            "action": "message",
            "messageText": f"{disp} {industry} {port} 소진현황",
        },
        {
            "label": "📅 주간별 어획량",
            "action": "message",
            "messageText": f"{disp} {industry} {port} 주간별 어획량",
        },
        {
            "label": "🗂 전체기간 어획량",
            "action": "message",
            "messageText": f"{disp} {industry} {port} 전체기간 어획량",
        },
        {
            "label": "◀︎ 선적지 목록",
            "action": "message",
            "messageText": f"{disp} {industry}",
        },
    ]

    return buttons

def parse_tac_dual(text: str):
    if not text: return None
    t = text.strip()
    all_inds = set(all_industries_union())
    for industry in sorted(all_inds, key=len, reverse=True):
        if t.endswith(industry):
            fish_part = t[:-len(industry)].strip()
            fish_norm = normalize_fish_name(fish_part)
            sp = resolve_tac_key(fish_norm) or resolve_tac_key(fish_part)
            if sp and industry in get_industries(sp):
                return sp, industry
    return None

def parse_tac_triplet(text: str):
    if not text:
        return None
    t = text.strip()

    # 먼저 의도 키워드 제거
    intent = parse_detail_intent(t)
    if intent:
        # 의도 키워드 빼고 앞부분만 남김
        for suffix in ["소진현황", "주간별 어획량", "전체기간 어획량"]:
            if t.endswith(suffix):
                t = t[: -len(suffix)].strip()
                break

    for port in sorted(all_ports_union(), key=len, reverse=True):
        if t.endswith(port):
            left = t[:-len(port)].strip()
            duo = parse_tac_dual(left)
            if duo:
                sp, industry = duo
                if port in get_ports(sp, industry):
                    return sp, industry, port
    return None

def parse_detail_intent(text: str):
    if not text: return None
    t = text.strip()
    if t.endswith("소진현황"): return "depletion"
    if t.endswith("주간별 어획량"): return "weekly_ts"
    if t.endswith("전체기간 어획량"): return "season_total"
    return None

# ──────────────────────────────────────────────────────────────────────────────
# 금어기 계산
# ──────────────────────────────────────────────────────────────────────────────
def _parse_md(token: str):
    token = token.strip().replace("익년", "").strip()
    if "." in token:
        m_str, d_str = token.split(".", 1)
        m = int(re.sub(r"\D", "", m_str) or 0)
        d = int(re.sub(r"\D", "", d_str) or 1)
    else:
        m = int(re.sub(r"\D", "", token) or 0); d = 1
    return m, d

def _in_range(md, start_md, end_md):
    sm, sd = start_md; em, ed = end_md; m, d = md
    if (sm, sd) <= (em, ed): return (sm, sd) <= (m, d) <= (em, ed)
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
        except Exception as ex:
            logger.warning(f"[WARN] 금어기 파싱 실패: {name} - {period} ({ex})")
    _PARSED_PERIODS = parsed
_prepare_periods()

@lru_cache(maxsize=370)
def today_banned_fishes_cached(month: int, day: int):
    md = (month, day); banned = []
    for name, start_md, end_md in _PARSED_PERIODS:
        try:
            if _in_range(md, start_md, end_md): banned.append(name)
        except Exception: pass
    return banned

def build_fish_buttons(fishes):
    return [{"label": display_name(n), "action": "message", "messageText": display_name(n)} for n in fishes[:MAX_QR]]

def is_today_ban_query(text: str) -> bool:
    if not text: return False
    t = _PUNCT_RE.sub("", _CLEAN_RE.sub("", text.strip())).replace("의","")
    return any(tok in t for tok in INTENT_TIME_TOKENS) and ("금어기" in t)

def extract_month_query(text: str):
    if not text: return None
    m1 = re.search(r"(\d{1,2})\s*월.*금어기", text)
    m2 = re.search(r"금어기.*?(\d{1,2})\s*월", text)
    m = m1 or m2
    if not m: return None
    try:
        month = int(m.group(1))
        if 1 <= month <= 12: return month
    except: pass
    return None

# ──────────────────────────────────────────────────────────────────────────────
# 렌더러
# ──────────────────────────────────────────────────────────────────────────────
def render_weekly_report(fish_norm, industry, port, data, ref_date=None):
    if not ref_date:
        ref_date = datetime.now(KST)
    sat, fri, m, week_idx, _ = week_range_and_index_for(ref_date)
    period_line = fmt_period_line(sat, fri)

    if not data:
        return f"📊 {m}월 {week_idx}주차 주간보고\n{period_line}\n\n데이터 준비중입니다."

    lines = [
        f"📊 {m}월 {week_idx}주차 주간보고",
        period_line,
        "",
        f"• 배정량: {fmt_num(data.get('배정량'))} kg",
        f"• 배분량: {fmt_num(data.get('배분량'))} kg",
        f"• 금주 포획량: {fmt_num(data.get('금주포획량'))} kg",
        f"• 누계: {fmt_num(data.get('누계'))} kg",
        f"• 배분량 소진율: {fmt_num(data.get('배분량소진율'))}%",
    ]
    if data.get("조업척수") is not None and data.get("총척수") is not None:
        lines.append(f"• 조업척수: {fmt_num(data.get('조업척수'))}척 (총 {fmt_num(data.get('총척수'))}척)")
    if data.get("총배분량소진율") is not None:
        lines.append(f"• 총 배분량 소진율: {fmt_num(data.get('총배분량소진율'))}%")
    if data.get("지난주누계량") is not None:
        lines.append(f"• 지난주 누계량: {fmt_num(data.get('지난주누계량'))} kg")
    if data.get("누락량") is not None:
        lines.append(f"• 누락량: {fmt_num(data.get('누락량'))} kg")
    return "\n".join(lines)

def render_depletion_summary(fish_norm, industry, port, rows, ref_date=None, top_n=8):
    if not ref_date:
        ref_date = datetime.now(KST)
    sat, fri, m, week_idx, _ = week_range_and_index_for(ref_date)
    period_line = fmt_period_line(sat, fri)
    disp = display_name(fish_norm)

    if not rows:
        return f"📈 {disp} {industry} — {port} 소진현황\n{period_line}\n\n데이터 준비중입니다."

    lines = [f"📈{port} 소진현황", "(period_line)", ""]
    for r in rows[:top_n]:
        lines.append(
            f"⚓{r.get('선명')}\n"
            f"할당량: {fmt_num(r.get('할당량'))} kg\n"
            f"금주소진량: {fmt_num(r.get('금주소진량'))} kg\n"
            f"누계: {fmt_num(r.get('누계'))} kg\n"
            f"잔량: {fmt_num(r.get('잔량'))} kg\n"
            f"소진율: {fmt_num(r.get('소진율_pct'))}%\n"
        )
    return "\n".join(lines).strip()

def render_weekly_vessel_catch(fish_norm, industry, port, rows, ref_date=None):
    if not ref_date:
        ref_date = datetime.now(KST)
    sat, fri, m, week_idx, _ = week_range_and_index_for(ref_date)
    period_line = fmt_period_line(sat, fri)
    disp = display_name(fish_norm)

    if not rows:
        return f"📋 {disp} {industry} — {port} 주간별 어획량\n{period_line}\n\n데이터 준비중입니다."

    lines = [f"📋{port} 주간별 어획량", "(period_line)", ""]
    for r in rows:
        lines.append(
            f"⚓{r.get('선명')}\n"
            f"주어종 어획량: {fmt_num(r.get('주어종어획량'))} kg\n"
            f"부수어획 어획량: {fmt_num(r.get('부수어획어획량'))} kg\n"
        )
    return "\n".join(lines).strip()

def render_season_vessel_catch(fish_norm, industry, port, rows, ref_date=None):
    if not ref_date:
        ref_date = datetime.now(KST)
    _, _, _, _, y = week_range_and_index_for(ref_date)
    label = season_label_from_year(y)
    disp = display_name(fish_norm)

    if not rows:
        return f"🗂 {disp} {industry} — {port} 전체기간 어획량\n{label}\n\n데이터 준비중입니다."

    lines = ["전체기간 어획량", "(25~26어기)", ""]
    for r in rows:
        lines.append(
            f"⚓{r.get('선명')}\n"
            f"주어종 어획량: {fmt_num(r.get('주어종어획량'))} kg\n"
            f"부수어획 어획량: {fmt_num(r.get('부수어획어획량'))} kg\n"
        )
    return "\n".join(lines).strip()

# ──────────────────────────────────────────────────────────────────────────────
# 도움말
# ──────────────────────────────────────────────────────────────────────────────
HELP_TEXT = (
    "🧭 사용 방법\n"
    "• '오늘 금어기' → 오늘 금어기 어종 목록\n"
    "• '8월 금어기 알려줘' → 해당 월 금어기 어종\n"
    "• 어종명을 입력하면 상세 규제(금어기/금지체장 등)를 안내합니다.\n"
    "• TAC 어종은 'TAC 살오징어' → 업종 → 선적지 → 주간보고/소진현황/어획량으로 탐색하세요.\n"
)

# ──────────────────────────────────────────────────────────────────────────────
# 라우트 (카카오 스킬 엔드포인트: /TAC)
# ──────────────────────────────────────────────────────────────────────────────
@app.route("/TAC", methods=["POST"])
def fishbot():
    try:
        req = request.get_json(force=True, silent=True) or {}
        user_text = (req.get("userRequest", {}).get("utterance") or "").strip()
        today = datetime.now(KST)

        # 도움말
        if "도움말" in user_text:
            return jsonify(build_response(HELP_TEXT, buttons=BASE_MENU))

        # 오늘 금어기 (버튼 유지)
        if is_today_ban_query(user_text):
            fishes = today_banned_fishes_cached(today.month, today.day)
            if not fishes:
                return jsonify(build_response(f"📅 오늘({today.month}월 {today.day}일) 금어기 어종은 없습니다.", buttons=BASE_MENU))
            lines = [f"📅 오늘({today.month}월 {today.day}일) 금어기 어종:"]
            lines += [f"- {get_emoji(n)} {display_name(n)}" for n in fishes]
            buttons = [{"label": display_name(n), "action":"message", "messageText": display_name(n)} for n in fishes[:MAX_QR]]
            return jsonify(build_response("\n".join(lines), buttons=buttons))

        # 월 금어기 (버튼 유지)
        m = extract_month_query(user_text)
        if m is not None:
            result = []
            for name, (sm, _), (em, _2) in _PARSED_PERIODS:
                if sm <= em:
                    if sm <= m <= em: result.append(name)
                else:
                    if m >= sm or m <= em: result.append(name)
            if not result:
                return jsonify(build_response(f"📅 {m}월 금어기 어종은 없습니다.", buttons=BASE_MENU))
            lines = [f"📅 {m}월 금어기 어종:"]
            lines += [f"- {get_emoji(n)} {display_name(n)}" for n in result]
            buttons = [{"label": display_name(n), "action":"message", "messageText": display_name(n)} for n in result[:MAX_QR]]
            return jsonify(build_response("\n".join(lines), buttons=buttons))

        # ① <어종> <업종> <선적지> (+세부 의도)
        trip = parse_tac_triplet(user_text)
        if trip:
            fish_norm, industry, port = trip
            intent = parse_detail_intent(user_text)

            if intent == "depletion":
                rows = get_depletion_rows(fish_norm, industry, port)
                text = render_depletion_summary(fish_norm, industry, port, rows, ref_date=today)
                return jsonify(build_response(text, buttons=build_port_detail_buttons(fish_norm, industry, port)))

            if intent == "weekly_ts":
                rows = get_weekly_vessel_catch(fish_norm, industry, port)
                text = render_weekly_vessel_catch(fish_norm, industry, port, rows, ref_date=today)
                return jsonify(build_response(text, buttons=build_port_detail_buttons(fish_norm, industry, port)))

            if intent == "season_total":
                rows = get_season_vessel_catch(fish_norm, industry, port)
                text = render_season_vessel_catch(fish_norm, industry, port, rows, ref_date=today)
                return jsonify(build_response(text, buttons=build_port_detail_buttons(fish_norm, industry, port)))

            # 기본: 주간보고
            data = get_weekly_report(fish_norm, industry, port)
            text = render_weekly_report(fish_norm, industry, port, data, ref_date=today)
            return jsonify(build_response(text, buttons=build_port_detail_buttons(fish_norm, industry, port)))

        # ② <어종> <업종> → 선적지 목록
        duo = parse_tac_dual(user_text)
        if duo:
            fish_norm, industry = duo
            ports = get_ports(fish_norm, industry)
            lines = [f"⛱️ {display_name(fish_norm)} {industry} 선적지 ⛱️", ""]
            lines += ports + ["", "아래 버튼을 눌러주세요."]
            return jsonify(build_response("\n".join(lines), buttons=build_port_buttons(fish_norm, industry)))

        # ③ TAC <어종> → 업종 목록
        tac_target = is_tac_list_request(user_text)
        if tac_target:
            sp = resolve_tac_key(tac_target)
            if sp:
                inds = get_industries(sp)
                lines = [f"🚢 {display_name(sp)} TAC 업종 🚢", ""]
                lines += inds + ["", "자세한 내용은 버튼을 눌러주십시오."]
                return jsonify(build_response("\n".join(lines), buttons=build_tac_industry_buttons(sp)))
            else:
                return jsonify(build_response(f"'{display_name(tac_target)}' TAC 업종 정보가 없습니다.", buttons=BASE_MENU))

        # ④ 특정 어종 상세 (※ BASE_MENU 제거, TAC 버튼만 필요 시 노출)
        fish_norm = normalize_fish_name(user_text)
        if fish_norm in fish_data:
            text, _btns_ignored = get_fish_info(fish_norm)   # ← fish_data 제거됨
            tac_btns = build_tac_entry_button_for(fish_norm)
            return jsonify(build_response(text, buttons=(tac_btns or None)))

        # 폴백
        return jsonify(build_response("제가 할 수 있는 일이 아니에요.", buttons=BASE_MENU))

    except Exception as e:
        logger.error(f"[ERROR] fishbot error: {e}", exc_info=True)
        return jsonify(build_response("⚠️ 오류가 발생했습니다. 잠시 후 다시 시도해 주세요.", buttons=BASE_MENU))

# 헬스체크
@app.route("/healthz", methods=["GET"])
def healthz():
    return "ok", 200

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    # 프로덕션 권장: gunicorn -w 4 -k gthread -b 0.0.0.0:$PORT app:app
    app.run(host="0.0.0.0", port=port)






