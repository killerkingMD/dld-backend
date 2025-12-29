from flask import Flask, request, jsonify, Response
import requests
import re

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
def resolve_short_url(url):
    r = requests.get(url, allow_redirects=True, headers=HEADERS, timeout=15)
    return r.url


def extract_video_id(url):
    """
    Aceita SOMENTE URLs de vídeo
    """
    if "/photo/" in url or "album" in url:
        raise Exception("Esse link não é um vídeo (photo/album)")

    m = re.search(r"/video/(\d+)", url)
    if not m:
        raise Exception("ID do vídeo não encontrado")

    return m.group(1)


def fetch_video_url(video_id):
    """
    Método estável: resolve direto do HTML
    (API privada do Kwai quebra constantemente)
    """
    video_page = f"https://www.kwai.com/@user/video/{video_id}"

    r = requests.get(video_page, headers=HEADERS, timeout=20)
    html = r.text

    # Busca URLs MP4 reais
    matches = re.findall(
        r'(https://[^"]+\.mp4[^"]*)',
        html
    )

    for url in matches:
        if "kwai" in url:
            return url.replace("\\u002F", "/")

    raise Exception("URL MP4 não encontrada no HTML")


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

        # Resolve encurtado
        final_url = resolve_short_url(url)

        # Valida tipo
        video_id = extract_video_id(final_url)

        # Extrai MP4 real
        video_url = fetch_video_url(video_id)

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
                "Content-Disposition": "attachment; filename=video.mp4",
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