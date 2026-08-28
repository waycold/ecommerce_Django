# Reconciliación Django API vs. Power BI (DAX) — Agosto 2025

**Fecha del análisis:** 2026-08-27
**Método:** comparación de código (`apps/analytics/services/*`, `apps/orders/models.py`) contra el modelo semántico real, consultado en vivo por XMLA contra Power BI Desktop ("Ecommerce") mediante DAX, y contrastado contra capturas del dashboard.

---

## Cambios aplicados en Power BI (2026-08-27) — naming de Revenue

Se corrigió la ambigüedad entre "Product Revenue" y "Net Revenue" directamente en el modelo (vía DAX en vivo, con rename en cascada — no rompió ninguna medida dependiente):

| Antes | Ahora | Motivo |
|---|---|---|
| `Net Revenue` (Fact Orders) | **`Order Revenue`** | "Net Revenue" es un término contable con significado propio (ingreso bruto neto de devoluciones), que no es lo que calcula esta fórmula (subtotal + shipping − descuento = valor total de la orden). |
| `Net Revenue (Projected)` (Fact Sales) | **`Order Revenue (Projected)`** | Idem, mantiene coherencia con el rename anterior. |
| `Gross Margin %` = Gross Profit / Order Revenue | **`Gross Margin %` = Gross Profit / Product Revenue** | Corrige la asimetría: antes mezclaba una ganancia calculada sobre Product Revenue con un denominador de Order Revenue (dos bases distintas). Ahora coincide exactamente con `avg_gross_margin_pct` de la API de Django (37,61% para agosto 2025, verificado). |
| *(no existía)* | **`Blended Margin %`** = Gross Profit / Order Revenue (nueva medida) | Preserva el comportamiento que tenía `Gross Margin %` antes de la corrección, para quien quiera el margen mezclando ingreso de mercadería con envío/descuento explícitamente. |

Todas las medidas que dependían de `Net Revenue` (Average Order Value, Historical/Projected Revenue Paid/Unpaid, Target Country/Age Group/Gender/Payment y sus versiones %) se actualizaron automáticamente por el rename en cascada y se validaron con consultas DAX en vivo — sin errores.

También se agregaron descripciones a `Product Revenue`, `Gross Profit`, `Order Revenue`, `Average Order Value` y a la columna `Financial statement` (documentando que `PROCESSING` es un rename intencional hecho solo en Power BI para lo que Django llama `PAID`).

**Pendiente, del lado de Django** — ver recomendaciones abajo. La API tiene la misma ambigüedad (`revenue` significa cosas distintas en `query_engine_service.py`/`margins_service.py` vs. `kpi_service.py`), pero ese endpoint lo consume un microservicio de IA/chatbot, así que el cambio ahí es más delicado y no se aplicó todavía.

## Resumen ejecutivo (corregido)

Causa raíz confirmada, con match exacto contra el dashboard: **el filtro de fecha "Last 12 Months" (relativo) del header está intersectando con el rango fijo 8/1/2025–8/31/2025**. Como ese slicer relativo se recalcula contra la fecha real de hoy cada vez que abrís el reporte, la intersección de ambos filtros deja una ventana efectiva de sólo **4 días (28 al 31 de agosto de 2025)**, no el mes completo — aunque el date picker siga mostrando "8/1/2025 – 8/31/2025".

No es un problema de fórmulas DAX ni de datos desincronizados. Es un filtro relativo que, sumado a uno absoluto, achica la ventana silenciosamente y **cambia todos los días**.

Dos hallazgos de mi primera pasada quedan descartados con tu feedback:

- ~~Hallazgo 1 (status PAID→PROCESSING como desincronización de datos)~~: es un rename **intencional** que hiciste sólo en Power BI para separar Paid/Unpaid con más claridad. No es un bug — abajo dejo una nota de por qué igual conviene documentarlo.
- ~~Hallazgo 3 (filtro de categoría pegado)~~: incorrecto, como bien señalaste. `Health_and_Household` en 181.570,87 era una coincidencia numérica con el total de categoría del mes completo, no con lo que mostraba tu tarjeta. La cifra real (181.377,75 en el tooltip de "Historical Revenue Paid") viene de otro lado, ver abajo.

---

## Causa raíz confirmada — intersección de dos filtros de fecha

Tu dashboard tiene **dos** controles de fecha en el header:

1. Un date range picker fijo: `8/1/2025` → `8/31/2025`.
2. Un slicer de fecha relativa: `Last / 12 / Months`, que Power BI muestra resuelto como `8/28/2025 – 8/27/2026` (porque hoy, en el reloj real, es 2026-08-27).

Ambos filtros actúan sobre el mismo campo de fecha y se combinan con AND. La intersección de `[8/1/2025, 8/31/2025]` y `[8/28/2025, 8/27/2026]` es `[8/28/2025, 8/31/2025]` — **4 días**, no 31.

Repliqué esa ventana exacta (28 al 31 de agosto de 2025, `Financial statement = "paid"`) contra el modelo en vivo y los números calzan con tu dashboard:

| Métrica | Dashboard (captura) | DAX directo, sólo 28–31 ago 2025 |
|---|---:|---:|
| Product Revenue | $165.03K | **$165.075,07** |
| Sum of Quantity | 136 | 138 |
| Gross Margin % | 31,45% | 31,36% |
| Average Order Value | $8.24K | $7.909,65 |
| Paid orders | 22 | 23 |
| Historical Revenue Paid (tooltip) | 181.377,75 | 181.922,04 |
| **Amazon_Fashion — Net Revenue (Top 8 Categories, tooltip)** | **$36.016,63** | **$36.016,63 (match exacto)** |

El match de Amazon_Fashion es exacto al centavo. Las diferencias chicas en el resto (23 vs 22 órdenes, 138 vs 136 unidades, etc.) son consistentes con que el slicer "Last 12 Months" se resuelve contra la hora exacta en que abriste/refrescaste el reporte, no contra medianoche — así que el corte de "hace 12 meses" cae en algún punto del 27/28 de agosto, no en un día limpio. No hace falta perseguir ese resto de diferencia: la magnitud y el top-category ya confirman la causa.

**Por qué esto es grave más allá de esta comparación puntual:** como el segundo filtro es relativo ("últimos 12 meses" respecto de hoy), la ventana efectiva se corre todos los días. Con el tiempo, agosto de 2025 va a quedar completamente afuera de "los últimos 12 meses" y esta misma combinación de filtros va a mostrar el dashboard en blanco para ese rango — sin que cambie nada en los datos. Cualquier comparación "mismo período" entre Django (que toma `date_from`/`date_to` literalmente) y este dashboard va a seguir sin coincidir mientras convivan los dos filtros de fecha.

**Acción recomendada:** sacar el slicer "Last 12 Months" de esa página (o dejarlo pero documentarlo/deshabilitarlo antes de comparar contra la API), o unificarlo con el date range picker para que no puedan pisarse.

---

## Sobre el status PAID → PROCESSING (no es un bug, pero documentalo)

Confirmé en el modelo que `Fact Orders[Status]` no tiene ninguna fila con el literal `"PAID"` — tiene `PROCESSING` en su lugar (546 filas de 5.719 totales), y la columna calculada `Financial statement` ya lo contempla:

```dax
Financial statement =
SWITCH(TRUE(),
    'Fact Orders'[Status] IN {"PROCESSING", "SHIPPED", "DELIVERED"}, "paid",
    'Fact Orders'[Status] IN {"PENDING", "CANCELED"}, "unpaid",
    "indefinite"
)
```

Como contaste, es un rename intencional que hiciste sólo en Power BI. La única recomendación acá es documentarlo en el modelo (una descripción en la columna `Status` o `Financial statement` alcanza), porque si en algún momento comparás por status literal contra la API de Django (que sí usa `"PAID"`), vas a necesitar recordar el mapeo — pero no es algo para arreglar.

---

## Otros puntos ya señalados en el informe DAX original (siguen vigentes, no relacionados con el gap de agosto)

1. **NPS no estándar**: Promotor = rating 5, Pasivo = rating 4, Detractor ≤ 3, en vez de la escala clásica 0-10.
2. **Denominadores de NPS inconsistentes**: `Net Promoter Score` excluye ratings en blanco; `% Promoters/Detractors/Passives` no.
3. **Medidas con `TODAY()`**: `Net Revenue (Projected)`, `Historical/Projected Revenue Paid/Unpaid` — cambian según el día real en que se evalúan (relacionado con el mismo problema del slicer relativo).
4. **`Cancellation Rate` / `Successful Orders`** en DAX usan `{"PROCESSING","SHIPPED","DELIVERED"}` hardcodeado — coherente con tu rename intencional, pero si algún día cambiás la etiqueta de nuevo hay que tocar estas medidas a mano.
5. **`Gross Margin %`** mezcla `Product Revenue` (solo subtotal) con `Net Revenue` (subtotal + shipping − descuento) en el denominador.

---

## Cómo verificarlo vos mismo en Power BI Desktop

1. En el visual del slicer "Last / 12 / Months", cambialo a "All" o quitalo de la página.
2. Volvé a mirar "Revenue by Month" / las tarjetas: deberían acercarse a los ~1.545.000 de revenue para agosto 2025 completo (status pagado/enviado/entregado), no a 181k.
3. Si querés mantener ambos filtros para otros usos, agregá una medida o texto que muestre el rango de fecha *efectivo* (intersección), para no confiarte del date picker fijo solo.
