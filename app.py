from flask import Flask, request, jsonify
import os
import requests
import traceback
from fish_data import fish_data

app = Flask(__name__)

# OpenRouter API 키 환경변수에서 읽기
OPENROUTER_API_KEY = os.environ.get("OPENROUTER_API_KEY")
OPENROUTER_API_URL = "https://openrouter.ai/api/v1/chat/completions"

# 법 조문 전문 및 요약 (주신 내용)
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
        if isinstance(data, dict) and "choices" in data:
            return data["choices"][0]["message"]["content"]
        else:
            return f"API 응답 형식 오류: {data}"
    except Exception as e:
        return f"API 호출 중 오류 발생: {str(e)}"

@app.route("/TAC", methods=["POST"])
def TAC():
    try:
        data = request.json
        user_input = data.get("userRequest", {}).get("utterance", "").strip()
        if not user_input:
            return jsonify({
                "version": "2.0",
                "template": {
                    "outputs": [{"simpleText": {"text": "입력이 비어 있습니다. 질문을 입력해주세요."}}]
                }
            })

        # 금어기/금지체장에 해당하는 어종 있는지 우선 체크
        for fish_name, info in fish_data.items():
            if fish_name in user_input:
                response_parts = []
                if info.get("금어기"):
                    response_parts.append(f"[{fish_name}]의 금어기는 {info['금어기']}입니다.")
                if info.get("금지체장"):
                    response_parts.append(f"[{fish_name}]의 금지체장은 {info['금지체장']}입니다.")
                if response_parts:
                    return jsonify({
                        "version": "2.0",
                        "template": {
                            "outputs": [{"simpleText": {"text": "\n".join(response_parts)}}]
                        }
                    })

        # fish_data에 해당 없으면 OpenRouter API 호출
        messages = [
            {"role": "system", "content": "당신은 수산자원관리법 전문가입니다. 질문에 정확하고 간결하게 답변하세요."},
            {"role": "user", "content": context + f"\n\n질문: {user_input}\n답변:"}
        ]

        answer = call_openrouter_api(messages)

    except Exception as e:
        traceback.print_exc()
        answer = f"오류 발생: {str(e)}"

    return jsonify({
        "version": "2.0",
        "template": {
            "outputs": [{"simpleText": {"text": answer}}]
        }
    })

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)