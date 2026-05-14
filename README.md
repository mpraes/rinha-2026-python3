# Rinha de Backend 2026 — Detecção de Fraude com KNN

Implementação em Python 3 da [Rinha de Backend 2026](https://github.com/zanfranh/rinha-2026), um desafio de performance que exige construir uma API de detecção de fraude baseada em busca vetorial.

## Abordagem

A API recebe o payload de uma transação, transforma em um vetor de 14 dimensões normalizadas e busca as 5 transações mais similares no dataset de referência (3 milhões de vetores) usando KNN exato por força bruta. A decisão de aprovar ou negar é baseada na proporção de fraudes entre os vizinhos: se 3 ou mais dos 5 vizinhos são fraude (`fraud_score >= 0.6`), a transação é negada.

### Vetorização

Cada transação é convertida em um vetor de 14 dimensões na ordem definida pelo desafio:

| Índice | Dimensão | Descrição |
|--------|----------|-----------|
| 0 | `amount` | Valor da transação normalizado |
| 1 | `installments` | Parcelas normalizadas |
| 2 | `amount_vs_avg` | Razão valor/média do cliente |
| 3 | `hour_of_day` | Hora do dia (0-23, UTC) |
| 4 | `day_of_week` | Dia da semana (seg=0, dom=6) |
| 5 | `minutes_since_last_tx` | Minutos desde última transação (-1 se nula) |
| 6 | `km_from_last_tx` | Distância da última transação (-1 se nula) |
| 7 | `km_from_home` | Distância de casa |
| 8 | `tx_count_24h` | Transações nas últimas 24h |
| 9 | `is_online` | Terminal online (0 ou 1) |
| 10 | `card_present` | Cartão presente (0 ou 1) |
| 11 | `unknown_merchant` | Comerciante desconhecido (0 ou 1) |
| 12 | `mcc_risk` | Risco do MCC do comerciante |
| 13 | `merchant_avg_amount` | Valor médio do comerciante |

Os valores são normalizados para `[0.0, 1.0]` com clamp. O valor `-1` é usado como sentinela para dados ausentes.

### Busca Vetorial

A busca usa **KNN exato por força bruta** com NumPy:

- **Distância**: Euclidiana (quadrada), calculada via `np.einsum('ij,ij->i', diff, diff)` — elimina a raiz e operações desnecessárias
- **Seleção dos K vizinhos**: `np.argpartition` faz uma ordenação parcial em O(N), colocando os 5 menores nas primeiras posições sem ordenar o array inteiro
- **Dataset**: 3M vetores de 14 dimensões carregados via `np.memmap` — o OS compartilha a memória física entre as instâncias da API

### Arquitetura de Deploy

```
Cliente → Nginx (LB, round-robin) → API 1 (Gunicorn, 1 worker sync)
                                 → API 2 (Gunicorn, 1 worker sync)
```

- **Load balancer**: Nginx com upstream round-robin entre as duas instâncias
- **API**: Falcon + Gunicorn com 1 worker sync — a busca KNN é CPU-bound e vetorizada, então múltiplos workers só adicionariam contenção e context-switching
- **Recursos**: 1 CPU e 350MB de RAM distribuídos entre 3 containers
- **Memória**: `np.memmap` permite que o OS compartilhe as páginas do dataset entre os processos, reduzindo o consumo total de memória

### Pré-processamento em Build Time

Todo o processamento pesado acontece no build do Docker:

1. Download e descompressão do dataset de referência (3M registros)
2. Conversão para arrays binários (`vectors.bin` e `labels.bin`)
3. Geração dos arquivos de normalização e MCC risk
4. Remoção dos arquivos temporários para manter a imagem enxuta

Isso garante que em runtime a API só faz I/O zero e computação vetorizada.

### Degradação Gracios

Qualquer erro interno retorna `{"approved": true, "fraud_score": 0.0}` com HTTP 200. Isso evita o erro HTTP (-5 pontos na pontuação) ao custo de um falso positivo (-1 ponto), que é sempre a troca vantajosa.

## Stack

- **Python 3.12** + **Falcon** (framework web minimalista)
- **NumPy** (operações vetoriais e memmap)
- **Gunicorn** (servidor WSGG, 1 worker sync)
- **Nginx** (load balancer)

## Execução Local

```bash
pip install -r requirements.txt
python src/preprocess.py
gunicorn -b 0.0.0.0:9999 -w 1 src.app:app --worker-class sync
```

## Docker

```bash
docker build -t rinha-api src/
docker run -p 9999:8000 rinha-api
```

## Submissão

A branch `submission` contém apenas os arquivos de deploy: `docker-compose.yml`, `nginx.conf`, `info.json` e `LICENSE`.
