"""Prueba de velocidad: carga, prefill y generación de qwen3.8:27b con dos ventanas, y prefill
con un prompt de unos 80k tokens en qwen3.8:27b, qwen3-coder:30b y gemma4:26b. Temperatura 0
y semilla fija. Se niega a arrancar si hay modelos cargados en Ollama, salvo con FORZAR=1.
Uso: python3 herramientas/mediciones/velocidad.py
"""
import json, os, random, time, urllib.request
URL = os.environ.get("OLLAMA_URL", "http://localhost:11434")
def post(path, body):
    req = urllib.request.Request(URL + path, json.dumps(body).encode(), {"Content-Type": "application/json"})
    with urllib.request.urlopen(req) as r:
        return json.load(r)
def get(path):
    with urllib.request.urlopen(URL + path) as r:
        return json.load(r)
cargados = [m["name"] for m in get("/api/ps").get("models", [])]
if cargados and os.environ.get("FORZAR") != "1":
    raise SystemExit("Hay modelos cargados en Ollama: " + ", ".join(cargados) +
                     ". Esta prueba los descargaría y te haría perder su caché. "
                     "Ejecútala cuando no estés usando Ollama, o con FORZAR=1.")
random.seed(42)
palabras = ("el la de que y en un ser se no haber por con su para como estar tener lo todo pero más hacer "
            "poder decir este ir otro ese si ya ver porque dar cuando muy sin vez mucho saber sobre mismo "
            "también hasta año dos querer entre así primero desde grande llegar pasar tiempo día bien poco "
            "deber poner cosa parecer donde ahora parte después vida quedar siempre creer hablar llevar dejar "
            "nada cada seguir menos nuevo encontrar función clase objeto variable módulo prueba error lista "
            "índice cadena número valor fichero ruta servidor cliente memoria caché contexto modelo").split()
def texto(n):
    return " ".join(random.choice(palabras) for _ in range(n))
corto, largo = texto(24000), texto(78000)
caps = {}
def medir(etiqueta, modelo, ctx, txt, mmap=None):
    if modelo not in caps:
        caps[modelo] = post("/api/show", {"model": modelo}).get("capabilities", [])
    opts = {"num_ctx": ctx, "num_predict": 256, "temperature": 0, "seed": 42}
    if mmap is not None:
        opts["use_mmap"] = mmap
    body = {"model": modelo, "prompt": f"[{time.time_ns()}] Resume en una frase:\n{txt}",
            "stream": False, "keep_alive": "5m", "options": opts}
    if "thinking" in caps[modelo]:
        body["think"] = False
    r = post("/api/generate", body)
    post("/api/generate", {"model": modelo, "keep_alive": 0})
    pre = r["prompt_eval_count"] / max(r["prompt_eval_duration"], 1) * 1e9
    gen = r["eval_count"] / max(r["eval_duration"], 1) * 1e9
    print(f"{etiqueta:26} {r.get('load_duration', 0) / 1e9:>8.1f} {r['prompt_eval_count']:>7} {pre:>11.0f} {gen:>8.1f}", flush=True)
print(f"{'caso':26} {'carga s':>8} {'prompt':>7} {'prefill t/s':>11} {'gen t/s':>8}", flush=True)
print("-- A: qwen3.8, ventana y mmap, dos repeticiones")
for n in (1, 2):
    medir(f"qwen3.8 131k mmap #{n}", "qwen3.8:27b", 131072, corto)
    medir(f"qwen3.8 131k sin mmap #{n}", "qwen3.8:27b", 131072, corto, mmap=False)
    medir(f"qwen3.8 262k #{n}", "qwen3.8:27b", 262144, corto)
print("-- B: prompt largo de unos 80k tokens")
for m in ("qwen3.8:27b", "qwen3-coder:30b", "gemma4:26b"):
    medir(f"{m} largo", m, 131072, largo)
