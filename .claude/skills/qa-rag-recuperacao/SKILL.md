---
name: qa-rag-recuperacao
description: Avalia e testa a etapa de recuperação (retrieval) do RAG de triagem de tickets — recall@K, MRR, top-1, filtros por plano e status, corte de distância, topK, ticket fora de escopo e ticket composto — usando o golden set qa/golden_tickets.json. Use ao mudar data/kb.json, TOP_K, MAX_DISTANCIA, EMBEDDING_MODEL, metadados ou src/recuperar.py/indexar.py, ou quando pedirem "testar a busca", "avaliar a recuperação", "o corte 0,70 ainda vale?", "adicionar ticket ao golden", "o artigo novo apareceu?". Não use para qualidade do texto gerado (qa-rag-geracao) nem da base em si (qa-rag-base-conhecimento).
---

# QA da recuperação

**Objetivo:** garantir que o LLM só recebe o contexto certo, do plano certo, e nada quando não há resposta.
O erro aqui não se corrige depois — o modelo responde com o que recebeu. Nenhum comando abaixo gasta token de LLM.

## Comandos

```bash
python -m qa.avaliar_recuperacao                 # relatório; exit 1 só se um caso 'ok' regredir
python -m qa.avaliar_recuperacao --json > antes.json   # snapshot para comparar antes/depois de uma mudança
pytest tests/test_recuperacao_golden.py -q -rxX
```
Primeira execução carrega o modelo de embedding (~30–40 s). Com o modelo já em cache use `HF_HUB_OFFLINE=1`
(evita esperar timeouts de rede).

## Critérios de aprovação (referência de 14/10/2026: 18 casos com resposta + 5 fora de escopo)

| Métrica / invariante | Piso | Medido | Onde falha |
|---|---|---|---|
| Plano nunca vaza (`min_plan_rank <= plano`) | **100%** | 100% | `test_invariante_plano_nunca_vaza` |
| `deprecated` nunca recuperado | **100%** | 100% | `test_invariante_deprecated_nunca_recuperado` |
| ≤ TOP_K resultados, todos ≤ corte, ordenados | **100%** | 100% | `test_invariante_corte_e_topk_respeitados` |
| recall@4 (todo artigo esperado no topK) | ≥ 0,95 | 1,00 | `test_metricas_agregadas_nao_regridem` |
| MRR | ≥ 0,85 | 0,94 | idem |
| top-1 | ≥ 0,80 | 0,89 | idem |
| Fora de escopo devolve vazio | 100% dos `ok` | 5/5 | `test_golden_caso[v01..v05]` |
| Folga do corte nos fora-de-escopo clássicos | ≥ corte + 0,05 | 0,81 e 0,91 | `test_fora_de_escopo_tem_folga...` |

Invariantes valem para QUALQUER ticket e plano — violação é **severidade crítica** (cliente Free recebendo recurso
Enterprise). Métricas agregadas são pisos com folga para ruído do modelo, não metas.
**recall@K pesa mais que top-1:** o LLM lê os K trechos, não só o primeiro.

## Procedimento por tipo de mudança

| Mudou | Risco | Fazer |
|---|---|---|
| `data/kb.json` | artigo novo "rouba" o top-1 de outro; metadado inválido quebra o upsert | `qa-rag-base-conhecimento` + adicione 1–2 tickets ao golden que DEVEM achar o artigo novo; rode `--json` e compare |
| `MAX_DISTANCIA` / `TOP_K` | recall × ruído | `--json` antes e depois. Reporte os DOIS lados: casos `ok` que perderam artigo × `limitacao_conhecida` que passaram a vazar. Nunca ajuste olhando 1 caso |
| `EMBEDDING_MODEL` | vetores incompatíveis; escala das distâncias muda | apague `.chroma/`, reindexe, **recalibre o corte** e revise os pisos de forma consciente (registre no relatório) |
| filtros / metadados | vazamento por plano/status | invariantes; `pytest -k invariante` |

## Como adicionar um caso ao golden (`qa/golden_tickets.json`)

`{"id","ticket","plano","esperado":["kb-xxx"],"status":"ok","nota":"..."}`
- `esperado: []` = deve vir **vazio**; registre a distância medida na `nota`.
- Defeito já conhecido → `status:"limitacao_conhecida"` + `nota` com o porquê (vira `xfail(strict)`).
- Escreva como o cliente escreve: sem acento, com erro de digitação, em inglês, curto, composto. Tickets limpos
  inflam o recall.
- Cubra cada combinação plano × artigo restrito (Free perguntando de recurso Pro/Enterprise é o caso mais perigoso).
- `test_golden_referencia_apenas_ids_existentes` impede apontar para artigo que não existe.

## Limitações conhecidas (xfail estrito — NÃO são bugs novos)

L1 artigo certo gated por plano → Free recebe artigo irrelevante; L2 ticket composto cobre 1 assunto; L3 corte frágil
(0,69 vs 0,70); L4 ticket curto/ruidoso escala sem necessidade. Se um deles PASSAR, o xfail estrito falha de
propósito: melhorou de verdade → mude `status` para `ok` e registre no `docs/QA-RELATORIO.md`.

## Armadilhas

- "Passou no corte" ≠ "é relevante": a distância mede vocabulário, não utilidade. Invariantes verdes não provam
  qualidade; olhe os trechos devolvidos nos casos novos.
- A faixa 0,65–0,70 mistura acerto legítimo e ruído (19 trechos em 13 casos no golden): um único limiar não separa.
- Amostra pequena = falsa segurança. Calibrar com ≥ 30 tickets antes de mexer no corte; hoje são 28.
- `xfail` que falha por motivo errado parece "bug conhecido". Confirme com `pytest --runxfail <teste> --tb=short`.
- Teste de recuperação depende do modelo de embedding: troca de versão do `sentence-transformers` pode mover distâncias.
  Se métricas mudarem sem mudança sua, fixe a versão e registre.

## Registrar

Data, commit, métricas (`recall@K`, MRR, top-1), casos que mudaram de lado e a comparação antes/depois.
