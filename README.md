# firegrowth

Biblioteca modular para construir e avaliar previsões da taxa de crescimento da extensão espacial observada de eventos de fogo DescrEVE.

O projeto é uma implementação inicial do contrato científico do estudo CAP-408-3 no MATOPIBA. O pacote não redistribui dados operacionais, credenciais ou arquivos meteorológicos. Ele trabalha com tabelas derivadas versionadas e permite que fontes externas sejam conectadas por adaptadores.

## Escopo v0.1

- alvo contínuo em hectares/dia, derivado de geometrias cumulativas;
- baselines zero, último valor e média móvel;
- divisão temporal por blocos, sem aleatorização de dias do mesmo evento;
- MAE, RMSE e viés;
- configuração declarativa em YAML/JSON;
- manifesto de execução com versão dos dados e parâmetros.

## Instalação de desenvolvimento

```bash
uv sync
uv run pytest
uv run firegrowth --help
```

Para validar o release local do dataset:

```bash
uv run firegrowth validate /caminho/matopiba-fire-events/release
```

O comando verifica tabelas obrigatórias, chaves de eventos e frentes órfãs.

Para preparar e executar o benchmark mínimo:

```bash
uv run firegrowth prepare \
  /mnt/dados/publicacoes/matopiba-fire-events/release \
  /mnt/dados/publicacoes/matopiba-fire-events/derived/benchmark-v0.1.0

uv run firegrowth run \
  /mnt/dados/publicacoes/matopiba-fire-events/release \
  /mnt/dados/publicacoes/matopiba-fire-events/derived/benchmark-v0.1.0 \
  --horizons 1,3
```

O resultado contém áreas cumulativas por evento–dia, tabelas supervisionadas,
previsões dos três baselines, métricas CSV, exclusões e manifesto com a revisão
do dataset.

Para gerar as estatísticas exploratórias sem meteorologia, instale o extra de
análise e execute:

```bash
uv sync --extra analysis
uv run firegrowth analyze \
  /mnt/dados/publicacoes/matopiba-fire-events/release \
  /mnt/dados/publicacoes/matopiba-fire-events/derived/benchmark-v0.1.0 \
  /mnt/dados/publicacoes/matopiba-fire-events/reports/exploratory_events
```

O relatório inclui estatísticas de eventos, frentes, detecções, duração,
lacunas, áreas, crescimento reconstruído, elegibilidade dos horizontes,
partições temporais, cobertura e figuras. A meteorologia não é carregada nessa
etapa.

Os derivados preservam a separação entre a fonte observacional e a análise:
`front_daily_union.parquet` contém a união diária em WKT e a área cumulativa;
`event_summary.parquet` contém duração do catálogo, intervalo observado,
faixas de duração, tipos e estatísticas por evento; e
`reconstruction_audit.parquet` compara os incrementos reconstruídos com o
campo original `delta_area`.

Para executar a análise específica da coorte multidiária:

```bash
uv run firegrowth multiday \
  /mnt/dados/publicacoes/matopiba-fire-events/release \
  /mnt/dados/publicacoes/matopiba-fire-events/derived/benchmark-v0.1.0 \
  /mnt/dados/publicacoes/matopiba-fire-events/reports/multiday_analysis
```

O filtro retrospectivo é `observed_days >= 2`, calculado a partir das frentes.
Ele não é usado como atributo futuro na tabela de alvos.

O pacote usa `src/` layout, `uv.lock`, testes científicos e configuração explícita, seguindo a aula “Da ideia ao PyPI — Benchmarks de nowcasting”.

## Dados esperados

O contrato público está em `docs/data_contract.md`. O dataset de eventos deve conter eventos, frentes, geometrias, datas UTC, chaves estáveis, cobertura e manifesto. Meteorologia SAMeT/MERGE será obtida separadamente via STAC e registrada no manifesto; nenhum segredo deve entrar no repositório.

## FAIR e citação

Cada experimento deve guardar `configs/`, a revisão do dataset, hashes dos arquivos, ambiente e resultados. Releases deverão receber tag SemVer, DOI via Zenodo e referência em `CITATION.cff`.

## Estado do projeto

O pacote está em desenvolvimento (`0.1.0`). A leitura e validação do dataset e
as funções básicas de alvo, geometria, partição temporal e métricas estão
implementadas. A construção completa de atributos meteorológicos e os modelos
de produção ainda são etapas futuras; nenhum resultado científico é incluído.
