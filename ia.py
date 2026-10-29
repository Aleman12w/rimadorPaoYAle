import os, json, httpx

MODELO = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
URL = f"https://generativelanguage.googleapis.com/v1beta/models/{MODELO}:generateContent"

def ia(instruccion, texto, como_json=False):
    """Manda instruccion + texto a Gemini. Devuelve texto, o un dict/lista si como_json=True."""
    clave = os.getenv("GEMINI_API_KEY", "").strip()
    if not clave:
        raise RuntimeError("Falta GEMINI_API_KEY: defínela en tu terminal o en el secret del Space.")
    cfg = {"responseMimeType": "application/json"} if como_json else {}
    r = httpx.post(URL, timeout=30, headers={"x-goog-api-key": clave},
        json={"contents": [{"parts": [{"text": instruccion + "\n\nTexto: " + texto}]}],
              "generationConfig": cfg})
    if r.is_error:
        try:
            respuesta = r.json()
        except ValueError:
            respuesta = None
        error = respuesta.get("error") if isinstance(respuesta, dict) else None
        detalle = error.get("message") if isinstance(error, dict) else None
        if not isinstance(detalle, str) or not detalle:
            detalle = "Google no incluyó detalles en la respuesta."
        raise RuntimeError(f"Gemini respondió con HTTP {r.status_code}: {detalle}")
    t = r.json()["candidates"][0]["content"]["parts"][0]["text"]
    if como_json:
        t = t.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()
        return json.loads(t)
    return t