# firegrowth

`firegrowth` é uma biblioteca para construir e comparar previsões da taxa de
crescimento da extensão espacial observada de eventos de fogo DescrEVE.

O pacote separa aquisição, geometria, construção do alvo, atributos,
partições, modelos, métricas e execução do benchmark. O experimento MATOPIBA
é uma configuração do pacote, não uma regra embutida em todas as funções.

## Princípios

- dados e software têm versões identificáveis;
- nenhum resultado usa informação posterior ao instante de referência;
- eventos que atravessam partições temporais não são divididos silenciosamente;
- crescimento observado não é interpretado como área queimada física;
- cada resultado deve registrar revisão do dataset, configuração e ambiente.
