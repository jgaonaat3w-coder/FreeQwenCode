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
| Prefill | Unos 320 tokens/s sostenidos con 24.500 tokens, 183 con 80.000 | Medido en octubre de 2026. En septiembre, 294 sobre 64.800 con otra versión |
| Generación | Unos 16,5 tokens/s sostenidos con 24.500 tokens de contexto, 12,6 con 80.000 | Medido en octubre de 2026, con flash attention y sin razonamiento |
| Carga | Unos 4 s con ventana de 131.072 o de 262.144 | Medido en octubre de 2026 con el fichero en la caché del sistema |
| Lote de prefill | 2048 con ventana de 49.152, 512 con ventana de 262.144 | Log de llama-server, elegido por Ollama |
| Puntos de control de caché | Activos: hasta 32, separados al menos 8192 tokens | Log de llama-server |

### Comparativa de velocidad

Medida el 6 de octubre de 2026 con Ollama 0.35.1, prompts sin caché, 256 tokens generados, sin razonamiento, temperatura 0 y semilla fija. Las cifras de `qwen3.8:27b` con 24.500 tokens son la media de cinco pasadas sostenidas. Las de los MoE con 24.500 tokens vienen de una primera prueba que coincidió con otro uso de la máquina y pueden estar contaminadas.

| Modelo | Prefill con 25k | Prefill con 80k | Generación con 25k | Generación con 80k |
|---|---|---|---|---|
| `qwen3.8:27b` | 324 t/s | 183 t/s | 16,5 t/s | 12,6 t/s |
| `qwen3-coder:30b` | 487 t/s, dudosa | 166 t/s | 39,8 t/s, dudosa | 17,8 t/s |
| `gemma4:26b` | 766 t/s, dudosa | 558 t/s | 22,8 t/s, dudosa | 46,3 t/s |

Lo que se deduce:

- **La ventana de 262.144 no cuesta velocidad.** Con 131.072 y con 262.144, `qwen3.8:27b` da lo mismo dentro del ruido, y carga en unos 4 s en ambos casos. La anomalía de la primera prueba y su carga de 47 s eran contaminación. Lo único que cuesta la ventana grande es memoria.
- **Hay un pico inicial y luego un régimen sostenido.** La primera pasada con la máquina en reposo dio 467 t/s de prefill y 22 t/s de generación, entre un 33 y un 44 % más que las siguientes. La hipótesis es la temperatura o el modo de energía. Una misión larga trabaja en régimen sostenido, así que hay que planificar con esas cifras.
- **Con contexto largo, el orden cambia.** `qwen3-coder:30b` se hunde: con 80k procesa prompts más despacio que `qwen3.8:27b`, porque todas sus capas usan atención completa. `gemma4:26b` aguanta: con 80k procesa prompts 3 veces más rápido y genera 3,7 veces más rápido que `qwen3.8:27b`.
- **La generación sigue el modelo de tráfico de memoria.** Cada token generado lee los pesos activos y toda la caché KV. Con esa cuenta, la predicción para `qwen3-coder:30b` con 84k era 17,6 t/s y la medida fue 17,8. Para `qwen3.8:27b` con 80k, 13,7 frente a 12,6.
- **El prefill de `qwen3.8:27b` crece más rápido que la conversación.** Ajustando las dos mediciones, procesar 5.000 tokens nuevos cuesta unos 21 s con 25k de contexto, 45 s con 80k y 67 s con 131k. Es una estimación de dos puntos, pero la tendencia es clara: la zona de trabajo cómoda acaba hacia los 60 a 80k tokens.

## Lo que enseñó el diagnóstico de Roo Code con Ollama

El punto de partida fue una queja concreta: con `qwen3.8:27b` en Roo Code, el contexto "se quedaba cortísimo". El diagnóstico dejó estas lecciones, que valen para cualquier harness local.

### 1. La memoria no es el límite. El prefill sí.

El modelo cabe con su ventana completa y sobra sitio. Lo que limita es el tiempo de reprocesar la conversación cuando se pierde la caché. Además, la generación se frena con la conversación llena, porque cada token generado lee la caché de las 16 capas de atención además de los pesos. Cifras de `qwen3.8:27b` en régimen sostenido:

| Conversación | Reprocesar en frío | Generación |
|---|---|---|
| 25k tokens | 1,3 min, medido | 16,5 t/s, medido |
| 80k tokens | 7,3 min, medido | 12,6 t/s, medido |
| 100k tokens | Unos 11 min, estimado | Unos 13 t/s, estimado |
| 200k tokens | Más de 30 min, estimado | Unos 10 t/s, estimado |

### 2. Perder la caché es el evento más caro del sistema.

La caché se pierde, o puede perderse, en estos casos:

- **Cambia la ventana entre peticiones.** Ollama recarga el modelo cada vez que cambia `num_ctx`. Un router con ventana adaptativa lo provocaba constantemente al alternar con Roo Code.
- **El modelo se descarga.** Ocurre por inactividad o porque otro modelo lo desaloja.
- **Entra una petición con otro prefijo.** Con un único hueco de inferencia, una tarea auxiliar puede pisar la caché de la conversación principal.
- **Se condensa con un prompt distinto.** Es el caso siguiente.

### 3. Roo Code condensa en frío.

Su petición de resumen usa un system prompt propio. Por eso no reutiliza la caché y procesa la conversación entera. Con 100k tokens, eso son unos 6 minutos antes de empezar a resumir.

### 4. El cliente HTTP no puede tener límite de tiempo hasta el primer byte.

Ollama no envía ni las cabeceras de respuesta hasta terminar el prefill. El fetch de Node, undici, aborta a los 300 segundos sin cabeceras, y la extensión solo muestra "fetch failed". Con las velocidades sostenidas medidas, eso pone un techo de unos 60k tokens a cualquier petición en frío con `qwen3.8:27b`. En VS Code se esquiva con `"http.electronFetch": true`. Cline tiene registrado el mismo fallo.

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
| Investigación | Proyecto de corpus, preguntas sobre el texto | `qwen3.8:27b` al mando con herramientas de búsqueda y cálculo, `gemma4:26b` solo como herramienta en algunas peticiones, cada afirmación con su fuente, incertidumbre explícita |
| Consulta rápida | Preguntas cortas sin relación con la tarea en curso | Modelo rápido, sin tocar la conversación principal |

### Cómo se detecta

1. **Señales deterministas y baratas primero.** El proyecto abierto y su fichero de memoria, que puede declarar el modo por defecto. La existencia de una cola de tareas o de deuda. Los adjuntos, como imágenes.
2. **Un clasificador pequeño para lo ambiguo.** `qwen3:4b` en su propio proceso decide en un segundo, sin tocar la caché del modelo principal.
3. **El agente principal puede proponer un cambio de modo** a mitad de tarea, por ejemplo al descubrir que una pregunta se ha convertido en una misión.
4. **La elección es visible y reversible.** La interfaz muestra qué modo ha elegido y por qué, y se cambia con un clic. Un error de clasificación silencioso es peor que una pregunta.

### Subagentes como mecanismo de enrutado

La forma de usar otro modelo sin romper la caché es delegar una subtarea completa. El subagente trabaja con otro modelo y su propio contexto, y devuelve un resultado corto que se añade al final de la conversación principal. Explorar el código, buscar en el corpus, calcular sobre él o ejecutar los tests y resumir el resultado son buenos candidatos.

### Memoria en modo programación: tres huecos

| Hueco | Modelo | Ventana | Pesos | Caché KV en f16 | Caché KV en q8_0 |
|---|---|---|---|---|---|
| Fijo, nunca se desaloja | `qwen3.8:27b`, principal | 131.072 | 17 GB | 8,5 GB | 4,3 GB |
| Intercambiable | `gemma4:26b` para leer documentación y texto largo, o `qwen3-coder:30b` para subtareas cortas de código | 65.536 | 17 a 18 GB | Por medir | Por medir |
| Pequeño, fijo | `qwen3:4b`, clasificador y tareas auxiliares | 16.384 | 2,5 GB | 2,3 GB | 1,2 GB |

Son estimaciones. En programación, `gemma4:26b` solo lee texto en lenguaje natural, nunca escribe ni revisa código. `qwen3-coder:30b` compensa en subtareas cortas de código, donde su contexto corto evita el hundimiento que sufre con contexto largo. Sin el hueco intercambiable, los otros dos ocupan unos 30 GB en f16, así que el total depende de qué modelo lo ocupe y de su caché. El hueco intercambiable se recarga solo en límites de tarea, y perder su caché es barato porque cada subtarea empieza con contexto propio.

## Combinación de modelos por fortalezas

Cada modelo se usa donde es fuerte y nunca donde no se confía en él. La matriz mezcla las mediciones con la experiencia de uso. `gemma4:26b` tiende a ser demasiado creativo y ha dado muchos resultados falsos en el pasado.

| Capacidad | `qwen3.8:27b` | `gemma4:26b` | `qwen3-coder:30b` | `qwen3:4b` |
|---|---|---|---|---|
| Fiabilidad de lo que afirma | De confianza, verificada ejecutando | Baja, nunca es fuente de verdad | Sin evaluar | No aplica |
| Leer texto largo | Lento | Fuerte y rápido | Se hunde con contexto largo | No |
| Escribir código | De confianza | No fiable | Rápido con contexto corto | No |
| Calcular y verificar | De confianza | No fiable | Solo escribiendo código | No |
| Proponer hipótesis | Sin evaluar | Útil, por su creatividad | Sin evaluar | No |
| Clasificar y tareas pequeñas | Sobra | Sobra | Sobra | Suficiente |

### Qwen siempre al mando

El principal es `qwen3.8:27b` en todos los modos. Ningún modelo en el que no se confía decide, resume para el usuario ni aporta cifras. Usar o no `gemma4:26b` se decide en cada petición, y lo decide el harness, no el propio `gemma4:26b`.

### Estrategia de lectura según la petición

La detección del modo elige también cómo se lee el texto. Se prefiere siempre la estrategia más verificable que resuelva la petición:

| Petición | Estrategia | Quién lee |
|---|---|---|
| Contar, medir o sacar estadísticas | Código ejecutado sobre el corpus | Qwen escribe el script y la ejecución decide |
| Dónde aparece algo concreto | Búsqueda determinista con expresiones regulares o un índice | Ningún modelo |
| Qué dicen unos textos sobre un tema | Recuperación de pasajes por embeddings y lectura de esos pasajes | Qwen |
| Entender un texto que cabe en 60 a 80k tokens | Lectura directa | `qwen3.8:27b` |
| Entender un texto mayor | Lectura por partes con subagentes y reducción final | `qwen3.8:27b` |
| Relacionar partes muy alejadas de un texto enorme | Localización global | `gemma4:26b` propone citas, el harness las verifica y Qwen interpreta |
| Muchas preguntas seguidas sobre el mismo texto enorme | Texto cargado una vez con la caché caliente | `gemma4:26b` localiza, Qwen interpreta |
| Lluvia de ideas | Hipótesis etiquetadas como tales | `gemma4:26b` o Qwen |

Leer por partes es la alternativa de confianza a `gemma4:26b`. Con partes de 25k tokens, 200k tokens cuestan unos 12 minutos con `qwen3.8:27b`, porque cada parte es corta y no sufre el crecimiento del prefill con el contexto. Lo que pierde es la visión global: una relación entre dos partes alejadas solo aparece si la reducción final la busca. Ese es el hueco que puede cubrir `gemma4:26b`.

### `gemma4:26b` como herramienta, nunca como fuente

Cuando se usa, su salida tiene un contrato estricto:

1. **Solo devuelve citas literales con su ubicación**, por ejemplo folio y línea, o fichero y párrafo. No devuelve resúmenes ni conclusiones.
2. **El harness comprueba cada cita carácter a carácter contra el texto.** Las que no existen exactamente se descartan y se cuentan. Esa tasa de citas falsas mide de forma objetiva cuánto se puede fiar de `gemma4:26b` en cada tipo de petición.
3. **Qwen solo recibe las citas verificadas.** Nunca ve la paráfrasis de `gemma4:26b`, para que no la herede como verdad.
4. **Cualquier otra cosa que aporte es una hipótesis.** Entra en el registro de hipótesis y solo pasa a hallazgo si Qwen la verifica con código o con citas.

### Cálculo y verificación

- **Las cifras las calculan subagentes Qwen escribiendo código.** El número sale de ejecutar un script sobre el corpus, nunca de que un modelo cuente. Con la transcripción EVA del Voynich es imprescindible, porque ningún modelo cuenta glifos de forma fiable: el tokenizador parte esas palabras de manera arbitraria.
- **La verificación es independiente.** Un segundo subagente Qwen, con contexto limpio, reimplementa el cálculo sin ver el primer script, y se comparan las salidas. Si no coinciden, el resultado no cuenta.
- **El corpus se identifica por su huella.** Cada script comprueba el SHA-256 del corpus canónico antes de calcular, de modo que cualquier resultado se puede reproducir.

### Salvaguardas de veracidad

Valen para todo lo que el entorno presenta al usuario, venga del modelo que venga:

1. **Hipótesis y hallazgos van en registros separados.** Una hipótesis puede ser creativa si está marcada como tal. Un hallazgo exige pruebas.
2. **Las cifras no se transcriben, se enlazan.** El modelo escribe una referencia al resultado y el harness inserta el valor verificado.
3. **Cada afirmación lleva su procedencia.** Un cálculo verificado, con su script y su salida, o una cita comprobada con su ubicación. La interfaz marca lo que no la tiene.
4. **Un control determinista revisa cada respuesta.** Busca cifras sin referencia y citas que no existen en el texto.

### Lo verificable se verifica ejecutando

El principio vale también fuera de la investigación. En programación, la verificación son los tests, el linter y la compilación, no la opinión de un modelo. Las misiones de código las supervisan los tests más un Qwen con contexto limpio que revisa el diff. Un revisor de la misma familia comparte puntos ciegos con el autor, y la ejecución lo compensa.

### Memoria en modo investigación

| Hueco | Modelo | Ventana | Pesos | Caché KV en f16 |
|---|---|---|---|---|
| Principal y subagentes | `qwen3.8:27b`, un hueco de 131.072 y dos de 32.768 | 196.608 en total | 17 GB | 12 GB |
| Pequeño | `qwen3:4b` | 16.384 | 2,5 GB | 2,3 GB |
| Bajo demanda | `gemma4:26b`, solo mientras una petición lo necesita | Según la petición | 17 GB | Por medir, pequeña |

Sin `gemma4:26b` suman unos 34 GB, con holgura. Con él cargado rondan los 51 GB más su caché y los buffers, muy cerca del límite de 56 GB. Si hace falta margen, la caché de Qwen en q8_0 libera unos 6 GB. Un solo `qwen3.8:27b` con varios huecos sirve al principal y a los subagentes sin duplicar pesos.

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
4. **Modelo principal:** `qwen3.8:27b` en todos los modos. `gemma4:26b` es una herramienta que se invoca según la petición, con salida verificada, y nunca es fuente de verdad.
5. **Quién elige el modo:** reglas más clasificador al empezar cada tarea, o solo el modelo principal, como hace Claude Code con sus subagentes. La propuesta es combinar las dos cosas: reglas y clasificador para el modo de la tarea, y el agente principal para lanzar subagentes dentro de ella.
6. **Relación con ArchonHub:** reutilizar su catálogo de mediciones y sus perfiles de tarea, o empezar de cero.
7. **Convivencia de modos:** si se programa mientras corre una investigación, los dos usos comparten `qwen3.8:27b`. Hace falta una única configuración con varios huecos y caché KV unificada, o aceptar una recarga en cada cambio.

## Mediciones pendientes

- Repetir `qwen3-coder:30b` y `gemma4:26b` con 25k tokens y la máquina sin otro uso.
- Confirmar el pico inicial: repetir con el Mac en reposo y revisar el modo de energía.
- Tamaño real de la caché KV de `gemma4:26b`, en la línea `llama_kv_cache` del log.
- Evaluación de las estrategias de lectura con preguntas del corpus de respuesta conocida: lectura directa, por partes, recuperación de pasajes y localización con `gemma4:26b`. Se mide acierto, afirmaciones inventadas y tiempo.
- Tasa de citas de `gemma4:26b` que no superan la verificación literal, por tipo de petición.
- Generación con y sin flash attention en la versión actual.
- Reutilización real de la caché entre turnos, comparando en el log los tokens del prompt con los tokens evaluados.
- Guardar y restaurar la caché en disco con un modelo híbrido en `llama-server`.
- Compactación al final de la conversación, para confirmar que solo procesa la instrucción.
- Precisión del clasificador de modo sobre peticiones reales. Las tareas guardadas de Roo Code sirven como conjunto de prueba si se etiqueta a mano un centenar.
- Convivencia de memoria: comprobar que Ollama tiene en cuenta la memoria que ocupa un `llama-server` externo y no sobrecarga la GPU.
