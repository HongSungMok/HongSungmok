from datetime import datetime
from flask import Flask, request, jsonify
import os
import requests
import traceback
from fish_data import fish_data  # fish_data는 dict 형태

app = Flask(__name__)

OPENROUTER_API_KEY = os.environ.get("OPENROUTER_API_KEY")
OPENROUTER_API_URL = "https://openrouter.ai/api/v1/chat/completions"

context = """
[요약]
[제1조] 목적 – 수산자원의 보호·회복·조성 등 관리 및 어업인의 소득증대 목적
[제2조] 정의 – 수산자원, 총허용어획량, 수산자원조성, 바다목장 정의
[제3조] 수산자원의 조사·연구 – 정부가 자원 상태 조사 책임
[제4조] 수산자원 조성 – 어초·해조장 설치 및 종자 방류 등 조성 가능
[제5조] 허가·등록 – 어업활동을 위한 허가/등록 절차 규정
[제6조] 허가 조건 – 허가 시 어업 방식·장비·어획량 조건 명시 가능
[제7조] 조업 금지 구역 – 어업 종류별 금지구역 예: 외끌이·트롤어업
[제8조] 휴어기 설정 – 자원 상태 등 고려하여 설정 가능
[제9조] 어장 안전관리 – 안전사고 예방 규정
[제10조] 어업 질서 유지 – 자원 보호와 질서 확립에 부합하도록 규제
[제11조] 정밀조사·평가 계획 – 자원 현황 평가 및 회복계획 수립 의무
[제12조] 어획물 등의 조사
  ① 해수부장관 또는 시·도지사는 시장·공판장·어선 등에 출입하여 어획물 종류·어획량 등을 조사할 수 있다.
  ② 조사 관원은 신분증명서를 지니고 제시해야 하며, 승선조사 전 어선주와 사전 협의해야 한다.
[제13조] 조성 정보 제출
  어획 실적·어장환경·어법 등 조사 데이터를 국립수산과학원에 제출해야 한다.
[제14조] 비어업인의 포획 제한
  투망·반두·외줄낚시 등 특정 어구는 비어업인의 사용이 제한됨
[제15조] 중복 자망 사용 승인
  이중 이상의 자망 사용은 별도로 승인 받아야 함
[제16조] 휴어기 설정
  해수부장관은 수산자원 보호를 위해 일정 기간 회피 조업(휴어기)을 설정할 수 있음
[제17조] 어장 안전·환경 보호
  어장 안전사고 예방 및 오염 방지를 위해 어장 환경을 관리해야 함
[제18조] 금지 수단
  폭발물·전기장치 등 금지 수단으로 어획하면 강력한 처벌 대상임

[형벌·벌칙 요약]
[제64조] 2년 이하 징역 또는 2천만 원 이하 벌금:
 • 금어기·금지체장 어업(제14조 위반)
 • 어장 안전·환경 무시(제17조 위반)
 • 휴어기 중 어업(제19조 제2항 위반)
 • 어선 관련 불법 행위(제22조 위반)
 • 폭발물·전류 등 금지수단 사용(제25조 제1항 위반)
 • 유해화학물질 무허가 사용(제25조 제2항 위반)
 • 수산자원 보호 명령 위반, 할당량 초과 어획 등
[제65조] 1천만 원 이하 벌금:
 • 조업금지구역 어업(제15조 위반)
 • 비어업인의 금지 포획(제18조 위반)
 • 2중 자망 무단 사용(제23조 3항 위반)
 • 금지 어구 제작·판매·보관(제24조 위반) 등
[제66조] 500만 원 이하 벌금:
 • 오염행위, 어획량 초과, 명령 불이행 등
[제67조] 300만 원 이하 벌금:
 • 불법 어획물 방류명령 불이행, 허위 보고, 지정 외 거래 등
"""

# 날짜 범위 검사 함수
def is_date_in_range(period: str, today: datetime) -> bool:
    try:
        start_str, end_str = period.split("~")
        start_month, start_day = map(int, start_str.split("."))
        if "익년" in end_str:
            end_str = end_str.replace("익년", "")
            end_month, end_day = map(int, end_str.strip().split("."))
            start_date = datetime(today.year, start_month, start_day)
            end_date = datetime(today.year + 1, end_month, end_day)
        else:
            end_month, end_day = map(int, end_str.strip().split("."))
            start_date = datetime(today.year, start_month, start_day)
            end_date = datetime(today.year, end_month, end_day)
        return start_date <= today <= end_date
    except Exception:
        return False

# 금어기 기간 필터링
def filter_periods(periods, today):
    if isinstance(periods, dict):
        valid_periods = {}
        for key, period in periods.items():
            if is_date_in_range(period, today):
                valid_periods[key] = period
        return valid_periods if valid_periods else None
    elif isinstance(periods, str):
        return periods if is_date_in_range(periods, today) else None
    return None

# 어종 정보 반환 함수
def get_fish_info(fish_name, fish_data, today=None):
    if today is None:
        today = datetime.today()

    fish = fish_data.get(fish_name)
    if not fish:
        return f"'{fish_name}'에 대한 정보가 없습니다."

    # 금어기 필터링
    금어기 = None
    for key in ["금어기", "유자망_금어기", "근해채낚기_연안복합_정치망_금어기", "지역별_금어기", "금어기_예외"]:
        if key in fish:
            filtered = filter_periods(fish[key], today)
            if filtered:
                if isinstance(filtered, dict):
                    금어기 = "; ".join(f"{k}: {v}" for k, v in filtered.items())
                else:
                    금어기 = filtered
                break
    if not 금어기:
        금어기 = "없음"

    # 금지체장 필터링
    금지체장 = None
    if "금지체장" in fish:
        금지체장 = fish["금지체장"]
        if isinstance(금지체장, dict):
            if "기본" in 금지체장:
                금지체장 = 금지체장["기본"]
            else:
                금지체장 = list(금지체장.values())[0]
    else:
        금지체장 = "없음"
    if not 금지체장:
        금지체장 = "없음"

    # 예외사항 및 포획비율 제한 정보
    예외사항 = fish.get("금어기_해역_특이사항") or fish.get("금어기_예외") or fish.get("금어기_특정해역") or fish.get("금어기_추가")
    포획비율 = fish.get("포획비율제한")

    response = f"금어기: {금어기}\n금지체장: {금지체장}"
    if 예외사항:
        response += f"\n예외사항: {예외사항}"
    if 포획비율:
        response += f"\n포획비율제한: {포획비율}"
    return response

# OpenRouter API 호출 함수
def call_openrouter_api(messages):
    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json"
    }
    payload = {
        "model": "gpt-3.5-turbo",
        "messages": messages,
        "temperature": 0.3,
        "max_tokens": 300
    }
    try:
        response = requests.post(OPENROUTER_API_URL, headers=headers, json=payload)
        response.raise_for_status()
        data = response.json()
        if isinstance(data, dict) and "choices" in data and data["choices"]:
            content = data["choices"][0]["message"]["content"]
            return str(content) if content is not None else "[API 응답 내용 없음]"
        else:
            return "[API 응답 오류]"
    except Exception as e:
        print(f"API 호출 오류: {e}")
        return "[API 호출 오류가 발생했습니다.]"

# 값 포맷팅 함수
def format_value(val):
    if isinstance(val, dict):
        return "\n".join(f"- {k}: {v}" for k, v in val.items())
    elif isinstance(val, list):
        lines = []
        for item in val:
            if isinstance(item, dict):
                lines.append(", ".join(f"{k}: {v}" for k, v in item.items()))
            else:
                lines.append(str(item))
        return "\n".join(f"- {line}" for line in lines)
    else:
        return str(val)

@app.route("/TAC", methods=["POST"])
def TAC():
    try:
        data = request.json
        user_input = data.get("userRequest", {}).get("utterance", "").strip()

        주요_어종 = [
            "고등어", "전갱이", "삼치", "갈치", "도루묵",
            "참조기", "오징어", "대게", "붉은대게", "제주소라",
            "꽃게", "참홍어", "키조개", "개조개", "바지락"
        ]

        if not user_input:
            answer = "입력이 비어 있습니다. 질문을 입력해주세요."
            quick_replies = []
        else:
            fish_key = None
            for name in fish_data.keys():
                if name in user_input:
                    fish_key = name
                    break

            if fish_key:
                # get_fish_info 호출
                answer = f"[{fish_key} 정보]\n\n" + get_fish_info(fish_key, fish_data)
                # 버튼 생성 (주요 어종 중 현재 어종 제외)
                quick_replies = [
                    {
                        "messageText": f"{name} 금어기",
                        "action": "message",
                        "label": name
                    }
                    for name in 주요_어종 if name != fish_key
                ]
            else:
                if not OPENROUTER_API_KEY:
                    answer = "서버 환경 변수에 OPENROUTER_API_KEY가 설정되어 있지 않습니다."
                    quick_replies = []
                else:
                    messages = [
                        {
                            "role": "system",
                            "content": "당신은 수산자원관리법 전문가입니다. 질문에 정확하고 간결하게 답변하세요."
                        },
                        {
                            "role": "user",
                            "content": context + f"\n\n질문: {user_input}\n답변:"
                        }
                    ]
                    answer = call_openrouter_api(messages)
                    quick_replies = []

        if not isinstance(answer, str):
            answer = str(answer)

        if len(answer) > 1900:
            answer = answer[:1900] + "\n\n[답변이 너무 길어 일부만 표시합니다.]"

        if not answer.strip():
            answer = "답변이 없습니다."

        response_json = {
            "version": "2.0",
            "template": {
                "outputs": [
                    {
                        "simpleText": {
                            "text": answer
                        }
                    }
                ],
                "quickReplies": quick_replies
            }
        }
        return jsonify(response_json)

    except Exception:
        traceback.print_exc()
        return jsonify({
            "version": "2.0",
            "template": {
                "outputs": [
                    {
                        "simpleText": {
                            "text": "오류가 발생했습니다. 다시 시도해주세요."
                        }
                    }
                ]
            }
        })

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
