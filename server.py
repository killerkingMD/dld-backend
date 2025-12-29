from flask import Flask, request, jsonify, Response
import requests
import re
import html

app = Flask(__name__)

# =========================================================
# HEADERS REAIS (ANDROID)
# =========================================================
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Linux; Android 13; Mobile) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Mobile Safari/537.36"
    ),
    "Accept": "*/*",
    "Referer": "https://www.kwai.com/"
}

# =========================================================
# UTILS
# =========================================================
def sanitize_filename(name: str) -> str:
    name = html.unescape(name)
    name = re.sub(r'[\\/:*?"<>|]', '', name)
    return name.strip()[:80]


def resolve_short_url(url):
    r = requests.get(url, allow_redirects=True, headers=HEADERS, timeout=15)
    return r.url


def extract_video_id(url):
    if "/photo/" in url or "album" in url:
        raise Exception("Esse link não é um vídeo")

    m = re.search(r"/video/(\d+)", url)
    if not m:
        raise Exception("ID do vídeo não encontrado")

    return m.group(1)


def fetch_video_data(video_id):
    """
    Extrai:
    - URL MP4 real
    - Título real do vídeo
    """
    video_page = f"https://www.kwai.com/@user/video/{video_id}"

    r = requests.get(video_page, headers=HEADERS, timeout=20)
    html_data = r.text

    # ---------- TITLE ----------
    title_match = re.search(
        r'"name":"([^"]+)"',
        html_data
    )
    title = sanitize_filename(title_match.group(1)) if title_match else "video_kwai"

    # ---------- MP4 ----------
    matches = re.findall(
        r'(https://[^"]+\.mp4[^"]*)',
        html_data
    )

    for url in matches:
        if "kwai" in url:
            return title, url.replace("\\u002F", "/")

    raise Exception("URL MP4 não encontrada")


# =========================================================
# ROUTES
# =========================================================
@app.route("/", methods=["GET"])
def index():
    return jsonify({"status": "online"})


@app.route("/download", methods=["POST"])
def download():
    try:
        data = request.get_json(force=True)
        url = data.get("url")

        if not url:
            return jsonify({"error": "URL ausente"}), 400

        final_url = resolve_short_url(url)
        video_id = extract_video_id(final_url)
        title, video_url = fetch_video_data(video_id)

        # =================================================
        # STREAMING REAL
        # =================================================
        def stream():
            with requests.get(
                video_url,
                headers=HEADERS,
                stream=True,
                timeout=60
            ) as r:
                r.raise_for_status()
                for chunk in r.iter_content(chunk_size=8192):
                    if chunk:
                        yield chunk

        return Response(
            stream(),
            content_type="video/mp4",
            headers={
                "X-Video-Title": title,
                "Cache-Control": "no-cache"
            }
        )

    except Exception as e:
        return jsonify({
            "error": "Falha no download",
            "details": str(e)
        }), 400


# =========================================================
# START
# =========================================================
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)