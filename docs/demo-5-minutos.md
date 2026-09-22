# Roteiro de demonstração em até cinco minutos

## 0:00 a 0:45 — problema e limites

Explique que o laboratório demonstra a camada operacional entre aplicações e provedores de linguagem. O modo padrão usa um provedor determinístico local. Não há SAP, LLM real, serviço pago ou resultado de produção por trás da demonstração.

## 0:45 a 1:30 — arquitetura

Mostre o diagrama do README e destaque quatro fronteiras: autenticação e políticas, adapter do provedor, observabilidade e ferramenta de pedidos somente leitura.

## 1:30 a 2:30 — fluxo controlado

Execute `./scripts/run_demo.sh`. Mostre a correlação `demo-0001`, o modelo autorizado, a indicação de tokens estimados e a resposta determinística. Em seguida, faça uma chamada com modelo não autorizado para mostrar o erro 403 estruturado.

## 2:30 a 3:30 — confiabilidade e observabilidade

Abra `/metrics` ou o Prometheus em `http://localhost:9090`. Explique o timeout total por aplicação, o limite de concorrência, a janela móvel de requisições e os retries apenas para falhas transitórias. Reforce que os contadores são locais ao processo.

## 3:30 a 4:20 — pedidos fictícios

Consulte `PO-100001`. Mostre que a ferramenta aceita apenas um identificador validado e monta uma URL fixa. Não existe endpoint de escrita, aprovação ou URL arbitrária.

## 4:20 a 5:00 — qualidade e próximos passos

Mostre os testes e o resultado da carga local. Termine com as limitações: uma instância, armazenamento em memória, tokenizer aproximado no mock e compatibilidade SAP real não validada.

