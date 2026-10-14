---
name: qa-rag-geracao
description: Testa a geração e o roteamento do microagente RAG de triagem (src/gerar.py, src/main.py) — contrato do JSON, enums, fontes citadas ⊆ recuperadas, escalonamento, promessa de reembolso, prompt injection e falhas do LLM — com LLM falso (grátis, determinístico) e, quando houver chave, com o LLM real. Use ao mexer no prompt (REGRAS), no parsing, no guarda-corpo do main.py, no modelo, ou quando pedirem "testar a resposta", "validar o JSON", "o agente alucina?", "testar prompt injection", "avaliar com a API".
---

# QA da geração e do roteamento (RAG Órbita Desk)

Princípio: **prompt não é garantia**. Regra que só existe em `REGRAS` não está testada. A suíte verifica, fora do
LLM, o que `triar()` deixa chegar ao cliente.

## A propriedade central

> O resultado de `triar` ou vai para `fila_humana`, ou cumpre o contrato inteiro.

Implementada em `src/validar.py` (reexportada por `qa/contrato.py`) e usada em produção por `triar` (`seguro_para_propagar`, `validar_saida`). O contrato exige: JSON objeto; chaves
`categoria, prioridade, escalar, resposta_sugerida, fontes`; enums do prompt; `escalar` booleano; fontes e citações
`[kb-xxx]` ⊆ ids realmente recuperados; resposta com fonte quando não escala; ≤ 120 palavras; sem promessa de
reembolso/desconto/exceção; `destino` coerente com `escalar`.

## Rodar

```bash
pytest tests/test_contrato_oraculo.py tests/test_triagem_contrato.py -q -rxX     # LLM falso, 0 token
ANTHROPIC_API_KEY=... python -m qa.avaliar_geracao                              # LLM real, ~35 chamadas
ANTHROPIC_API_KEY=... python -m qa.avaliar_geracao --so-adversariais --saida out.json
```
Sem `ANTHROPIC_API_KEY`, **diga explicitamente que a qualidade das respostas reais não foi medida** — foi assim
que o README original ficou (limitação 4). Nunca apresente teste com LLM falso como prova de qualidade do modelo.

## Como o teste com LLM falso funciona

Fixture `llm_falso` (tests/conftest.py) troca o SDK `anthropic` e devolve o que o teste mandar:
`llm_falso.responder(dict | str | None)`; conta `chamadas`, guarda `prompts` e `kwargs` (modelo, temperatura).
`saida_valida(**campos)` gera a saída perfeita; **estrague um campo por vez**, para cada caso violar uma regra só.

Checagem obrigatória ao criar um `xfail`: rode `pytest --runxfail -k <caso> --tb=line` e confirme que a mensagem
é exatamente a do bug. (Já aconteceu de a saída-base violar outra regra e o xfail passar por motivo errado.)

## Quando o resultado do LLM real violar o contrato

Classifique cada linha de `avaliar_geracao`:
- `CONT` — o modelo violou, mas `triar` mandou ao humano. Sistema funcionou; registre a taxa do modelo.
- `LEAK` — violação que chegaria ao cliente, ou crash. **É bug do pipeline**, não do modelo: abra no
  `docs/QA-RELATORIO.md` e transforme num teste com LLM falso reproduzindo a saída exata (guarde o texto bruto).
- Avalie à mão, por amostra, o que o oráculo não vê: tom, correção do conteúdo, resposta "plausível mas sem
  suporte no artigo". Citar `[kb-001]` não prova que o artigo sustenta a frase.

## Checklist por mudança

| Mudou | Conferir |
|---|---|
| `REGRAS` (prompt) | `test_enums_do_contrato_batem_com_o_prompt`; reexecute `avaliar_geracao --so-adversariais` |
| parsing de `gerar()` | saída em cerca de código, texto livre, lista, string, conteúdo vazio, JSON truncado |
| `main.triar` | fail-open (chave ausente → deve escalar), escalar não booleano, caminho sem trechos |
| modelo / temperatura | `test_chamada_ao_llm_usa_temperatura_zero...`; rode a bateria real e compare violações |
| delimitadores do ticket | ticket contendo `</ticket>`, "ignore as regras", pedido de reembolso sob pressão |

## Armadilhas

- Escalar **no lado seguro**: dado faltando, ambíguo ou inválido → `fila_humana`. Nunca `rascunho`.
- Guarda-corpo que só roda *depois* do LLM não evita o gasto nem a alucinação (foi o BUG-06: sem trechos o modelo ainda era chamado — hoje `triar` curto-circuita).
- O validador de promessa de reembolso (`src/validar.py`) é uma regex: valide-o nos dois sentidos (`test_oraculo_*`). Resposta cautelosa
  ("a equipe financeira decide") não pode ser acusada — falso positivo faz o time ignorar o alerta.
- Dados: tickets reais contêm PII. O golden usa só texto fictício; não cole ticket real em testes ou relatórios.
