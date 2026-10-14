---
name: qa-rag-recuperacao
description: Testa a etapa de recuperação (retrieval) do microagente RAG de triagem de tickets — recall@K, MRR, filtros por plano/status, corte de distância e artigos fora de escopo — usando o golden set em qa/golden_tickets.json. Use sempre que mudar kb.json, TOP_K, MAX_DISTANCIA, o modelo de embedding, os metadados ou src/recuperar.py/indexar.py, ou quando pedirem "testar a busca", "avaliar a recuperação", "o corte 0,70 ainda vale?", "adicionar ticket ao golden".
---

# QA da recuperação (RAG Órbita Desk)

A recuperação decide o que o LLM pode saber. Erro aqui não se corrige depois: o modelo responde com o que recebeu.
Nada abaixo chama LLM nem gasta token.

## Rodar

```bash
python -m qa.avaliar_recuperacao            # relatório legível; exit 1 só se um caso 'ok' regredir
python -m qa.avaliar_recuperacao --json     # para comparar antes/depois de uma mudança
pytest tests/test_recuperacao_golden.py tests/test_kb_integridade.py -q
```
Primeira execução baixa/carrega o modelo de embedding (~40 s). Depois de baixado, `HF_HUB_OFFLINE=1` evita
esperar timeouts de rede.

## O que olhar (nesta ordem)

1. **Invariantes de segurança** (`test_invariante_*`) — valem para QUALQUER ticket, são inegociáveis:
   plano nunca vaza (`min_plan_rank <= plano`), `deprecated` nunca volta, ≤ TOP_K resultados, todos ≤ corte, ordenados.
   Uma falha aqui é severidade alta: o cliente Free pode receber promessa de recurso Enterprise.
2. **Regressão do golden** — casos `status:"ok"` precisam achar os artigos esperados dentro do topK.
   Métricas de referência (14/10/2026, 18 casos): recall@4 = 1,00 · MRR = 0,94 · top-1 = 0,89 · fora de escopo 5/5.
   Para busca, **recall@K importa mais que top-1**: o LLM lê os K trechos, não só o primeiro.
3. **Folga do corte** — o melhor acerto de um fora-de-escopo clássico deve estar ≥ corte+0,05. Hoje: 0,81 e 0,91 (ok),
   mas casos reais já caem em 0,68–0,69 (v06, v08). Qualquer ajuste de MAX_DISTANCIA tem que reportar o impacto
   nos dois lados: quantos `ok` perdem artigo (recall↓) × quantos `limitacao_conhecida` passam a vazar ruído.
4. **Limitações conhecidas** (`status:"limitacao_conhecida"`) — são `xfail(strict)`. Se passarem, o teste FALHA de
   propósito: melhorou de verdade → mude o `status` para `ok` e registre no `docs/QA-RELATORIO.md`.

## Ao mudar algo, o que reexecutar

| Mudou | Risco | Fazer |
|---|---|---|
| `data/kb.json` (artigo novo/editado) | artigo novo "rouba" o top-1 de outros; metadado inválido quebra o upsert | `test_kb_integridade` + golden; adicione 1–2 tickets que DEVEM achar o artigo novo |
| `MAX_DISTANCIA` / `TOP_K` | recall × ruído | rode `--json` antes e depois e compare; nunca ajuste olhando 1 caso |
| `EMBEDDING_MODEL` | todos os vetores ficam incompatíveis; distâncias mudam de escala | apague `.chroma/`, reindexe, **recalibre o corte** — os pisos de `test_metricas_agregadas_nao_regridem` podem precisar de revisão consciente |
| filtros / metadados | vazamento por plano/status | invariantes acima |

## Como adicionar um caso ao golden

Edite `qa/golden_tickets.json`: `{"id","ticket","plano","esperado":["kb-xxx"],"status":"ok","nota":"..."}`.
- `esperado: []` = deve vir **vazio** (fora de escopo ou sem artigo). Escreva a `nota` com a distância medida.
- Caso novo que você já sabe que falha → `status:"limitacao_conhecida"` + `nota` explicando o porquê.
- Prefira tickets **como o cliente escreve**: sem acento, com erro, em inglês, curtos, compostos. Tickets limpos
  demais inflam o recall e escondem o problema.
- Cubra cada combinação plano × artigo restrito (um Free perguntando de recurso Pro/Enterprise é o caso mais perigoso).

## Armadilhas (já aconteceram)

- Calibrar o corte em poucos exemplos: o README admite 8; o golden tem 18+9. Amostra pequena = falsa segurança.
- "Passou no corte" ≠ "é relevante": kb-015 (SLA) a 0,68 é entregue a quem perguntou de SSO. A distância mede
  proximidade de vocabulário, não utilidade. Não declare "recuperação OK" só porque os invariantes passaram.
- `upsert` não apaga: artigo removido do `kb.json` continua recuperável (BUG-07). Ao remover artigo, apague `.chroma/`.
- Um teste `xfail` que falha por motivo errado (import, fixture) parece "bug conhecido". Confira com
  `pytest --runxfail <teste>` que a mensagem de erro é a do bug declarado.
