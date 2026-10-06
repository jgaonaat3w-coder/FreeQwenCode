# FreeQwenCode: concepto

**Estado:** exploración conceptual. Este documento recoge el razonamiento y las mediciones hasta ahora. No es un plan de implementación.

## Qué buscamos

Un entorno de programación agéntica lo más parecido posible a Claude Code, con cuatro condiciones:

- Modelos locales, en concreto los Qwen y Gemma instalados en la máquina de referencia.
- Interfaz gráfica, no de terminal.
- Contexto largo utilizable de verdad, no solo nominal.
- **Detección automática de lo que hace falta en cada momento.** No hay un único uso, así que el entorno debe reconocer el tipo de trabajo y adaptarse sin que haya que configurarlo cada vez.

"Lo más parecido posible" se refiere a la forma: el bucle agéntico, las herramientas para leer, editar, buscar y ejecutar, los permisos, la memoria de proyecto, los subagentes y la compactación del contexto. La calidad del modelo es otra cuestión. Con un 27B local, lo razonable es esperar un agente de una o dos generaciones atrás.

### Usos previstos

- **Programar con el usuario delante.** Cambios acotados, preguntas sobre el código y depuración, donde manda la latencia de cada turno.
- **Misiones largas casi desatendidas.** Retomar lo pendiente, recorrer una cola de tareas o de deuda técnica y cerrar cada punto con lint, compilación y tests.
- **Investigación sobre un corpus de texto.** Buscar, citar y verificar sobre el texto, con reglas epistémicas estrictas: decir «no lo sé» es preferible a inventar.
- **Depender menos de servicios de pago.** Asumir en local las tareas que hoy se resuelven con Claude Code.

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
| Prefill | Entre 292 y 344 tokens/s | Medido en octubre de 2026 sobre 24.500 tokens. En septiembre, 294 sobre 64.800 |
| Generación | Entre 15 y 21 tokens/s, con flash attention y sin razonamiento | Medido en octubre de 2026. En septiembre, 28 sin flash attention y 21,5 con ella |
| Carga | 5,5 s con ventana de 131.072, 47 s con 262.144 | Medido en octubre de 2026. Con 262.144, Ollama desactiva mmap |
| Lote de prefill | 2048 con ventana de 49.152, 512 con ventana de 262.144 | Log de llama-server, elegido por Ollama |
| Puntos de control de caché | Activos: hasta 32, separados al menos 8192 tokens | Log de llama-server |

### Comparativa de velocidad

Medida el 6 de octubre de 2026 con Ollama 0.35.1, un prompt de unos 24.500 tokens sin caché, 256 tokens generados y sin razonamiento. Es una sola pasada por configuración, con la temperatura por defecto de cada modelo. Además, pudo coincidir con otro uso de `qwen3.8:27b` en la misma máquina, así que las cifras pueden estar contaminadas por recargas o por competir por la GPU.

| Modelo | Ventana | Carga | Prefill | Generación |
|---|---|---|---|---|
| `qwen3.8:27b` | 131.072 | 5,5 s | 292 t/s | 15,2 t/s |
| `qwen3.8:27b` | 262.144 | 46,9 s | 344 t/s | 21,3 t/s |
| `qwen3-coder:30b` | 131.072 | 9,1 s | 487 t/s | 39,8 t/s |
| `gemma4:26b` | 131.072 | 7,4 s | 766 t/s | 22,8 t/s |

Lo que se deduce, con la cautela de una sola pasada:

- **Los MoE son más rápidos, pero no varias veces en todo.** `gemma4:26b` procesa prompts entre 2,2 y 2,6 veces más rápido que `qwen3.8:27b`. `qwen3-coder:30b` genera unas 2 veces más rápido, y en prefill solo le saca entre 1,4 y 1,7 veces.
- **Cada MoE destaca en una cosa.** `gemma4:26b` en leer, probablemente porque la mayoría de sus capas usan atención de ventana deslizante. `qwen3-coder:30b` en escribir.
- **El resultado de `qwen3.8:27b` a 262.144 contradice lo esperado.** Con un lote de prefill menor fue más rápido en las dos fases. Puede deberse al orden, a la lectura del modelo desde disco en la primera pasada, a la variabilidad de la generación especulativa con temperatura 1 o a la otra carga de trabajo. Hay que repetirlo.
- **Un turno típico de agente**, con 5.000 tokens nuevos y 500 generados, tarda entre 38 y 50 s con `qwen3.8:27b`, unos 23 s con `qwen3-coder:30b` y unos 28 s con `gemma4:26b`. Sin contar razonamiento.

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
10. **Enrutar por tarea, no por mensaje.** El modelo solo cambia al empezar una tarea, al lanzar un subagente o después de compactar. Cambiarlo a mitad de conversación cuesta minutos de prefill. ArchonHub, el router anterior, lo sufría porque elegía modelo y ventana en cada petición.
11. **Ningún modelo se carga ni se descarga en el camino crítico.** Los modelos que se usan a diario están residentes con su ventana fija. Cargar otro es una decisión deliberada en un límite de tarea.
12. **El razonamiento se dosifica por modo.** Cada token de razonamiento cuesta lo mismo que uno de respuesta. En conversación conviene bajo o apagado. En misión e investigación, medio o alto.

## Detección automática del modo

### Modos

El entorno no es un único agente con un único comportamiento. Es un conjunto de modos, y cada uno cambia las herramientas, la autonomía, la supervisión y la vista de la interfaz, no solo el modelo.

| Modo | Cuándo | Qué cambia |
|---|---|---|
| Conversación | El usuario está delante y pide cambios acotados o hace preguntas | Modelo principal, respuestas breves, permiso antes de lo destructivo |
| Misión | «Sigue con lo pendiente», una cola de tareas, trabajo de horas | Plan explícito, puntos de control, revisión por un supervisor en cada hito, aviso al terminar o al atascarse |
| Investigación | Proyecto de corpus, preguntas sobre el texto | Herramientas de búsqueda y cita, cada afirmación con su fuente, incertidumbre explícita |
| Consulta rápida | Preguntas cortas sin relación con la tarea en curso | Modelo rápido, sin tocar la conversación principal |

### Cómo se detecta

1. **Señales deterministas y baratas primero.** El proyecto abierto y su fichero de memoria, que puede declarar el modo por defecto. La existencia de una cola de tareas o de deuda. Los adjuntos, como imágenes.
2. **Un clasificador pequeño para lo ambiguo.** `qwen3:4b` en su propio proceso decide en un segundo, sin tocar la caché del modelo principal.
3. **El agente principal puede proponer un cambio de modo** a mitad de tarea, por ejemplo al descubrir que una pregunta se ha convertido en una misión.
4. **La elección es visible y reversible.** La interfaz muestra qué modo ha elegido y por qué, y se cambia con un clic. Un error de clasificación silencioso es peor que una pregunta.

### Subagentes como mecanismo de enrutado

La forma de usar otro modelo sin romper la caché es delegar una subtarea completa. El subagente trabaja con otro modelo y su propio contexto, y devuelve un resultado corto que se añade al final de la conversación principal. Explorar el código, buscar en el corpus o ejecutar los tests y resumir el resultado son buenos candidatos.

### Memoria: tres huecos

| Hueco | Modelo | Ventana | Pesos | Caché KV en f16 | Caché KV en q8_0 |
|---|---|---|---|---|---|
| Fijo, nunca se desaloja | `qwen3.8:27b`, principal | 131.072 | 17 GB | 8,5 GB | 4,3 GB |
| Intercambiable | `gemma4:26b` para subtareas de lectura y supervisión, o `qwen3-coder:30b` para subtareas de escritura | 65.536 | 18 GB | 6 GB | 3 GB |
| Pequeño, fijo | `qwen3:4b`, clasificador y tareas auxiliares | 16.384 | 2,5 GB | 2,3 GB | 1,2 GB |

Son estimaciones, y las del hueco intercambiable corresponden a `qwen3-coder:30b`. Que el supervisor sea de otra familia que el principal ayuda a que no compartan los mismos errores. En f16 suman unos 54 GB más los buffers de cálculo, que no caben en los 56 GB disponibles. Con la caché en q8_0 bajan a unos 46 GB, más buffers. El hueco intercambiable se recarga solo en límites de tarea, y perder su caché es barato porque cada subtarea empieza con contexto propio.

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
3. **Interfaz:** VS Code, app de escritorio o editor vía ACP. Tiene que poder cambiar de vista según el modo.
4. **Modelo principal:** `qwen3.8:27b`, denso, de más calidad y el más lento en todo, frente a los MoE. Las mediciones inclinan a mantenerlo como principal y usar los MoE en subagentes, porque la ventaja de velocidad es real pero no de varias veces.
5. **Quién elige el modo:** reglas más clasificador al empezar cada tarea, o solo el modelo principal, como hace Claude Code con sus subagentes. La propuesta es combinar las dos cosas: reglas y clasificador para el modo de la tarea, y el agente principal para lanzar subagentes dentro de ella.
6. **Relación con ArchonHub:** reutilizar su catálogo de mediciones y sus perfiles de tarea, o empezar de cero.

## Mediciones pendientes

- Repetir `qwen3.8:27b` a 131.072 y a 262.144 con temperatura 0, semilla fija y la máquina sin otro uso, y probar 131.072 sin mmap. La primera pasada dio 262.144 como más rápido, al revés de lo esperado.
- Caída del prefill con prompts de unos 80k tokens en los tres modelos.
- Generación con y sin flash attention en la versión actual.
- Reutilización real de la caché entre turnos, comparando en el log los tokens del prompt con los tokens evaluados.
- Guardar y restaurar la caché en disco con un modelo híbrido en `llama-server`.
- Compactación al final de la conversación, para confirmar que solo procesa la instrucción.
- Precisión del clasificador de modo sobre peticiones reales. Las tareas guardadas de Roo Code sirven como conjunto de prueba si se etiqueta a mano un centenar.
- Convivencia de memoria: comprobar que Ollama tiene en cuenta la memoria que ocupa un `llama-server` externo y no sobrecarga la GPU.
