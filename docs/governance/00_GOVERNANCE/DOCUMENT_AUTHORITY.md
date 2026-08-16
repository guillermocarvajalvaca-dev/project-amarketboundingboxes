# Autoridad documental

## 1. Precedencia

En caso de contradicción prevalece el nivel superior:

1. Ley, seguridad, privacidad, derechos de uso y políticas institucionales.
2. Guía y rúbrica oficial escrita de MCI-509.
3. Aclaraciones verificables del docente.
4. Contrato SDD congelado, con versión y SHA-256.
5. Manual operativo de la misma versión.
6. Contratos de módulos y datos.
7. Issues, briefs y decisiones aprobadas.
8. Código, datos y resultados observados en commit/ruta identificable.
9. Papers y materiales científicos.
10. Propuestas de modelos de lenguaje.

Una fuente inferior no transforma una sugerencia en requisito ni invalida una fuente
superior. Si dos autoridades del mismo nivel se contradicen, se aplica Stop-the-Line.

## 2. Fuentes observadas

| ID | Fuente | Estado | Uso autorizado |
|---|---|---|---|
| AUTH-01 | `Proyecto_Final_Guia_y_Entregables.md` | `OBSERVED` | Entregables, rúbrica y reproducibilidad |
| AUTH-02 | Captura docente `WhatsApp Image 2026-08-15 at 8.10.38 PM.jpeg` | `OBSERVED_PARTIAL` | Confirma scripts en `src/` y entrenamiento sin Jupyter |
| AUTH-03 | Instrucción del docente comunicada por Guillermo, 2026-08-15 | `PARTIALLY_VERIFIED` | Scraping Amarket, píxeles extremos, caja relativa y YOLO |
| AUTH-04 | `PAQUETE_CHATGPT_RPC_20260815.md` | `OBSERVED_SUPERSEDED` | Contexto histórico; no gobierna el alcance actual |
| AUTH-05 | `Qwen_markdown_20260815_etbi39mla.md` | `OBSERVED_DUPLICATE_CONTEXT` | Contexto auxiliar; no es autoridad independiente |
| AUTH-06 | Smoke test Amarket ejecutado 2026-08-15 | `EXECUTED` | Viabilidad técnica inicial de colección, ficha e imagen |
| AUTH-07 | Aceptación y directiva del coordinador, 2026-08-16 | `OBSERVED` | Congela v1.0.0; la aprobación del coordinador basta para autorizar fases |

## 3. Resoluciones de precedencia

- La guía escrita exige `train.py`, `evaluate.py`, `predict.py`, entorno reproducible,
  notebook CPU, informe LaTeX y análisis de errores.
- La aclaración comunicada por Guillermo añade el scraper y el algoritmo de píxeles
  extremos como columna vertebral.
- Las referencias del paquete histórico a checkout, identificación por SKU o RPC como
  dataset objetivo quedan reemplazadas por el SDD v1.0.0-FROZEN.
- La etiqueta YOLO es `class_id=0` para `product`; SKU permanece como metadato.
- `robots.txt` permite catálogo público, pero no constituye licencia de
  redistribución. La publicación de imágenes permanece condicionada a derechos.
- Guillermo, como coordinador y líder, es la autoridad única para abrir o cerrar una
  fase. Los acknowledgements del resto del equipo son evidencia colaborativa, pero no
  una precondición de autorización.
- La autoridad de fase no altera owners, revisores, trazabilidad ni la prohibición de
  autoaprobar PR.

## 4. Estados epistémicos

- `OBSERVED`: leído directamente.
- `EXECUTED`: comprobado mediante ejecución registrada.
- `INFERRED`: conclusión razonable, no demostrada.
- `UNKNOWN`: evidencia ausente.
- `NOT RUN`: prueba no ejecutada.
- `BLOCKED`: falta decisión o evidencia imprescindible.

Ningún estado inferior puede presentarse como `PASSED`.
