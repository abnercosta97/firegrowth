# Contrato de dados v0.1

## Observações de fogo

O dataset público deverá fornecer `events.parquet`, `fronts.parquet` ou GeoParquet, `front_sensors.parquet` quando disponível, `sensors.parquet`, `coverage.parquet`, o limite do MATOPIBA e `manifest.json`.

Campos mínimos:

- `event_id`: identificador estável;
- `front_id`: identificador estável da frente;
- `event_id` em `fronts` como chave estrangeira;
- `observation_date`: data UTC representada pela frente;
- `geometry`: geometria original, CRS declarado;
- campos originais de contagem, FRP e qualidade, sem renomear silenciosamente a semântica;
- manifesto com versão da extração, filtros, cobertura, checksums e data de referência.

Eventos encerrados, absorvidos e fora do estado operacional atual devem ser incluídos quando fizerem parte da coorte histórica. A ausência de uma frente não pode ser interpretada como ausência de observação sem registro de cobertura.

## Derivados do benchmark

`features.parquet`, `targets.parquet` e `splits.parquet` devem manter `event_id`, `reference_date`, `horizon_days`, `dataset_revision`, `feature_cutoff` e `eligibility_reason`. O alvo principal é incremento de área da união cumulativa, em hectares por dia; áreas finais e meteorologia posterior são proibidas como preditores.

## Proveniência meteorológica

Para cada variável, registrar coleção STAC, item, asset, URL, checksum quando possível, janela temporal, unidade, resolução, método de extração espacial e latência conhecida. MERGE deve respeitar a janela D−1 13 UTC–D 12 UTC. Valores ausentes não são zero.
