# Protocolo do benchmark

1. Construir a união cumulativa das geometrias por evento e data.
2. Calcular `growth_ha_day` para o horizonte escolhido.
3. Remover referências sem acompanhamento completo, sem recodificá-las como zero.
4. Separar 2025 em desenvolvimento/validação cronológica e reservar 2026 para teste temporal.
5. Comparar zero, último crescimento, média móvel, regressão e um modelo de árvores.
6. Reportar MAE, RMSE e viés por horizonte, período e evento.
7. Estimar incerteza por reamostragem pareada de eventos ou famílias, nunca por linhas independentes do mesmo episódio.

O resultado é crescimento observado do produto DescrEVE, não área queimada física nem velocidade de propagação de chamas.

Antes do treinamento, `firegrowth analyze` gera a caracterização descritiva
dos eventos sem meteorologia: estrutura temporal, duração, lacunas, áreas,
sensores, detecções, crescimento geométrico e disponibilidade dos horizontes.
Eventos sem data futura exata ou que cruzam partições são contabilizados como
exclusões; não são convertidos silenciosamente em crescimento zero.

## Dados publicados

O benchmark deve usar uma revisão imutável do dataset:

```text
abnercosta97/matopiba-fire-events
revision: v1.0.0
commit: 9b5a8f1dae609b1f00fee55b99bf27be969bf737
```

O release cobre 2025-01-01 a 2026-11-09. O ano de 2026 é incompleto e as
amostras finais devem respeitar o horizonte do alvo. Detecções individuais não
possuem vínculo histórico autoritativo com eventos/frentes; elas não devem ser
agregadas por evento sem uma regra adicional documentada.
