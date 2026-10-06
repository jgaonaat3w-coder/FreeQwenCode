# FreeQwenCode: concepto

**Estado:** exploración conceptual. Este documento recoge el razonamiento y las mediciones hasta ahora. No es un plan de implementación.

## Qué buscamos

Un entorno de programación agéntica lo más parecido posible a Claude Code, con tres condiciones:

- Modelos locales, en concreto los Qwen y Gemma instalados en la máquina de referencia.
- Interfaz gráfica, no de terminal.
- Contexto largo utilizable de verdad, no solo nominal.

"Lo más parecido posible" se refiere a la forma: el bucle agéntico, las herramientas para leer, editar, buscar y ejecutar, los permisos, la memoria de proyecto, los subagentes y la compactación del contexto. La calidad del modelo es otra cuestión. Con un 27B local, lo razonable es esperar un agente de una o dos generaciones atrás.

## Máquina y modelos de referencia

| | |
|---|---|
| Equipo | MacBook Pro con Apple M5 Max, GPU de 40 núcleos y 64 GB de memoria unificada |
| Memoria disponible para la GPU | 56 GB, fijados por un servicio de arranque |
| Servidor | Ollama 0.35.1, que por dentro lanza `llama-server` de llama.cpp |
| Modelo principal | `qwen3.8:27b`, cuantizado en Q4_K_M, unos 17 GB |
| Alternativas a medir | `qwen3-coder:30b` y `gemma4:26b`, ambos MoE con unos 3 a 4B parámetros activos |
| Auxiliares | `qwen3:4b` para tareas pequeñas, `qwen2.5-coder:1.5b-base` para autocompletado FIM y modelos de embeddings |

### `qwen3.8:27b` en cifras

| Dato | Valor | Origen |
|---|---|---|
| Arquitectura | Híbrida: 64 capas, 16 de atención completa y 48 Gated DeltaNet, más 1 capa MTP | Metadatos GGUF |
| Contexto nativo | 262.144 tokens | Metadatos GGUF |
| Caché KV | 64 KiB por token en f16, solo en las 16 capas de atención | Log de llama-server |
| Caché KV a 262.144 | 16 GiB, más 1 GiB de la capa MTP | Log de llama-server |
| Memoria total a 262.144 | Unos 35 GB | Estimación |
| Prefill | Unos 294 tokens/s | Medido en septiembre de 2026 sobre 64.800 tokens |
| Generación | 28 tokens/s sin flash attention, 21,5 con ella | Medido en septiembre de 2026 con una versión anterior de Ollama |
| Lote de prefill | 2048 con ventana de 49.152, 512 con ventana de 262.144 | Log de llama-server, elegido por Ollama |
| Puntos de control de caché | Activos: hasta 32, separados al menos 8192 tokens | Log de llama-server |

## Lo que enseñó el diagnóstico de Roo Code con Ollama

El punto de partida fue una queja concreta: con `qwen3.8:27b` en Roo Code, el contexto "se quedaba cortísimo". El diagnóstico dejó estas lecciones, que valen para cualquier harness local.

### 1. La memoria no es el límite. El prefill sí.

El modelo cabe con su ventana completa y sobra sitio. Lo que limita es el tiempo de reprocesar la conversación cuando se pierde la caché. Además, la generación se frena con la conversación llena, porque cada token generado lee la caché de las 16 capas de atención además de los pesos.

| Conversación | Reprocesar en frío a 294 tok/s | Generación frente a conversación vacía, estimada |
|---|---|---|
| 50k tokens | Unos 3 min | Un 15 % más lenta |
| 100k tokens | Unos 6 min | Un 30 % más lenta |
| 200k tokens | Unos 11 min | Un 45 % más lenta |

### 2. Perder la caché es el evento más caro del sistema.

La caché se pierde, o puede perderse, en estos casos:

- **Cambia la ventana entre peticiones.** Ollama recarga el modelo cada vez que cambia `num_ctx`. Un router con ventana adaptativa lo provocaba constantemente al alternar con Roo Code.
- **El modelo se descarga.** Ocurre por inactividad o porque otro modelo lo desaloja.
- **Entra una petición con otro prefijo.** Con un único hueco de inferencia, una tarea auxiliar puede pisar la caché de la conversación principal.
- **Se condensa con un prompt distinto.** Es el caso siguiente.

### 3. Roo Code condensa en frío.

Su petición de resumen usa un system prompt propio. Por eso no reutiliza la caché y procesa la conversación entera. Con 100k tokens, eso son unos 6 minutos antes de empezar a resumir.

### 4. El cliente HTTP no puede tener límite de tiempo hasta el primer byte.

Ollama no envía ni las cabeceras de respuesta hasta terminar el prefill. El fetch de Node, undici, aborta a los 300 segundos sin cabeceras, y la extensión solo muestra "fetch failed". A 294 tok/s, eso pone un techo de unos 85k tokens a cualquier petición en frío. En VS Code se esquiva con `"http.electronFetch": true`. Cline tiene registrado el mismo fallo.

### 5. Roo Code ya no se mantiene.

Su repositorio se archivó el 15 de mayo de 2026. El propio proyecto remite a ZooCode, un fork de la comunidad, y a Cline, del que nació.

## Principios de diseño

1. **La caché es sagrada.** Todo el diseño se subordina a no perderla.
2. **Prefijo estable, cambios solo al final.** El system prompt y las definiciones de herramientas van fijos al principio. Nada variable, como la hora o la lista de ficheros abiertos, va antes del historial. El historial solo crece por el final.
3. **Compactar sin romper la caché.** La petición de resumen se envía como un mensaje más al final de la conversación, con el mismo system prompt y las mismas herramientas. El servidor reutiliza la caché y solo procesa la instrucción, así que el prefill pasa de minutos a segundos. Queda el tiempo de generar el resumen, que conviene pedir sin razonamiento. El hilo nuevo, formado por el system prompt y el resumen, es corto y barato aunque vaya en frío.
4. **Las tareas auxiliares no tocan el modelo principal.** Títulos, mensajes de commit, clasificaciones y resúmenes de salidas de herramientas van a un modelo pequeño en otro proceso. Es el patrón de Claude Code con su modelo pequeño, y aquí además protege la caché del principal.
5. **Una ventana fija por modelo, decidida al arrancar.** Nunca se negocia por petición.
6. **El modelo principal es residente.** Se carga una vez y no se descarga por inactividad. Si no está cargado, la interfaz avisa antes de enviar una conversación larga.
7. **Sin límites de tiempo hasta el primer token, y con progreso visible.** Antes de enviar, la interfaz estima el prefill a partir de los tokens que no están en caché y de la velocidad medida, y lo muestra.
8. **El presupuesto de contexto se mide en tiempo, no en porcentaje.** Se compacta cuando el coste de reprocesar en frío o el frenazo de la generación superan un umbral, no al llegar a un porcentaje fijo de la ventana.
9. **Retomar sin reprocesar.** Al pausar una tarea larga, el estado del hueco de inferencia se guarda en disco y se restaura al retomarla. `llama-server` lo permite. Ollama no lo expone.

## Capa de inferencia

Ollama ya usa `llama-server` por dentro. La cuestión es si el harness habla con Ollama o directamente con `llama-server`.

| | Ollama | `llama-server` directo |
|---|---|---|
| Gestión de modelos | Muy cómoda | Manual, aunque puede usar los mismos ficheros GGUF que Ollama ya descargó |
| Ventana | Por petición, y cambiarla recarga el modelo | Fija al arrancar |
| Lote de prefill | Lo elige Ollama: 512 con ventana de 262.144 | Configurable |
| Puntos de control de caché | Valores por defecto | Configurables |
| Guardar y restaurar la caché en disco | No | Sí |
| Plantilla de chat y parser de herramientas | Los aplica Ollama | Hay que verificarlos |

**Hipótesis de trabajo:** `llama-server` directo para el modelo principal y Ollama para todo lo demás. Se puede probar con el binario que trae Ollama, que ya soporta la arquitectura `qwen35` y el MTP.

## Harness e interfaz

Ninguna opción cumple hoy todos los principios. Lo que hay que averiguar de cada una es cuánto cuesta adaptarla.

- **OpenCode.** TypeScript sobre Bun, licencia MIT, arquitectura cliente-servidor y app de escritorio real. Es la base más parecida a Claude Code con interfaz gráfica. Falta comprobar cómo compacta y qué límites de tiempo tiene su cliente HTTP.
- **Cline o ZooCode en VS Code.** Mantienen el flujo de trabajo actual dentro de VS Code. Heredan el diseño de Roo Code, y cambiar su compactación supone mantener un fork.
- **Qwen Code con un editor vía ACP.** Está optimizado para el formato de herramientas de Qwen. La interfaz gráfica la pone el editor, por ejemplo Zed.
- **Claude Code contra la API compatible con Anthropic de Ollama.** Da la forma exacta, pero solo en terminal, y conviene revisar sus términos de uso.
- **Harness propio.** Da control total sobre los principios a cambio de construirlo todo.

## Decisiones abiertas

1. **Base del harness:** adaptar OpenCode, usar una extensión de VS Code o escribir un harness propio.
2. **Capa de inferencia del modelo principal:** Ollama o `llama-server` directo.
3. **Interfaz:** VS Code, app de escritorio o editor vía ACP.
4. **Modelo principal:** `qwen3.8:27b`, denso, de más calidad y con prefill lento, frente a los MoE, previsiblemente mucho más rápidos en prefill.

## Mediciones pendientes

- Prefill y generación de `qwen3.8:27b` con Ollama 0.35.1 a 131.072 y a 262.144, para saber cuánto cuesta el lote de 512.
- Lo mismo con `qwen3-coder:30b` y `gemma4:26b`.
- Generación con y sin flash attention en la versión actual.
- Reutilización real de la caché entre turnos, comparando en el log los tokens del prompt con los tokens evaluados.
- Guardar y restaurar la caché en disco con un modelo híbrido en `llama-server`.
- Compactación al final de la conversación, para confirmar que solo procesa la instrucción.
