from flask import Flask, request
import csv, random, re, os, json
from PIL import Image, ImageEnhance
import pytesseract
import shutil
pytesseract.pytesseract.tesseract_cmd = shutil.which("tesseract")
from pathlib import Path

# ===== 設定 =====
UPLOAD_FOLDER = "uploads"
QUESTION_COUNT = 80

app = Flask(__name__)
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# ===== 単語帳読み込み（大文字保持）=====
WORDS = {}
DISPLAY_WORDS = {}

with open("words.csv", encoding="utf-8") as f:
    for row in csv.DictReader(f):
        original = row["word"].strip()
        lower = original.lower()

        WORDS[lower] = row["meaning"].strip()
        DISPLAY_WORDS[lower] = original

# ===== HTML =====
HTML_HEAD = """
<!doctype html>
<html lang="ja">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.2/dist/css/bootstrap.min.css" rel="stylesheet">
<title>英単語OCRテスト</title>
</head>
<body class="bg-light">
<div class="container py-4">
<h3 class="text-center mb-3">📸 JPG画像 → 英単語テスト</h3>
<div class="card p-3 shadow-sm mb-4">
<form method="POST" enctype="multipart/form-data">
<input class="form-control mb-3" type="file" name="images" accept=".jpg,.jpeg" multiple required>
<button class="btn btn-primary w-100">テスト作成</button>
</form>
</div>
"""

HTML_FOOT = "</div></body></html>"

# ===== OCR =====
def ocr_image(path):

    try:

        img = Image.open(path).convert("L")
        img.thumbnail((500, 500))  # これだけでOK
        img = ImageEnhance.Contrast(img).enhance(1.3)

        config = "--oem 3 --psm 11"
        text = pytesseract.image_to_string(img, lang="eng", config=config)

        text = text.replace("0","o").replace("1","l")

        raw_words = re.findall(r"[A-Za-z]+(?:-[A-Za-z]+)*", text)

        found = set()

        for w in raw_words:

            key = w.lower()

            if key in WORDS:
                found.add(key)

        return found

    except Exception as e:

        print("OCR失敗:", e)
        return set()

# ===== クイズ生成 =====
def make_quiz_from_words(found_words):

    if not found_words:
        return[]
        
    targets = list(found_words)

    if len(targets) > QUESTION_COUNT:
        targets = random.sample(targets, QUESTION_COUNT)

    quizzes = []
    meanings = list(WORDS.values())

    for key in targets:

        display_word = DISPLAY_WORDS[key]
        meaning = WORDS[key]

        q_type = random.choice(["en_to_ja", "ja_to_en"])

        if q_type == "en_to_ja":

            question = f"【英→日】{display_word} の意味は？"
            correct = meaning
            wrongs = random.sample(
                [m for m in meanings if m != meaning], 3
            )
            choices = wrongs + [correct]

        else:

            question = f"【日→英】「{meaning}」に最も近い英単語は？"
            correct = display_word
            wrongs = random.sample(
                [DISPLAY_WORDS[w] for w in WORDS if w != key], 3
            )
            choices = wrongs + [correct]

        random.shuffle(choices)

        quizzes.append((question, correct, choices))

    return quizzes

# ===== Flask =====
@app.route("/", methods=["GET", "POST"])
def index():

    html = HTML_HEAD

    if request.method == "POST":

        files = request.files.getlist("images")[:2]
        all_words = set()

        for file in files:

            if file.filename.lower().endswith((".jpg", ".jpeg")):

                path = Path(UPLOAD_FOLDER) / file.filename
                file.save(path)

                all_words |= ocr_image(path)

        quizzes = make_quiz_from_words(all_words)

        if not quizzes:

            html += "<p class='text-danger'>単語が見つかりませんでした。</p>"

        else:

            html += f"<p class='fw-bold'>作成問題数：{len(quizzes)} 問</p>"

            html += """
<script>
let score = 0;
let answered = 0;

function checkAnswer(btn, correct) {

    const buttons = btn.parentElement.querySelectorAll("button");
    buttons.forEach(b => b.disabled = true);

    answered++;

    if (btn.textContent.trim() === correct.trim()) {

        btn.classList.remove("btn-outline-primary");
        btn.classList.add("btn-success");
        score++;

    } else {

        btn.classList.remove("btn-outline-primary");
        btn.classList.add("btn-danger");
        alert("正解は「" + correct + "」");

    }

    document.getElementById("score").innerText = score;
    document.getElementById("rate").innerText =
        Math.round(score / answered * 100);
}
</script>

<div class="mb-3">
スコア：<b><span id="score">0</span></b>
正答率：<b><span id="rate">0</span>%</b>
</div>
"""

            for i, (q, correct, choices) in enumerate(quizzes, 1):

                html += f"""
<div class="card mb-3 p-3 shadow-sm">
<p class="fw-bold">Q{i}. {q}</p>
<div class="d-grid gap-2">
"""

                safe_correct = json.dumps(correct)

                for c in choices:
                    html += f'<button class="btn btn-outline-primary" onclick=\'checkAnswer(this, {safe_correct})\'>{c}</button>'

                html += "</div></div>"

    html += HTML_FOOT
    return html


import os

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
