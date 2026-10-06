# FreeQwenCode: plan de construcción

**Estado:** plan inicial del 6 de octubre de 2026. Se ejecuta con Claude Code en el Mac de referencia. Lo que se decide y se mide durante la ejecución se registra en [concepto.md](concepto.md), que es la fuente de verdad del diseño.

## Cómo se trabaja con este plan

1. **Antes de cada tarea**, el agente lee las secciones de `docs/concepto.md` que la tarea cita.
2. **Cada tarea tiene un agente asignado.** La sesión principal de Claude Code orquesta y delega en ese agente.
3. **Nada está hecho sin verificación.** El verificador revisa con contexto limpio cada tarea mediana o grande y comprueba su criterio de «hecho cuando» ejecutando, no opinando.
4. **Un commit por tarea**, con el mensaje en español y la casilla de la tarea marcada en este plan.
5. **Hitos y puntos de decisión son paradas obligatorias.** Se presenta lo hecho y lo medido, y se espera la aprobación del usuario.
6. **Las mediciones en el Mac no interrumpen otros usos.** Antes de cargar o descargar un modelo se consulta `/api/ps`. Si hay modelos cargados, se pregunta al usuario.
7. **No se toca nada ajeno a FreeQwenCode sin permiso:** ni Roo, ni PyLinkedin, ni la configuración de Ollama. Los servicios `com.archonhub.iogpu-wired-limit` y `com.archonhub.ollama-env` no se borran nunca.
8. **Idioma:** interfaz, documentación, comentarios y commits en español. Identificadores de código en inglés.

## Agentes

Se definen como subagentes de Claude Code en `.claude/agents/`. El nivel indica qué modelo de Claude usar: máximo, medio o rápido.

| Agente | Nivel | Papel | Herramientas |
|---|---|---|---|
| `arquitecto` | Máximo | Diseña módulos, interfaces y contratos. Resuelve dudas de diseño y revisa las piezas críticas | Lectura, búsqueda, escritura solo en `docs/` |
| `implementador-swift` | Medio | Escribe el núcleo en Swift y sus tests | Todas |
| `implementador-web` | Medio | Escribe la interfaz en TypeScript y sus tests | Todas |
| `medidor` | Medio | Ejecuta mediciones reales en el Mac respetando la regla 6 y documenta resultados | Todas |
| `verificador` | Máximo | Revisa con contexto limpio, ejecuta compilación, tests y escenarios adversos, y contrasta con los principios de diseño | Lectura, búsqueda, ejecución |
| `documentador` | Rápido | Mantiene al día `concepto.md`, este plan y la ayuda de usuario | Lectura, escritura en `docs/` |
| Usuario | | Aprueba hitos, toma las decisiones marcadas y aporta datos reales | |

Las tareas marcadas con ★ son críticas. En ellas el `arquitecto` diseña antes de implementar y revisa después.

## Pila técnica

| Pieza | Elección | Motivo |
|---|---|---|
| Núcleo | Swift 6 con Swift Package Manager | Compilado, ejecutable autónomo y acceso nativo a PDFKit, Metal y la memoria de los procesos |
| Servidor HTTP | Hummingbird 2 | Ligero y asíncrono |
| Cliente HTTP | AsyncHTTPClient | Flujo continuo de datos y tiempos de espera configurables, sin límite hasta el primer byte |
| Persistencia | SQLite con GRDB | Sesiones, registro de decisiones, índice de la Biblioteca y búsqueda de texto completo |
| Vectores | Accelerate | Similitud de embeddings rápida sin dependencias |
| Documentos | PDFKit, WebKit y `textutil` | Texto, páginas como imagen, formularios, HTML a PDF y HTML a Word, todo incluido en macOS |
| Interfaz | TypeScript, React y Vite | Interfaz fina que solo muestra. Se compila y se embebe en el ejecutable |
| Pruebas de interfaz | Playwright | Recorridos de extremo a extremo con el navegador |

Node.js solo se necesita para compilar la interfaz. El ejecutable final no depende de él.

## Requisitos de agilidad

La herramienta se va a usar entre 10 y 12 horas al día. Estos requisitos se miden en cada hito.

| Requisito | Objetivo |
|---|---|
| Arranque del núcleo | Menos de 1 s. El núcleo corre siempre como agente de inicio de sesión |
| Respuesta de la interfaz a una acción | Menos de 100 ms |
| Primera señal visible tras enviar una petición | Menos de 200 ms, con la estimación de espera |
| Sobrecoste del núcleo sobre el tiempo del modelo | Menos del 5 % |
| Memoria propia del núcleo en reposo | Menos de 200 MB, para no quitársela a los modelos |
| Cierre inesperado | Sin pérdida de trabajo. Las sesiones se guardan de forma continua y se reanudan |
| Uso sin ratón | Paleta de comandos y atajos para todas las secciones y acciones |
| Esperas | Ninguna bloquea la interfaz. Todas muestran estimación y se pueden cancelar o mandar al fondo |
| Trabajo en paralelo | Varias tareas a la vez, con cola visible en Actividad y aviso al terminar |

## Fase 0. Cimientos y validaciones

- [ ] **0.1 Repositorio y convenciones.** Agente: `arquitecto`. Crear la rama `main` desde el estado actual, la estructura de carpetas y un `Makefile` con compilar, probar y empaquetar. Ampliar `CLAUDE.md` con las convenciones. Hecho cuando: `make build` y `make test` funcionan en vacío.
- [ ] **0.2 Subagentes.** Agente: `arquitecto`. Crear `.claude/agents/` con los agentes de la tabla. Hecho cuando: Claude Code los lista y cada uno tiene su nivel y sus herramientas.
- [ ] **0.3 Herramientas del Mac.** Agente: `medidor`. Comprobar Swift, Node.js, `rg`, `osascript` y el `llama-server` incluido en Ollama. Hecho cuando: hay un informe con versiones. Si falta algo, se pregunta al usuario antes de instalar.
- [ ] **0.4 Mediciones que deciden la arquitectura** ★. Agente: `medidor`, con diseño del `arquitecto`.
  - Prueba de lectura de PDF e imágenes: PDFKit frente a `qwen3.8:27b` y `gemma4:26b`, con `herramientas/mediciones/lectura.py`.
  - Velocidad con la máquina libre, repitiendo `herramientas/mediciones/velocidad.py` para confirmar las cifras de `concepto.md`.
  - Huellas reales de memoria por modelo y ventana, incluida la caché KV, con el log de `llama-server` y la memoria de cada proceso.
  - `llama-server` directo con el fichero GGUF de `qwen3.8:27b`: llamada a herramientas con su plantilla, guardar y restaurar la caché con 80k tokens, tiempo de cada operación y comprobación de que no reprocesa.
  - Varios huecos con caché KV unificada.
  - Hecho cuando: los resultados están en `concepto.md`.
- [ ] **0.5 Punto de decisión del usuario.** Capa de inferencia del modelo principal, Ollama o `llama-server` directo, y convivencia de modos. El `arquitecto` presenta las opciones con los datos de 0.4.
- [ ] **0.6 Esqueleto del núcleo** ★. Agente: `implementador-swift`. Servidor solo en `127.0.0.1` con interfaz embebida, API y flujo de eventos. Persistencia, configuración, registros y agente de inicio de sesión con reinicio automático. Seguridad local: comprobación de las cabeceras `Host` y `Origin` y un token de sesión, para que ninguna web externa pueda dar órdenes al núcleo. Hecho cuando: arranca en menos de 1 s y rechaza peticiones de otro origen.
- [ ] **0.7 Esqueleto de la interfaz.** Agente: `implementador-web`. Barra lateral con todas las secciones, paleta de comandos, atajos y tema claro y oscuro. El Chat abre la app de Ollama. Hecho cuando: se navega por todo sin ratón y cada acción responde en menos de 100 ms.
- [ ] **0.8 Empaquetado.** Agente: `implementador-swift`. Compilación de publicación sin símbolos, con la interfaz minificada dentro del ejecutable y un instalador del agente de inicio. El ejecutable instalado vive fuera del Escritorio, porque launchd no tiene permiso para leer ahí. Hecho cuando: un único ejecutable funciona en una carpeta limpia y arranca solo al iniciar sesión.
- [ ] **Hito M0.** Agente: `verificador`. Esqueleto funcionando, mediciones documentadas, requisitos de agilidad del esqueleto cumplidos. Aprobación del usuario.

## Fase 1. Gestor de memoria y Lectura

- [ ] **1.1 Catálogo de modelos y requisitos.** Agente: `implementador-swift`. Huellas medidas en 0.4, capacidades de cada modelo, configuración fija por modelo y tipos de petición con sus requisitos. Lista de equivalentes vacía.
- [ ] **1.2 Monitor de memoria.** Agente: `implementador-swift`. Memoria del sistema, presupuesto de la GPU, huella de cada proceso, modelos cargados en Ollama y carga externa como Roo o PyLinkedin.
- [ ] **1.3 Elección del modelo** ★. Agentes: `arquitecto` e `implementador-swift`. Fase A del gestor como función pura que no recibe el estado de la memoria. Hecho cuando: el compilador impide pasarle la memoria y los tests cubren cada tipo de petición.
- [ ] **1.4 Decisiones de memoria** ★. Agentes: `arquitecto` e `implementador-swift`. Fase B del gestor: cargar en paralelo, descargar por valor de caché, guardar la caché antes de descargar, cola con prioridades y pregunta al usuario por encima de un minuto de reprocesado. Registro de decisiones dividido en elección y memoria.
- [ ] **1.5 Pasarela compatible con la API de Ollama** ★. Agente: `implementador-swift`. Flujo continuo sin límite hasta el primer byte, ventana fija por modelo y control de `keep_alive`.
- [ ] **1.6 Supervisor de `llama-server`.** Agente: `implementador-swift`. Solo si 0.5 lo decide. Arranque, parada, varios huecos, guardar y restaurar la caché.
- [ ] **1.7 Lectura.** Agentes: `implementador-swift` e `implementador-web`. Capa de texto con PDFKit, páginas como imagen para `qwen3.8:27b` y vista paralela para revisar. Herramienta disponible para las demás secciones.
- [ ] **1.8 Actividad.** Agente: `implementador-web`. Memoria por modelo, valor de caché, cola, registro de decisiones con su motivo y fijar modelos.
- [ ] **1.9 Escenarios adversos.** Agentes: `verificador` y `medidor`. Estados de memoria simulados y reales: dos peticiones simultáneas, un modelo cargado con otra ventana, una imagen que no cabe y una carga externa que aparece de repente. Hecho cuando: ninguna decisión cambia el modelo elegido y ninguna descarga afecta a una petición en curso.
- [ ] **Hito M1.** Aprobación del usuario.

## Fase 2. Código

- [ ] **2.1 Bucle agéntico** ★. Agentes: `arquitecto` e `implementador-swift`. `qwen3.8:27b` con llamada a herramientas, flujo continuo y un prefijo estable: system prompt y herramientas fijos, y los datos variables al final.
- [ ] **2.2 Herramientas del agente.** Agente: `implementador-swift`. Leer, buscar, editar con diff, escribir, ejecutar órdenes y git.
- [ ] **2.3 Permisos.** Agentes: `implementador-swift` e `implementador-web`. Aprobaciones, lista de órdenes permitidas, modo plan y evaluación del sandbox de macOS para las órdenes.
- [ ] **2.4 Puntos de restauración.** Agente: `implementador-swift`. Deshacer los cambios de un turno.
- [ ] **2.5 Proyectos.** Agentes: `implementador-swift` e `implementador-web`. Fichero de instrucciones por proyecto, reglas, glosario y colas de tareas.
- [ ] **2.6 Compactación y presupuesto por tiempo** ★. Agentes: `arquitecto` e `implementador-swift`, con validación del `medidor`. El resumen se pide al final de la conversación con el mismo prefijo. La decisión de compactar se toma con la curva de prefill medida. Hecho cuando: el log demuestra que la compactación solo procesa la instrucción.
- [ ] **2.7 Subagentes.** Agente: `implementador-swift`. Exploración con `qwen3.8:27b` en huecos cortos y tareas auxiliares con `qwen3:4b`, como títulos y mensajes de commit.
- [ ] **2.8 Nuevo y detección del modo.** Agentes: `implementador-swift` e `implementador-web`. Reglas, clasificador con `qwen3:4b` y el selector visible para cambiar la elección.
- [ ] **2.9 Conjunto de evaluación del clasificador.** Agente: usuario, con apoyo del `documentador`. Etiquetar un centenar de peticiones reales. El `verificador` mide el acierto.
- [ ] **2.10 Verificación por ejecución.** Agente: `implementador-swift`. Tests, linter y compilación integrados. Supervisión de misiones con tests y un Qwen con contexto limpio que revisa el diff.
- [ ] **2.11 Interfaz de Código.** Agente: `implementador-web`. Conversación con llamadas a herramientas, diffs, aprobaciones, estimaciones de espera y atajos.
- [ ] **2.12 Búsqueda web.** Agente: `implementador-swift`. A través del SearXNG local, si el usuario activa su formato JSON.
- [ ] **2.13 Evaluación de agilidad.** Agentes: `medidor` y `verificador`. Tiempos por turno y calidad de `qwen3-coder:30b` en subtareas cortas de código.
- [ ] **2.14 Punto de decisión del usuario.** Si `qwen3-coder:30b` se declara equivalente para alguna subtarea, a la vista de 2.13.
- [ ] **Hito M2.** FreeQwenCode es usable a diario para programar. Desde aquí, el usuario lo usa y anota lo que falla. Aprobación del usuario.

## Fase 3. Biblioteca

- [ ] **3.1 Ingesta.** Agente: `implementador-swift`. Carpetas vigiladas con PDF, Word, PowerPoint, Markdown y texto. Lectura para los escaneos. Huella de cada documento para detectar cambios.
- [ ] **3.2 Índice.** Agente: `implementador-swift`. Embeddings con `qwen3-embedding:0.6b` a través del gestor, búsqueda de texto completo y búsqueda híbrida.
- [ ] **3.3 Respuestas con citas** ★. Agentes: `implementador-swift` e `implementador-web`. Cada cita se comprueba literalmente contra el documento antes de mostrarse. La sección Biblioteca y la herramienta para las demás secciones.
- [ ] **3.4 Evaluación.** Agentes: usuario y `verificador`. Preguntas con respuesta conocida sobre documentos reales.
- [ ] **Hito M3.** Aprobación del usuario.

## Fase 4. Oficina

- [ ] **4.1 Espacio de trabajo común** ★. Agentes: `arquitecto`, `implementador-swift` e `implementador-web`. Tres columnas: entradas, resultado y comprobaciones. Un registro de comprobaciones en el que una en rojo impide dar el documento por terminado.
- [ ] **4.2 Informes.** Agentes: `implementador-swift` e `implementador-web`. Plantillas HTML convertidas a PDF con WebKit y a Word con `textutil`. Gráficos generados por código y cifras enlazadas a su cálculo.
- [ ] **4.3 Traducciones.** Agente: `implementador-swift`. Word y PowerPoint conservando el formato, y PDF hacia Word. Glosario del proyecto. Comprobaciones de estructura, números, nombres propios y glosario.
- [ ] **4.4 Comparar versiones.** Agente: `implementador-swift`. Diferencias literales calculadas por código y un resumen en el que cada punto apunta a una diferencia.
- [ ] **4.5 Rellenar formularios.** Agentes: `implementador-swift` e `implementador-web`. Formularios PDF con campos y plantillas de Word. Datos guardados en Personalización. Lectura de vuelta de cada campo. Nunca se envía ni se firma nada sin el usuario.
- [ ] **4.6 Evaluación con documentos reales.** Agentes: usuario y `verificador`.
- [ ] **Hito M4.** Aprobación del usuario.

## Fase 5. Investigación, Imágenes y Rutinas

- [ ] **5.1 Investigación** ★. Agentes: `arquitecto`, `implementador-swift` e `implementador-web`. Registro del corpus con su SHA-256, registros de hipótesis y hallazgos, subagentes que calculan escribiendo código, verificación por reimplementación independiente, cifras enlazadas y control final determinista. Estrategia de lectura según la petición. Contrato de citas de `gemma4:26b` y su tasa de citas falsas.
- [ ] **5.2 Evaluación de `gemma4:26b` en buenas condiciones.** Agentes: `medidor` y `verificador`. Contexto completo y razonamiento activado, sobre las tareas en las que falló.
- [ ] **5.3 Imágenes.** Agentes: `arquitecto` e `implementador-swift`. Averiguar cómo usa PyLinkedin Qwen-Image 2.1 y proponer el servicio compartido. Punto de decisión del usuario antes de tocar PyLinkedin. Después, la integración con el gestor, con memoria exclusiva, y la lectura de vuelta del texto de cada imagen.
- [ ] **5.4 Rutinas.** Agentes: `implementador-swift` e `implementador-web`. Tareas programadas, trabajos pesados en horas libres y avisos al terminar.
- [ ] **5.5 Voz, opcional.** Agente: `implementador-swift`. Transcripción con `faster-whisper` si el usuario lo pide.
- [ ] **Hito M5.** Aprobación del usuario.

## Puntos de decisión del usuario

| Cuándo | Qué se decide |
|---|---|
| 0.5 | Capa de inferencia del modelo principal y convivencia de modos |
| 2.9 | Etiquetas del conjunto de evaluación del clasificador |
| 2.14 | Modelos equivalentes para subtareas cortas de código |
| 5.2 | Si `gemma4:26b` gana algún papel más |
| 5.3 | Si se toca PyLinkedin para compartir Qwen-Image 2.1 |
| Cada hito | Aceptación de lo construido |
