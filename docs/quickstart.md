# Guia rápido

## Validar o dataset

```bash
uv run firegrowth validate /mnt/dados/publicacoes/matopiba-fire-events/release
```

## Usar a API

```python
import numpy as np
from firegrowth import cumulative_area_growth, regression_metrics

areas = np.array([100.0, 125.0, 160.0])
growth = cumulative_area_growth(areas, horizon_days=1)
print(growth)  # [25., 35., nan]
print(regression_metrics(np.array([25., 35.]), np.array([20., 40.])))
```

Para geometrias WKT, use `firegrowth.geometry.union_area_hectares`. O método
reprojeta EPSG:4326 para EPSG:6933 antes de calcular hectares. Não calcule área
diretamente em graus.
