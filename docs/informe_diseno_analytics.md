# Informe de Diseño — Analytics Portal
**Proyecto:** ecommerce_Django
**Alcance:** Dashboard, Forecast & Trends, Data Simulator, AI Copilot
**Fecha:** 28 de agosto de 2026
**Objetivo declarado:** mayor claridad visual manteniendo un estilo oscuro (no necesariamente 100% oscuro) y analítico.

---

## 1. Metodología

Esta revisión no se basó solo en las capturas de pantalla enviadas: se inspeccionó el código real del proyecto para fundamentar cada observación en archivos y líneas concretas.

Archivos revisados:

- `templates/analytics/base_analytics.html` (sistema de diseño base: variables CSS, navbar, botones, tabla, tarjetas)
- `templates/analytics/dashboard.html`
- `templates/analytics/forecast.html`
- `templates/analytics/simulator.html`
- `templates/analytics/ai_chat.html`
- `apps/analytics/views.py`
- `apps/analytics/services/kpi_service.py`
- `apps/analytics/services/forecast_service.py`
- `apps/analytics/services/funnel_service.py`
- `apps/analytics/services/margins_service.py`

Esto permitió distinguir entre problemas puramente visuales (color, espaciado, jerarquía) y problemas de **datos disponibles pero no expuestos** — que resultaron ser el hallazgo más relevante del informe.

---

## 2. Impresión general

La base del sistema de diseño es sólida: variables CSS bien definidas (`--bg-primary`, `--bg-card`, `--accent`, etc.), tipografía monoespaciada para valores numéricos, navbar contenida y consistente entre vistas. Sin embargo, hay dos problemas transversales que explican la mayoría de los síntomas reportados:

1. **Falta de contraste de profundidad entre capas de fondo.** Los tres tonos de fondo (`--bg-primary`, `--bg-secondary`, `--bg-card`) están a solo 3-4% de luminosidad de distancia entre sí. Esto hace que las tarjetas "no se despeguen" del fondo, y es la causa raíz de por qué Forecast se percibe vacío incluso con dos gráficos, y por qué el Dashboard se siente plano pese a tener contenido.
2. **Un único color de acento (azul) para todo.** El mismo `--accent: #3b82f6` se usa para el estado activo del nav, el punto de los KPIs, el número de ranking, las líneas de los gráficos, las barras de categoría, los botones, el thumb de los sliders y el ícono del robot. Al no haber jerarquía semántica de color, nada se prioriza visualmente sobre el resto.

Estos dos puntos, resueltos a nivel de tokens CSS, mejoran las cuatro vistas simultáneamente sin necesidad de rediseñar cada pantalla por separado.

---

## 3. Colores

### 3.1 Paleta actual (`base_analytics.html`, líneas 14-23)

| Token | Valor | Uso |
|---|---|---|
| `--bg-primary` | `#08090a` | Fondo general de la página |
| `--bg-secondary` | `#0d0f12` | Fondo de secciones secundarias (`future-sec`, `slider-group`, `progress-box`) |
| `--bg-card` | `#111317` | Fondo de tarjetas (`analytics-card`) |
| `--border-color` | `#1e222b` | Bordes de tarjetas, inputs, divisores |
| `--text-primary` | `#f8fafc` | Texto principal |
| `--text-secondary` | `#64748b` | Texto secundario, labels, metadatos |
| `--accent` | `#3b82f6` | Color de marca / interacción |
| `--accent-dim` | `#1d4ed8` | Hover de botones de acento |

### 3.2 Problemas detectados

**a) Escalones de fondo demasiado cercanos.**
`#08090a` → `#0d0f12` → `#111317` son, en términos perceptuales, casi el mismo gris. El resultado es que una tarjeta y el fondo sobre el que está apoyada compiten muy poco en luminosidad, y todo el layout se lee como una superficie continua en vez de capas con jerarquía. Esto no requiere abandonar el estilo oscuro: se soluciona ensanchando la escala.

**b) Un solo acento para toda la interfaz.**
No hay diferenciación entre "esto es una acción" (botón), "esto es información neutra" (KPI), "esto es positivo" (crecimiento) y "esto es una advertencia" (pedidos abandonados, pendientes de pago). El KPI "Abandoned/Pending Orders" del Dashboard usa el mismo punto gris neutro que "Average Order Value", pese a ser conceptualmente una señal de alerta. En cambio, en Forecast (`forecast.html`, línea 31) ya existe el instinto correcto: el punto de "MoM Revenue Growth" cambia entre `#22c55e` (verde) y `#ef4444` (rojo) según el signo del valor — ese patrón está resuelto ad-hoc en un solo lugar y debería generalizarse a todo el sistema.

**c) Contraste al límite en texto secundario.**
`--text-secondary: #64748b` sobre `--bg-card: #111317` da un ratio de contraste de aproximadamente 4.3:1. Es aceptable para texto grande, pero los usos más frecuentes de este color son textos de 11-12px con `letter-spacing` (`.kpi-title`, encabezados de `.table-custom th`, `.section-title`) — exactamente el texto más denso en información de toda la interfaz, y el que más necesita margen de contraste, no menos.

### 3.3 Recomendaciones

| Cambio | Detalle |
|---|---|
| Ensanchar escala de fondos | `--bg-primary: #0a0b0d`, `--bg-secondary: #14161b`, `--bg-card: #1a1d24`, agregar `--bg-elevated: #20242c` para hover/estados activos |
| Set semántico de color (sobre el azul existente) | Verde `#22c55e` (positivo/crecimiento), Ámbar `#f59e0b` (pendiente/advertencia), Rojo `#ef4444` (negativo/crítico), un segundo tono frío (teal/violeta) reservado para series secundarias en gráficos |
| Reservar el azul (`--accent`) exclusivamente para marca y acciones primarias | Botones, nav activo, foco de inputs — no para significar "dato neutro" |
| Subir `--text-secondary` a ~`#8a97ab` (≈6:1 de contraste) | Sin tocar el resto de la paleta; mejora legibilidad de labels y headers sin aclarar visualmente la interfaz |

Con estos cuatro cambios de tokens, el sistema sigue siendo oscuro y analítico, pero cada capa se distingue de un vistazo y el color empieza a comunicar significado en vez de ser solo decorativo.

---

## 4. Dashboard — "quiero más datos"

### 4.1 Diagnóstico

Este es el hallazgo más importante de todo el informe: **el backend ya tiene los datos que faltan en la vista; simplemente no están conectados.**

`apps/analytics/views.py` → `DashboardView.get()` llama únicamente a `get_dashboard_kpis()`, que en `kpi_service.py` calcula:

- Ingreso neto del mes
- Órdenes completadas del mes
- Ticket promedio
- Carritos abandonados/pendientes (histórico total)
- Top 8 productos más vendidos

Eso es todo lo que llega al template `dashboard.html`. Sin embargo, dentro de `apps/analytics/services/` existen **dos servicios completos, funcionales, y no utilizados en ninguna vista**:

- **`funnel_service.py` → `calculate_funnel_and_promotions_service()`**: calcula embudo de conversión, tasa de abandono de carrito, ranking de productos abandonados, efectividad de cupones promocionales y distribución por método de pago. Acepta un parámetro `period` (`last_7_days`, `last_30_days`, `last_90_days`, `last_year`, `all_time`).
- **`margins_service.py` → `calculate_margins_service()`**: calcula margen bruto y ganancia agregados por producto, categoría, marca o proveedor, con ordenamiento configurable (`margin_desc`, `margin_asc`, `revenue_desc`, `profit_desc`).

Ninguno de los dos aparece referenciado en `views.py`. Esto significa que se puede aumentar significativamente la densidad de datos del Dashboard **sin escribir lógica de negocio nueva** — solo conectando servicios ya construidos.

### 4.2 Recomendaciones concretas

1. **Card "Conversión & Abandono"**, alimentada por `funnel_service`: embudo de conversión + ranking de productos con carritos abandonados + breakdown por método de pago. Esto además le da contexto real al KPI "Abandoned/Pending Orders", que hoy es un número aislado (538 en la captura) sin ninguna explicación de qué lo compone o por qué importa.
2. **Tabla o mini-gráfico "Márgenes por categoría"**, alimentada por `margins_service`, ubicada junto al Top 8 de productos. Esto transforma "los más vendidos por unidades" en "los más vendidos **y** más rentables" — una narrativa analítica bastante más fuerte para un portfolio orientado a negocio.
3. **Comparación mes contra mes en las 4 KPI cards actuales.** Hoy cada card muestra solo el valor del mes en curso, sin ninguna referencia de tendencia. Un chip pequeño de variación (flecha + % vs. mes anterior) es barato de implementar visualmente y aporta mucha profundidad percibida sin rediseñar el layout.
4. Considerar reutilizar los datos de categoría que ya calcula `forecast_service.py` (usados en la vista de Forecast) para agregar una vista rápida de distribución de ingresos por categoría también en el Dashboard, evitando que la página termine siendo "una tabla y una tarjeta promocional de Power BI".

---

## 5. Forecast & Trends — "está muy vacío"

### 5.1 Diagnóstico

La página tiene 3 KPI cards y 2 gráficos (`forecastChart` a la izquierda, `categoryChart` a la derecha), ambos con `height: 280px` fijo (`forecast.html`, líneas 51 y 59). Debajo de esa fila no hay ningún otro contenido — la mitad inferior de la pantalla queda completamente en blanco, que es exactamente la sensación de vacío reportada.

Puntos adicionales:

- Las bandas de "Upper Bound" y "Lower Bound" del gráfico de forecast (`forecast.html`, líneas 121-137) se dibujan como líneas punteadas grises al 25% de opacidad (`rgba(148, 163, 184, 0.25)`), que en la práctica son casi invisibles — se pierde información de incertidumbre del modelo que podría ocupar espacio visual de forma útil.
- El layout de columnas es 8/4 (`col-lg-8` / `col-lg-4`), lo cual dejar huecos irregulares en los costados del gráfico de categorías cuando hay pocas categorías con barras cortas.

### 5.2 Recomendaciones concretas

1. **Aumentar la altura de ambos gráficos** de 280px a un rango de 380-420px — cambio de una línea de CSS con impacto inmediato en la sensación de "vacío".
2. **Convertir las bandas de confianza en un área sombreada** entre upper y lower bound (fill entre datasets de Chart.js) en lugar de dos líneas punteadas casi invisibles. Esto llena espacio visual de forma legítima (comunica incertidumbre del modelo) sin inventar datos nuevos.
3. **Agregar un tercer panel** debajo de la fila de KPIs, por ejemplo un gráfico de barras de variación mensual (MoM %) reutilizando el mismo array `historical_revenue` que ya llega al JavaScript vía `forecastData` — no requiere una llamada nueva al backend.
4. Si `forecast_service.py` calcula alguna métrica adicional por categoría (crecimiento proyectado por categoría, por ejemplo) que hoy no se renderiza, es candidata directa para llenar el espacio inferior con datos reales en vez de whitespace decorativo.

---

## 6. Data Simulator — sliders desbalanceados

### 6.1 Diagnóstico

Se identificaron dos problemas distintos, ambos verificables en `simulator.html`:

**a) No hay validación de que los pesos de venta por tier sumen 100%.**
Los cuatro sliders "Sales Weight" (Tier 1 a Tier 4, líneas 61-100) tienen valores por defecto que sí suman 100% (50 + 30 + 15 + 5), pero no existe ningún elemento en la interfaz que comunique esa restricción. Un usuario puede mover el Tier 1 a 80% dejando los demás sin cambios, y el modelo queda internamente inconsistente sin ningún aviso visual ni de validación antes de generar el dataset.

**b) Todos los sliders lucen visualmente idénticos sin importar su rango.**
El slider "Target User Base" tiene rango 500-5000 con valor por defecto 5000 (línea 117) — es decir, nace pegado al extremo derecho de su propio rango, lo cual visualmente se lee como un control "roto" o "al tope". En cambio, los sliders de "Category Weights" (rango 0.1-2.0, líneas 158-192) tienen valores por defecto que los agrupan cerca del extremo izquierdo-medio. El resultado es una grilla de controles que parece arbitraria en vez de "afinada", porque no hay ninguna referencia visual (marca central, ticks) que indique dónde está parado cada valor relativo a su propio rango.

### 6.2 Recomendaciones concretas

1. **Agregar un contador de suma en vivo** debajo de los 4 sliders de "Sales Weight", del tipo "Total: 100%", que cambie a ámbar/rojo si la suma se aleja de 100%. Alternativamente (más trabajo, pero más pulido): hacer que los sliders se reajusten proporcionalmente entre sí al mover uno, como una interacción de tipo "distribución de presupuesto".
2. **Recentrar los valores por defecto dentro de su propio rango** donde el dominio lo permita — por ejemplo, llevar el default de "Target User Base" a un punto medio (~2500-3000) en lugar del techo del rango (5000).
3. **Agregar una marca de referencia visual** (tick central o línea de referencia) en el track de cada slider, para que la posición del thumb comunique "bajo / medio / alto" relativo a su rango, y no solo un valor numérico absoluto en el label.
4. Nota menor: en el runtime observado en las capturas, los "Category Weights" cargan uniformemente en 0.5 pese a que los valores por defecto codificados en el HTML son distintos entre sí (1.0 / 0.9 / 1.0 / 1.0 / 0.7) — vale la pena confirmar si la configuración cargada en tiempo real está aplanando estos valores intencionalmente, porque visualmente cinco sliders idénticos transmiten "esto no importa" incluso si el dato subyacente es distinto.

---

## 7. AI Copilot — simplificar al estilo ChatGPT / Claude / Gemini

### 7.1 Diagnóstico

La comparación estructural con las interfaces de referencia (ChatGPT, Claude, Gemini) es clara: esos productos usan una sola columna centrada de ancho moderado (~720-820px), diferencian los turnos de conversación principalmente por alineación y un tinte sutil de fondo (no por chrome pesado), y no muestran un panel permanente de métricas internas del sistema.

La implementación actual (`ai_chat.html`) invierte ese patrón: es un layout de dos columnas donde el panel derecho `.telemetry-sidebar` (320px de ancho fijo, línea 73) muestra de forma permanente: latencia de última consulta, modelo activo (`gemini-3.7-flash`), ID de agente, protocolo (`SSE Stream (HTTP/2)`), turnos en sesión, tokens estimados, ID de sesión y estado de autenticación JWT. Este es lenguaje y densidad de un panel de estado de sistema (ops dashboard), no de un asistente conversacional — y es la razón por la que esta vista se percibe "cargada" pese a tener, en la práctica, menos datos de negocio reales que el Dashboard.

Adicionalmente:

- Cada mensaje del chat (`.message-row`) combina un avatar cuadrado (`.avatar-icon`, 34x34px) con una tarjeta con borde propio (`.message-content`, con `border` + `bg-card` + `border-radius`) — dos elementos de "chrome" por turno de conversación.
- El header incluye el badge "agent: analytics" junto al subtítulo "Multi-turn Managerial AI Agent & Copilot" (líneas 872-877) — terminología interna/técnica expuesta directamente en una superficie orientada a usuario final.

### 7.2 Recomendaciones concretas

1. **Ocultar el sidebar de telemetría por defecto.** Puede conservarse como panel de diagnóstico colapsable (por ejemplo, un ícono que lo despliega) para mantener el framing de "staff only", pero no debe competir visualmente con el chat en la vista por defecto.
2. **Ampliar la columna de chat** a un ancho máximo de ~760-840px, centrada, una vez liberado el espacio del sidebar — esto replica directamente el patrón de lectura de las interfaces de referencia mencionadas.
3. **Simplificar la burbuja de mensaje.** Considerar eliminar el avatar en los mensajes del usuario (mantenerlo solo, opcionalmente, en las respuestas del asistente) y diferenciar los turnos únicamente con un tinte de fondo sutil, reduciendo el chrome visual por turno a la mitad.
4. **Revisar el copy del header.** "agent: analytics" y el lenguaje de "Multi-turn Managerial AI Agent" son términos de arquitectura interna filtrándose a la interfaz — o se retiran de la vista por defecto, o se convierten en un tag visualmente discreto (sin borde, tono fantasma) que no compita con el título principal.
5. Mantener los 4 chips de "Preguntas Sugeridas de Negocio" — ese elemento sí está alineado con el patrón de referencia (prompts sugeridos al inicio de la conversación); solo confirmar que se ocultan una vez que la conversación tiene mensajes, si no lo hacen ya.

---

## 8. Consistencia

| Elemento | Problema | Recomendación |
|---|---|---|
| Estilos inline | `style="font-size: 12px;"` y similares se repiten más de 15 veces entre `dashboard.html`, `forecast.html` y `simulator.html` | Extraer a un par de clases utilitarias (`.text-xs`, `.text-2xs`) dentro del bloque `<style>` de `base_analytics.html` |
| Colores en Chart.js | Los grids y ticks de los gráficos (`forecast.html`, líneas 150-193) usan hex hardcodeados (`#1e222b`, `#64748b`, `#94a3b8`) que duplican las variables CSS ya definidas en el mismo archivo | Leer los colores desde las variables CSS (`getComputedStyle`) o centralizarlos en un objeto JS compartido, para evitar que se desincronicen si la paleta cambia |
| Puntos de color en KPIs | El color del punto indicador (`.kpi-indicator`) se sobreescribe manualmente por KPI vía `style="background-color: ..."` en vez de una clase semántica | Crear clases `.kpi-dot-positive`, `.kpi-dot-neutral`, `.kpi-dot-warning` ligadas al set semántico de color propuesto en la sección 3.3 |

---

## 9. Accesibilidad

| Aspecto | Estado | Recomendación |
|---|---|---|
| Contraste de texto secundario | `#64748b` sobre `#111317` ≈ 4.3:1, al límite de AA para texto menor a 18px, justo en los usos más densos en información (`kpi-title`, headers de tabla) | Subir a ~`#8a97ab` (≈6:1) sin alterar el resto de la jerarquía tonal |
| Asociación de labels en sliders | Los `<input type="range">` no tienen `for`/`id` ni `aria-labelledby` vinculado al `<span>` de su etiqueta | Asociar explícitamente cada label con su input correspondiente |
| Tamaño de leyenda en gráficos | Chart.js configura `font: { size: 10 }` en leyendas y ejes (`forecast.html`, líneas 145, 151, 155, 188) | Subir a 11-12px, especialmente considerando que hay espacio vertical disponible de sobra en Forecast |
| Foco visible en controles | No hay override visible de `:focus` en sliders ni botones más allá del default del navegador | Definir un estado de foco consistente con el acento de marca, útil tanto para accesibilidad como para reforzar la identidad visual |

---

## 10. Qué funciona bien

- El sistema de variables CSS y clases reales (`.analytics-card`, `.kpi-title/value/meta`, `.table-custom`) está inusualmente bien organizado para un proyecto individual de portfolio — no son parches ad-hoc sobre Bootstrap, sino un sistema de componentes coherente.
- El uso de fuente monoespaciada específicamente para valores numéricos (KPIs, montos y unidades en tabla, log feed del simulador) es una señal correcta y reconocible de "producto analítico" — conviene mantenerla y extenderla a las nuevas secciones que se agreguen.
- El estado activo de la navegación (subrayado de acento, minimalista) está bien resuelto y no necesita cambios.
- El patrón semántico verde/rojo ya presente en el KPI de "MoM Revenue Growth" de Forecast demuestra que el criterio de diseño correcto ya existe en el equipo — solo falta generalizarlo al resto del sistema.

---

## 11. Recomendaciones priorizadas

1. **Conectar `funnel_service` y `margins_service` al Dashboard.** Es el mayor impacto posible sobre "quiero más datos", y no requiere backend nuevo — solo exponer servicios ya construidos.
2. **Ajustar la escala de fondos + introducir un set semántico de color chico.** Un solo cambio de tokens CSS mejora la claridad visual en las cuatro vistas a la vez, incluyendo el efecto de vacío en Forecast, sin abandonar el estilo oscuro.
3. **Simplificar AI Copilot a una columna, con el panel técnico colapsado por defecto.** Responde directamente a la referencia de ChatGPT/Claude/Gemini solicitada.
4. **Agregar contador de suma (o auto-rebalanceo) en los sliders de Tier del Simulator, y recentrar los valores por defecto dentro de sus rangos.** Resuelve concretamente el desbalance reportado.
5. **(Menor, higiene de código)** Extraer estilos inline repetidos a clases utilitarias y centralizar los colores de Chart.js en variables compartidas con el CSS — no es urgente, pero refuerza la narrativa de "proyecto data-driven" cuidado también a nivel de código.

---

*Fin del informe.*
