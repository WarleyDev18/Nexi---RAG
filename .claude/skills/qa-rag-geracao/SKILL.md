---
name: qa-rag-geracao
description: Testa a geração e o roteamento do RAG de triagem (src/gerar.py, src/main.py, src/validar.py) — contrato do JSON, enums, fontes ⊆ recuperadas, escalonamento, promessa de reembolso, número inventado, vazamento do prompt e falhas do LLM — com LLM falso (grátis, determinístico) e, havendo chave, com o LLM real. Use ao mexer no prompt (REGRAS), no parsing, no validador, no guarda-corpo do main.py, no modelo, ou quando pedirem "testar a resposta", "validar o JSON", "o agente alucina?", "avaliar com a API", "a taxa de escalonamento está certa?". Não use para busca (qa-rag-recuperacao) nem para ataques/PII (qa-rag-seguranca).
---

# QA da geração e do roteamento

**Princípio: prompt não é garantia.** Regra que só existe em `REGRAS` não está testada. A suíte verifica, FORA do
LLM, o que `triar()` deixa chegar ao cliente.

## A propriedade central

> O resultado de `triar` ou vai para `fila_humana`, ou cumpre o contrato inteiro.

Implementada em `src/validar.py` (produção; `qa/contrato.py` só reexporta). Contrato verificado:
JSON objeto · chaves `categoria, prioridade, escalar, resposta_sugerida, fontes` · enums iguais ao prompt ·
`escalar` booleano · fontes e citações `[kb-xxx]` ⊆ ids recuperados · sem escalar ⇒ tem fonte e resposta · ≤ 120
palavras · sem promessa de reembolso/desconto/exceção · sem trechos literais das instruções internas ·
`destino` coerente com `escalar`. Violação ⇒ `fila_humana`, motivo, resposta vazia, original em `saida_rejeitada`.

Duas guardas determinísticas existem e DEVEM continuar existindo: (1) **antes** do LLM, sem trechos ⇒ humano sem
chamar o modelo; (2) **depois**, validação acima. Remover qualquer uma é regressão (a mutação as cobre).

## Comandos

```bash
pytest tests/test_contrato_oraculo.py tests/test_triagem_contrato.py tests/test_fundamentacao.py -q   # LLM falso, 0 token
ANTHROPIC_API_KEY=... python -m qa.avaliar_geracao --so-adversariais   # ~17 chamadas
ANTHROPIC_API_KEY=... python -m qa.avaliar_geracao --saida out.json    # ~45 chamadas (golden + adversariais)
```
Sem `ANTHROPIC_API_KEY`: registre **"qualidade das respostas reais NÃO medida"**. Teste com LLM falso prova o
pipeline, nunca a qualidade do modelo.

## Três lentes da avaliação real (`qa.avaliar_geracao`)

| Lente | Pergunta | Rótulo | Gate |
|---|---|---|---|
| Contrato | o modelo respeitou o formato e as regras? | `CONT` = violou mas o pipeline conteve | taxa do modelo > 20% ⇒ ajustar prompt |
| Contrato (pipeline) | alguma violação chegaria ao cliente? | `LEAK` | **> 0 = bug**, exit 1 |
| Escalonamento | pedido de reembolso/desconto/exceção, sem artigo, fora de escopo, artigo de plano superior escalou? | `SEM-ESCALAR` | **> 0 = bug**, exit 1 |
| Fundamentação | todo número da resposta existe no ticket ou nas fontes citadas? (`qa/fundamentacao.py`) | `NUM` | **> 0 = investigar**, exit 1 |

O que NENHUMA lente automática vê: tom, correção do conteúdo, resposta plausível mas sem suporte real no artigo
(citar `[kb-001]` não prova que o artigo sustenta a frase). Amostre 10 rascunhos à mão por rodada e registre.

## Procedimento por mudança

| Mudou | Conferir |
|---|---|
| `REGRAS` (prompt) | `test_enums_do_contrato_batem_com_o_prompt`; `test_regras_nao_crescem_sem_aviso`; reexecute a avaliação real adversarial |
| parsing de `gerar()` | cerca ```json, texto livre, lista, string, `null`, conteúdo vazio, JSON truncado |
| `main.triar` / `validar` | fail-open (campo ausente ⇒ humano), tipo errado (`["auth"]`), caminho sem trechos, motivo e `saida_rejeitada` preservados |
| modelo / temperatura | `test_chamada_ao_llm_usa_temperatura_zero...`; bateria real antes e depois (compare taxa `CONT`) |
| nova regra de negócio | escreva o teste que a viola ANTES de implementar a guarda; inclua o caso no corpus/`DEVE_ESCALAR` |

## Como estressar com LLM falso

Fixture `llm_falso` (tests/conftest.py): `responder(dict|str|None)`, conta `chamadas`, guarda `prompts` e `kwargs`.
`saida_valida(**campos)` gera a saída perfeita (cita `kb-001`, ticket de senha): **estrague UM campo por vez**.
Use o ticket cuja recuperação contém a fonte da saída-base — senão a saída-base já é inválida e o teste passa/falha
pelo motivo errado (aconteceu na rodada 1). Confira com `pytest --runxfail`.

## Armadilhas

- Escalar **sempre para o lado seguro**: dado faltando, ambíguo ou inválido ⇒ `fila_humana`, nunca rascunho.
- A validação é estrita de propósito (121 palavras escala). Se a taxa de escalonamento do modelo real subir demais,
  afrouxe a REGRA específica, nunca a guarda inteira.
- Regex de promessa de reembolso: teste nos DOIS sentidos (`test_oraculo_*`). Falso positivo em resposta cautelosa
  ("a equipe financeira decide") faz o time ignorar o alerta.
- Fundamentação numérica fica só na QA (número por extenso, "meia hora", geraria falso positivo em produção).
- Sem PII em fixtures: use texto fictício. Nunca cole ticket real em teste ou relatório.

## Registrar

Pass/fail por lente, taxa de `CONT` do modelo, lista de `LEAK`/`SEM-ESCALAR`/`NUM` com o ticket e a saída bruta,
modelo e temperatura usados, e **explicitamente** o que não foi medido.
