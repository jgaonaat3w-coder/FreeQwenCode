"""Prueba de lectura: crea un PDF con texto conocido y compara cuántas líneas leen exactas
PDFKit, qwen3.8:27b y gemma4:26b. Se niega a arrancar si hay modelos cargados en Ollama,
salvo con FORZAR=1. Uso: python3 herramientas/mediciones/lectura.py
"""
import base64, difflib, json, os, shutil, subprocess, sys, tempfile, urllib.request
URL = os.environ.get("OLLAMA_URL", "http://localhost:11434")
MODELOS = ["qwen3.8:27b", "gemma4:26b"]
LINEAS = [
    "Informe de prueba de lectura",
    "Fecha: 6 de octubre de 2026",
    "Importe total: 1.234,56 EUR (IVA incluido)",
    "Referencia: FQ-2026-0042",
    "El análisis se realizó con año, señal y cigüeña.",
    "Tabla: modelo | prefill | generación",
    "qwen3.8 | 183 | 12,6",
    "gemma4 | 558 | 46,3",
]
def post(path, body):
    req = urllib.request.Request(URL + path, json.dumps(body).encode(), {"Content-Type": "application/json"})
    with urllib.request.urlopen(req) as r:
        return json.load(r)
def get(path):
    with urllib.request.urlopen(URL + path) as r:
        return json.load(r)
def crear_pdf(lineas, ruta):
    ops = ["BT", "/F1 14 Tf", "20 TL", "56 780 Td"]
    for l in lineas:
        ops.append("(" + l.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)") + ") Tj T*")
    ops.append("ET")
    flujo = "\n".join(ops).encode("cp1252")
    objs = [b"<< /Type /Catalog /Pages 2 0 R >>",
            b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
            b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] /Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>",
            b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica /Encoding /WinAnsiEncoding >>",
            b"<< /Length %d >>\nstream\n" % len(flujo) + flujo + b"\nendstream"]
    out = bytearray(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")
    pos = []
    for i, o in enumerate(objs, 1):
        pos.append(len(out))
        out += b"%d 0 obj\n" % i + o + b"\nendobj\n"
    xref = len(out)
    out += b"xref\n0 %d\n0000000000 65535 f \n" % (len(objs) + 1)
    for p in pos:
        out += b"%010d 00000 n \n" % p
    out += b"trailer\n<< /Size %d /Root 1 0 R >>\nstartxref\n%d\n%%%%EOF\n" % (len(objs) + 1, xref)
    open(ruta, "wb").write(out)
def pdf_a_png(pdf, carpeta):
    if shutil.which("qlmanage"):
        subprocess.run(["qlmanage", "-t", "-s", "1600", "-o", carpeta, pdf], capture_output=True)
        png = os.path.join(carpeta, os.path.basename(pdf) + ".png")
        if os.path.exists(png):
            return png
    png = os.path.join(carpeta, "pagina.png")
    subprocess.run(["sips", "-s", "format", "png", pdf, "--out", png], capture_output=True)
    return png if os.path.exists(png) else None
def texto_pdf(pdf):
    if not shutil.which("osascript"):
        return None
    js = ("ObjC.import('PDFKit'); var d = $.PDFDocument.alloc.initWithURL($.NSURL.fileURLWithPath("
          + json.dumps(pdf) + ")); d.string.js")
    r = subprocess.run(["osascript", "-l", "JavaScript", "-e", js], capture_output=True, text=True)
    return r.stdout if r.returncode == 0 and r.stdout.strip() else None
def comparar(texto):
    leidas = [l.strip() for l in texto.strip().splitlines() if l.strip()]
    ratio = difflib.SequenceMatcher(None, "\n".join(LINEAS), "\n".join(leidas)).ratio()
    fallos = [l for l in LINEAS if l not in leidas]
    return ratio, fallos
def main():
    print("== Capacidades declaradas por Ollama")
    caps = {}
    for m in MODELOS:
        try:
            caps[m] = post("/api/show", {"model": m}).get("capabilities", [])
        except Exception as e:
            caps[m] = []
            print(f"{m}: no disponible ({e})")
            continue
        print(f"{m}: {', '.join(caps[m])}")
    cargados = [x["name"] for x in get("/api/ps").get("models", [])]
    if cargados and os.environ.get("FORZAR") != "1":
        sys.exit("\nHay modelos cargados: " + ", ".join(cargados) + ". La prueba de lectura los descargaría "
                 "y te haría perder su caché. Repite cuando no estés usando Ollama, o con FORZAR=1.")
    carpeta = tempfile.mkdtemp(prefix="lectura-")
    pdf = os.path.join(carpeta, "prueba.pdf")
    crear_pdf(LINEAS, pdf)
    png = pdf_a_png(pdf, carpeta)
    if not png:
        sys.exit("No se pudo convertir el PDF en imagen con qlmanage ni con sips.")
    print(f"\n== PDF de prueba: {pdf}\n== Página como imagen: {png}")
    capa = texto_pdf(pdf)
    if capa is None:
        print("\n-- Capa de texto con PDFKit: no disponible")
    else:
        ratio, fallos = comparar(capa)
        print(f"\n-- Capa de texto con PDFKit, sin modelo: parecido {ratio:.1%}, "
              f"{len(LINEAS) - len(fallos)} de {len(LINEAS)} líneas exactas")
    img = base64.b64encode(open(png, "rb").read()).decode()
    for m in MODELOS:
        if "vision" not in caps.get(m, []):
            print(f"\n-- {m}: sin capacidad de visión, no se prueba")
            continue
        body = {"model": m, "stream": False, "keep_alive": "2m", "images": [img],
                "prompt": "Transcribe exactamente todo el texto de la imagen, línea a línea, sin añadir ni corregir nada.",
                "options": {"num_ctx": 8192, "temperature": 0, "seed": 42, "num_predict": 512}}
        if "thinking" in caps[m]:
            body["think"] = False
        r = post("/api/generate", body)
        post("/api/generate", {"model": m, "keep_alive": 0})
        ratio, fallos = comparar(r.get("response", ""))
        print(f"\n-- {m}: parecido {ratio:.1%}, {len(LINEAS) - len(fallos)} de {len(LINEAS)} líneas exactas, "
              f"{r.get('total_duration', 0) / 1e9:.1f} s")
        print(r.get("response", "").strip())
        for f in fallos:
            print(f"   no aparece exacta: {f}")
main()
