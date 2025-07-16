from flask import Flask, request, jsonify
import openai

openai.api_key = "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"

app = Flask(__name__)

context = """
당신은 한국의 수산자원관리법 전문가입니다. 아래 내용을 바탕으로 사용자 질문에 답해주세요.

[요약]
제13조: 무허가 어업은 처벌 대상입니다.
제14조: 금어기/크기 제한 위반 시 과태료가 부과됩니다.
제15조: TAC 제도는 정부가 어종별 총허용어획량을 정하는 제도입니다.
"""

@app.route("/fisheriesbot", methods=["POST"])
def fisheriesbot():
    user_input = request.json.get("userRequest")["utterance"]
    prompt = context + f"\n\n질문: {user_input}\n답변:"

    response = openai.ChatCompletion.create(
        model="gpt-4",
        messages=[
            {"role": "system", "content": "수산자원관리법 전문가처럼 대답하세요."},
            {"role": "user", "content": prompt}
        ],
        temperature=0.3,
        max_tokens=500
    )

    answer = response.choices[0].message.content.strip()

    return jsonify({
        "version": "2.0",
        "template": {
            "outputs": [{
                "simpleText": {"text": answer}
            }]
        }
    })

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
