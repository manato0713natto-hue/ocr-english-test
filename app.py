from flask import Flask, request
import csv, random, re, os, json, uuid
from PIL import Image, ImageEnhance
import pytesseract
import shutil
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
import difflib

# ===== EasyOCR =====
import easyocr
reader = easyocr.Reader(['en'], gpu=False)

pytesseract.pytesseract.tesseract_cmd = shutil.which("tesseract")

# ===== 設定 =====
UPLOAD_FOLDER = "uploads"
QUESTION_COUNT = 20
MAX_FILES = 2   # ← EasyOCR使うので控えめ
MAX_TOTAL_SIZE = 2 * 1024 * 1024

app = Flask(__name__)
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# ===== 単語帳 =====
WORDS = {}
DISPLAY_WORDS = {}

with open("words.csv", encoding="utf-8") as f:
    for row in csv.DictReader(f):
        original = row["word"].strip()
        lower = original.lower()
        WORDS[lower] = row["meaning"].strip()
        DISPLAY_WORDS[lower] = original

# ===== OCR補正 =====
def correct_word(word):
    candidates = list(WORDS.keys())
    match = difflib.get_close_matches(word, candidates, n=1, cutoff=0.8)
    return match[0] if match else None

# ===== Tesseract =====
def ocr_tesseract(path):
    try:
        img = Image.open(path).convert("L")
        img.thumbnail((600, 600))
        img = ImageEnhance.Contrast(img).enhance(1.3)

        config = "--oem 3 --psm 6"
        text = pytesseract.image_to_string(img, lang="eng", config=config)

        words = re.findall(r"[A-Za-z]{3,}", text)

        result = set()
        for w in words:
            key = w.lower()
            if key in WORDS:
                result.add(key)
            else:
                corrected = correct_word(key)
                if corrected:
                    result.add(corrected)

        return result

    except:
        return set()

# ===== EasyOCR（フォールバック）=====
def ocr_easy(path):
    try:
        result = reader.readtext(path, detail=0)
        words = re.findall(r"[A-Za-z]{3,}", " ".join(result))

        found = set()
        for w in words:
            key = w.lower()
            if key in WORDS:
                found.add(key)
            else:
                corrected = correct_word(key)
                if corrected:
                    found.add(corrected)

        return found

    except:
        return set()

# ===== ハイブリッドOCR =====
def smart_ocr(path):
    words = ocr_tesseract(path)

    # 少なすぎたらEasyOCR
    if len(words) < 3:
        words = ocr_easy(path)

    return words

# ===== クイズ生成 =====
def make_quiz_from_words(found_words):

    if not found_words:
        return []

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

<h3 class="text-center mb-3">📸 OCR英単語テスト（高精度版）</h3>

<div class="card p-3 mb-4">
<form method="POST" enctype="multipart/form-data" onsubmit="showLoading()">
<input class="form-control mb-3" type="file" name="images" accept=".jpg,.jpeg" multiple required>
<button class="btn btn-primary w-100">テスト作成</button>
</form>
</div>

<div id="loading" style="display:none;" class="text-center">
<div class="spinner-border"></div>
<p>高精度OCR処理中...</p>
</div>

<script>
function showLoading(){
    document.getElementById("loading").style.display="block";
}
</script>
"""

HTML_FOOT = "</div></body></html>"

# ===== Flask =====
@app.route("/", methods=["GET", "POST"])
def index():

    html = HTML_HEAD

    if request.method == "POST":

        files = request.files.getlist("images")[:MAX_FILES]

        # サイズ制限
        total = 0
        for f in files:
            data = f.read()
            total += len(data)
            f.seek(0)

        if total > MAX_TOTAL_SIZE:
            return html + "<p class='text-danger'>サイズ大きすぎ</p>" + HTML_FOOT

        def process(file):
            if file.filename.lower().endswith((".jpg", ".jpeg")):

                path = Path(UPLOAD_FOLDER) / f"{uuid.uuid4()}.jpg"
                file.save(path)

                words = smart_ocr(path)

                try:
                    os.remove(path)
                except:
                    pass

                return words

            return set()

        all_words = set()

        with ThreadPoolExecutor(max_workers=2) as ex:
            results = list(ex.map(process, files))

        for r in results:
            all_words |= r

        quizzes = make_quiz_from_words(all_words)

        if not quizzes:
            html += "<p class='text-danger'>単語検出失敗</p>"

        else:

            html += f"<p>問題数：{len(quizzes)}</p>"

            html += "<div id='score'>0</div>"

            for i, (q, correct, choices) in enumerate(quizzes, 1):

                html += f"<p>{i}. {q}</p>"

                safe = json.dumps(correct)

                for c in choices:
                    html += f"<button onclick='check(this,{safe})'>{c}</button><br>"

        html += """
<script>
let score=0;
function check(btn,correct){
    if(btn.innerText.trim()==correct.trim()){
        btn.style.background="green";
        score++;
    }else{
        btn.style.background="red";
        alert("正解:"+correct);
    }
    document.getElementById("score").innerText=score;
}
</script>
"""

    html += HTML_FOOT
    return html


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
