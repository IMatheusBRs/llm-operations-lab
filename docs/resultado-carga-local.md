# Resultado do teste de carga local

Execução real realizada em 22 de setembro de 2026 às 00:06 UTC, usando o servidor Uvicorn local e o provedor mock determinístico.

## Ambiente e parâmetros

- Python 3.13.14
- Linux 7.0.0-31-generic x86_64 com glibc 2.43
- URL local `http://127.0.0.1:8000`
- 20 requisições
- concorrência 2
- credencial fictícia `demo-app`
- modelo `mock-echo`

## Resultado observado

- 20 respostas HTTP 200
- duração total de 0,0239 segundo
- vazão observada de 835,82 requisições por segundo
- latência mínima de 1,099 ms
- latência média de 1,904 ms
- percentil 95 de 2,904 ms
- latência máxima de 11,331 ms

Os dados brutos estão em `load-results/local-python-3.13.json`.

## Limitação da medição

Este resultado mede apenas uma execução curta da API local com regras determinísticas e sem rede externa. Não mede um LLM, não representa capacidade sustentada, não deve ser extrapolado para produção e pode variar conforme máquina, runtime e processos concorrentes.

