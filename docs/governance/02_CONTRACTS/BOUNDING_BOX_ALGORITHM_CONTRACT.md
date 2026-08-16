# Contrato del algoritmo de bounding boxes v1.0.0 — FROZEN

## 1. Propiedad y alcance

Andrés Poiche implementa `src/data/make_boxes.py`; Monserrat Barba verifica. El
baseline acepta una imagen con un producto aislado y fondo transparente o uniforme.
No usa anotación manual silenciosa, segmentación aprendida ni `rembg`.

## 2. Clase

```text
class_id = 0
class_name = product
```

SKU, nombre y descripción se copian a la auditoría como metadatos y jamás cambian el
`class_id`.

## 3. Entrada

- imagen decodificable con `W>0`, `H>0`;
- fila `ACCEPTED` del manifest;
- `source_asset_id`, `sku_id`, SHA-256 y fondo registrado;
- parámetros explícitos y versionados.

```yaml
box_algorithm:
  version: pixel-extremes-v1
  alpha_threshold: PENDING_G3_PILOT
  background_uniformity_tolerance: PENDING_G3_PILOT
  foreground_delta: PENDING_G3_PILOT
  min_foreground_pixels: PENDING_G3_PILOT
```

Una configuración `PENDING_*` no procesa el dataset final. Los parámetros se fijan
con un piloto y permanecen idénticos para todas las imágenes y splits.

## 4. Máscara

### RGBA con transparencia real

```text
foreground(x,y) = alpha(x,y) > alpha_threshold
```

Un canal completamente opaco no demuestra fondo transparente y pasa al caso RGB.

### RGB con fondo uniforme

1. Reunir píxeles del borde.
2. Calcular color de fondo por mediana de canal.
3. Verificar uniformidad del borde con tolerancia configurada.
4. Calcular distancia de cada píxel al fondo.
5. Marcar primer plano cuando la distancia supera `foreground_delta`.
6. Rechazar si fondo, máscara o número de componentes no satisfacen el contrato.

El baseline no corrige sombras, ruido u objetos múltiples de manera particular por
imagen. Un caso incompatible se rechaza y conserva evidencia.

## 5. Extremos y bordes

Con `X,Y` como coordenadas enteras del primer plano:

```text
x_min = min(X)      # izquierda, inclusivo
x_max = max(X)      # derecha, inclusivo
y_min = min(Y)      # arriba, inclusivo
y_max = max(Y)      # abajo, inclusivo

x0 = x_min
x1 = x_max + 1
y0 = y_min
y1 = y_max + 1
```

Entonces:

```text
box_width_px  = x1 - x0
box_height_px = y1 - y0
x_center_px   = (x0 + x1) / 2
y_center_px   = (y0 + y1) / 2

x_center = x_center_px / W
y_center = y_center_px / H
width    = box_width_px / W
height   = box_height_px / H
```

## 6. Salida

Cada imagen aceptada produce un `.txt` de una línea:

```text
0 <x_center:.6f> <y_center:.6f> <width:.6f> <height:.6f>
```

La escritura de label y auditoría es atómica e idempotente.

## 7. Auditoría mínima

```text
source_asset_id,sku_id,class_id,image_path,label_path,image_width_px,
image_height_px,mask_method,algorithm_version,parameters_hash,
foreground_pixel_count,x_min,y_min,x_max,y_max,x0,y0,x1,y1,
x_center_px,y_center_px,box_width_px,box_height_px,x_center,y_center,
width,height,source_sha256,status,rejection_reason
```

Un rechazo conserva fila y no crea `.txt`.

## 8. Pruebas T01–T10

| ID | Caso | Esperado |
|---|---|---|
| T01 | `10×8`, x=2..6, y=1..5 | `0 0.450000 0.437500 0.500000 0.625000` |
| T02 | píxel (0,0) en `10×20` | `0 0.050000 0.025000 0.100000 0.050000` |
| T03 | toda la imagen | `0 0.500000 0.500000 1.000000 1.000000` |
| T04 | máscara vacía | rechazo, sin label |
| T05 | toca derecha/abajo | sin truncamiento |
| T06 | fondo no uniforme | rechazo |
| T07 | mismo input/config dos veces | mismos bytes, sin duplicar audit |
| T08 | clase distinta de 0 | fallo, sin outputs parciales |
| T09 | imagen corrupta | rechazo trazable |
| T10 | label/imagen huérfano | gate falla |

## 9. QA visual y aceptación

- 100% de aceptadas tienen exactamente una etiqueta.
- Cero cajas inválidas, huérfanos o clases distintas de 0.
- T01–T10 pasan.
- Una muestra reproducible muestra imagen, máscara, extremos y caja.
- Monserrat reproduce el piloto sin cambiar parámetros.
- Las limitaciones de fondo uniforme, reflejos, sombras y objetos recortados se
  documentan; la fórmula no sustituye inspección visual.
