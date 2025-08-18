# TAC_data.py
# TAC 대상 어종/업종/선적지 메타데이터 (변하지 않는 정적 정보)

from typing import Dict, List

# 표준 어종 키는 fish_utils.normalize_fish_name() 결과와 동일하게 관리하세요.
# display/aliases는 사용자 입력 보정 및 표기를 위한 용도입니다.
TAC_DATA: Dict[str, dict] = {
    # ── 예시: 살오징어 ────────────────────────────────────────────────────────
    "살오징어": {
        "display": "살오징어",
        "aliases": ["살오징어(오징어)"],
        "industries": {
            "근해채낚기": {
                "ports": ["부산", "울산", "강원", "경북", "경남", "제주", "전남", "충남"],
            },
            "동해구중형트롤": { "ports": ["강원", "경북"] },
            "대형트롤":     { "ports": ["부산", "경남", "전남"] },
            "대형선망":     { "ports": ["부산", "경남"] },
            "쌍끌이대형저인망": { "ports": ["부산", "인천", "전남", "경남"] },
            "근해자망":     { "ports": ["부산", "인천", "울산", "충남", "전북", "전남", "경북", "경남", "제주"] },
            "서남해구쌍끌이중형저인망": { "ports": ["경남", "전남"] },
        },
    },

    # ── 확장: 꽃게/고등어 등 TAC 대상 어종을 여기에 추가 ─────────────
    # "꽃게": {
    #   "display": "꽃게",
    #   "aliases": [],
    #   "industries": {
    #       "연안자망": {"ports": ["부산", ...]},
    #       ...
    #   }
    # },
}

# ──────────────────────────────────────────────────────────────────────────────
# 헬퍼 함수 (앱에서 이 함수들만 사용하면 구조가 안 꼬입니다)
# ──────────────────────────────────────────────────────────────────────────────
def is_tac_species(fish_norm: str) -> bool:
    return fish_norm in TAC_DATA

def get_display_name(fish_norm: str) -> str:
    return TAC_DATA.get(fish_norm, {}).get("display", fish_norm)

def get_aliases(fish_norm: str) -> List[str]:
    return TAC_DATA.get(fish_norm, {}).get("aliases", [])

def get_industries(fish_norm: str) -> List[str]:
    return list(TAC_DATA.get(fish_norm, {}).get("industries", {}).keys())

def get_ports(fish_norm: str, industry: str) -> List[str]:
    inds = TAC_DATA.get(fish_norm, {}).get("industries", {})
    return list(inds.get(industry, {}).get("ports", []))

def all_industries_union() -> List[str]:
    s = set()
    for sp in TAC_DATA.values():
        s.update(sp.get("industries", {}).keys())
    return sorted(s)

def all_ports_union() -> List[str]:
    s = set()
    for sp in TAC_DATA.values():
        for ind in sp.get("industries", {}).values():
            s.update(ind.get("ports", []))
    return sorted(s)
