# TAC_data_sources.py
# "운영 데이터" 접근 레이어 (주간보고/소진현황/주간·시즌 어획량)
# → 초기엔 인메모리 샘플, 이후 Google Sheets/JSON/DB로 교체 시
#    아래 함수들 내부만 바꾸면 됩니다.

from typing import Dict, List, Optional, Tuple

# ── 주간보고(요약) ───────────────────────────────────────────────────────────
# 키: (어종, 업종, 선적지)
WEEKLY_REPORT: Dict[Tuple[str, str, str], Dict] = {
    ("살오징어", "근해채낚기", "부산"): {
        "배정량": 1_536_000,
        "배분량": 1_105_800,
        "금주포획량": 6_212.0,
        "누계": 42_261.10,
        "배분량소진율": 3.8,
        "조업척수": 5,
        "총척수": 27,
        "총배분량소진율": 2.8,
        "지난주누계량": 32_242.60,
        "누락량": 3_806.50,
    }
}

# ── 소진현황(선박별) ─────────────────────────────────────────────────────────
DEPLETION_ROWS: Dict[Tuple[str, str, str], List[Dict]] = {
    ("살오징어", "근해채낚기", "부산"): [
        {"선명":"민기호","할당량":27_670,"금주소진량":0,"누계":2_591.6,"잔량":27_670.0,"소진율_pct":3.7},
        {"선명":"민지호","할당량":70_750,"금주소진량":516,"누계":2_863.0,"잔량":68_158.4,"소진율_pct":3.7},
        {"선명":"귀원호","할당량":97_250,"금주소진량":148,"누계":3_017.5,"잔량":94_232.5,"소진율_pct":3.1},
        {"선명":"훈녕호","할당량":64_200,"금주소진량":0,"누계":630.0,"잔량":63_570.0,"소진율_pct":1.0},
        {"선명":"진수호","할당량":93_600,"금주소진량":0,"누계":889.0,"잔량":92_711.0,"소진율_pct":0.9},
    ]
}

# ── 어획량(선박별) 포맷 — 주간/시즌 공통 ─────────────────────────────────────
# 요청 포맷:
#   어선명
#   주어종 어획량: xx kg
#   부수어획 어획량: xx kg
# 동일 포맷으로 주간/전체기간 모두 구성합니다.
VESSEL_WEEKLY_CATCH: Dict[Tuple[str, str, str], List[Dict]] = {
    ("살오징어", "근해채낚기", "부산"): [
        {"선명":"민기호",      "주어종어획량": 420.0, "부수어획어획량": 18.0},
        {"선명":"민지호","주어종어획량": 516.0, "부수어획어획량": 22.0},
        {"선명":"귀원호",      "주어종어획량": 148.0, "부수어획어획량": 9.0},
    ]
}

VESSEL_SEASON_CATCH: Dict[Tuple[str, str, str], List[Dict]] = {
    ("살오징어", "근해채낚기", "부산"): [
        {"선명":"민기호",      "주어종어획량": 2_591.6, "부수어획어획량": 110.0},
        {"선명":"민지호","주어종어획량": 2_863.0, "부수어획어획량": 135.0},
        {"선명":"귀원호",      "주어종어획량": 3_017.5, "부수어획어획량": 128.0},
    ]
}

# ── 공개 인터페이스 ──────────────────────────────────────────────────────────
def get_weekly_report(fish_norm: str, industry: str, port: str) -> Optional[Dict]:
    return WEEKLY_REPORT.get((fish_norm, industry, port))

def get_depletion_rows(fish_norm: str, industry: str, port: str) -> List[Dict]:
    return DEPLETION_ROWS.get((fish_norm, industry, port), [])

def get_weekly_vessel_catch(fish_norm: str, industry: str, port: str) -> List[Dict]:
    return VESSEL_WEEKLY_CATCH.get((fish_norm, industry, port), [])

def get_season_vessel_catch(fish_norm: str, industry: str, port: str) -> List[Dict]:
    return VESSEL_SEASON_CATCH.get((fish_norm, industry, port), [])
