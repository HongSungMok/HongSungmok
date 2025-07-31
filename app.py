from flask import Flask, request, jsonify
from datetime import datetime
import logging
import os
import re

from fish_data import fish_data
from fish_utils import (
    normalize_fish_name,
    get_fish_info,
    get_fishes_in_seasonal_ban,
)

app = Flask(__name__)
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 사용자에게 보여줄 어종명 맵핑
display_name_map = {
    "조피볼락(우럭)": "조피볼락",
    "넙치(광어)": "넙치",
    "살오징어(오징어)": "살오징어",
    "전복(전복류)": "전복",
    "제주소라": "제주소라",
}

# 이모지
fish_emojis = {
    "대게": "🦀", "붉은대게": "🦀", "꽃게": "🦀",
    "오분자기": "🐚", "키조개": "🦪", "제주소라": "🐚",
    "주꾸미": "🐙", "대문어": "🐙", "참문어": "🐙",
    "낙지": "🦑", "살오징어(오징어)": "🦑",
    "해삼": "🌊", "넓미역": "🌿", "우뭇가사리": "🌿", "톳": "🌿",
}

def get_display_name(name: str) -> str:
    return display_name_map.get(name, name)

def get_emoji(name: str) -> str:
    return fish_emojis.get(name, "🐟")

def build_response(text, buttons=None):
    response = {
        "version": "2.0",
        "template": {
            "outputs": [{"simpleText": {"text": text}}]
        }
    }
    if buttons:
        response["template"]["quickReplies"] = buttons
    return response

@app.route("/TAC", methods=["POST"])
def fishbot():
    try:
        req = request.get_json()
        user_text = req.get("userRequest", {}).get("utterance", "").strip()
        today = datetime.today()
        logger.info(f"사용자 입력: {user_text}")

        # 오늘 금어기 어종
        if re.search(r"(오늘|지금|현재|금일|투데이).*(금어기)", user_text):
            fishes = get_fishes_in_seasonal_ban(fish_data, today)
            if not fishes:
                return jsonify(build_response(f"📅 오늘({today.month}월 {today.day}일) 금어기 어종은 없습니다."))
            lines = [f"📅 오늘({today.month}월 {today.day}일) 금어기 어종:"]
            buttons = []
            for name in fishes:
                disp = get_display_name(name)
                emoji = get_emoji(name)
                lines.append(f"- {emoji} {disp}")
                buttons.append({"label": disp, "action": "message", "messageText": disp})
            return jsonify(build_response("\n".join(lines), buttons=buttons))

        # 월별 금어기 어종
        m = re.search(r"(\d{1,2})월.*금어기", user_text)
        if m:
            month = int(m.group(1))
            result = []
            for name, info in fish_data.items():
                period = info.get("금어기")
                if not period or "~" not in period:
                    continue
                try:
                    start, end = period.split("~")
                    sm = int(start.strip().split(".")[0])
                    em = int(end.replace("익년", "").strip().split(".")[0])
                    if sm <= em:
                        if sm <= month <= em:
                            result.append(name)
                    else:
                        if month >= sm or month <= em:
                            result.append(name)
                except:
                    continue
            if not result:
                return jsonify(build_response(f"📅 {month}월 금어기 어종은 없습니다."))
            lines = [f"📅 {month}월 금어기 어종:"]
            buttons = []
            for name in result:
                disp = get_display_name(name)
                emoji = get_emoji(name)
                lines.append(f"- {emoji} {disp}")
                buttons.append({"label": disp, "action": "message", "messageText": disp})
            return jsonify(build_response("\n".join(lines), buttons=buttons))

        # 특정 어종 조회
        fish_norm = normalize_fish_name(user_text)
        text, buttons = get_fish_info(fish_norm, fish_data)
        return jsonify(build_response(text, buttons))

    except Exception as e:
        logger.error(f"오류 발생: {e}")
        return jsonify(build_response("⚠️ 오류가 발생했습니다. 잠시 후 다시 시도해 주세요."))

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)