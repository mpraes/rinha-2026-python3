# Rinha de Backend 2026 - Python

A Rinha de Backend e um desafio de performance com limite rigido de CPU e memoria.
O objetivo aqui e simples: responder rapido, errar pouco e nao cair sob carga.

## Abordagem (o que importa)

Em vez de rodar KNN exato em runtime sobre 3M vetores, este projeto move custo pesado para build time e deixa o request path o mais curto possivel.

Resumo da estrategia:

- Build time: treina um modelo linear (SGDClassifier log loss) e salva apenas `coef` e `intercept` em `resources/model.json`.
- Runtime: extrai 14 features escalares, calcula um produto linear desenrolado e aplica sigmoid estavel numericamente.
- Decisao: `approved = fraud_score < 0.6` (configuravel por `FRAUD_THRESHOLD`).

Por que essa abordagem:

- Menor latencia p99: troca busca O(N) por inferencia O(14).
- Menor pressao de CPU: sem operacoes vetoriais pesadas no hot path.
- Menor risco de timeout: caminho de execucao curto e deterministico.
- Melhor custo-beneficio para o score da Rinha: reduz HTTP errors e fila sob burst.

## Detalhes de implementacao

### 1. Hot path sem overhead evitavel

- Parse de data com slicing de string ISO (sem `datetime.fromisoformat`).
- Calculo de dia da semana e minutos por aritmetica civil.
- Multiplicacao por reciprocals precomputados (evita divisoes repetidas).
- Resposta em bytes (`resp.data`) e `orjson` quando disponivel.

### 2. Treino offline e inferencia online

- `src/preprocess.py` baixa dataset oficial e arquivos auxiliares.
- Treina `SGDClassifier(loss="log_loss")` com `class_weight` para custo assimetrico.
- Persistencia minimalista do modelo em JSON para carregamento rapido.

### 3. Tolerancia a falha orientada a pontuacao

Qualquer excecao interna retorna HTTP 200 com payload seguro:

```json
{"approved": true, "fraud_score": 0.0}
```

Na Rinha, isso costuma ser melhor que HTTP error (penalidade maior no score).

## Arquitetura de deploy

```text
Cliente -> Nginx (LB) -> API 1 (Granian WSGI)
                    -> API 2 (Granian WSGI)
```

- Nginx faz round-robin entre duas instancias.
- API roda com Granian em modo WSGI.
- Config principal atual: `workers=2`, `blocking-threads=1` por container.
- Limites respeitados: stack total em 1 CPU e 350MB.

## Stack

- Python 3.12
- Falcon
- Granian
- orjson (com fallback para `json`)
- scikit-learn (apenas no build)
- uv (gestao de dependencias)

## Rodando local

```bash
uv sync --frozen --no-dev
python src/preprocess.py
granian --interface wsgi --host 0.0.0.0 --port 9999 --workers 2 --blocking-threads 1 src.app:app
```

## Docker

```bash
docker buildx build --platform linux/amd64 -f src/Dockerfile -t rinha-api:local .
API_IMAGE=rinha-api:local docker compose up -d
```
