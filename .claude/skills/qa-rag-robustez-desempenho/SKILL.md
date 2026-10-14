---
name: qa-rag-robustez-desempenho
description: Testa robustez de entrada (texto vazio, unicode, emoji, caracteres de controle, 100 mil caracteres, fuzz determinístico, CLI) e orçamento de prompt/latência/custo do RAG de triagem. Use ao mudar TOP_K, tamanho de artigo, REGRAS, modelo de embedding, a CLI, ou quando pedirem "e se o ticket for gigante?", "quanto custa por ticket?", "está lento?", "o prompt cresceu?", "testar a CLI". Não use para correção da busca (qa-rag-recuperacao).
---

# QA de robustez e desempenho

**Objetivo:** nenhum texto derruba o fluxo, e custo/latência não degradam sem ninguém perceber. Limites são
**generosos de propósito** (máquinas variam): pegam regressão de ordem de grandeza, não microvariação.

## Comandos

```bash
pytest tests/test_robustez.py tests/test_desempenho.py tests/test_cli.py -q
HF_HUB_OFFLINE=1 pytest tests/test_desempenho.py -q --durations=5      # com modelo em cache, tempos mais honestos
```

## Robustez — o que é garantido

| Garantia | Teste |
|---|---|
| `recuperar` aceita qualquer `str` nos 3 planos (vazio, `\x00`, emoji, 20 mil caracteres, RTL, CJK, SQL, HTML, template, largura total) | `test_recuperar_aceita_qualquer_texto` |
| Fuzz com semente fixa (20261014) nunca levanta exceção | `test_fuzz_recuperar_nunca_levanta_excecao` |
| `triar` SEMPRE devolve `destino` válido para entrada de borda | `test_fuzz_triar_sempre_devolve_destino_valido` |
| 100 mil caracteres terminam em < 20 s e o assunto dos primeiros tokens ainda é achado | `test_ticket_gigante_*` |
| Entrada fora do contrato (plano inválido, ticket não-`str`) ⇒ `ValueError` claro | `test_plano_invalido...`, `test_ticket_que_nao_e_texto...` |
| CLI: `--dry-run` não chama LLM; JSON legível com acento; plano inválido ⇒ exit 2; sem ticket ⇒ uso | `tests/test_cli.py` |

Ao achar uma entrada que quebra: **adicione-a a `BORDA`** em `tests/test_robustez.py` com o sintoma no commit.
Fuzz: para variar, troque a semente numa rodada de exploração, mas deixe a fixa no repositório (reprodutibilidade).

## Desempenho e custo — orçamentos (aproximação 1 token ≈ 3,5 caracteres, sem rede)

| Orçamento | Limite | Por quê |
|---|---|---|
| Prompt de pior caso (REGRAS + 4 maiores artigos + ticket de 2.000 caracteres) | < 2.500 tokens | custo por ticket; hoje ≈ metade disso |
| `len(REGRAS)` | < 2.200 caracteres | cada regra nova paga em TODO ticket |
| `TOP_K` | ≤ 8 | diluição de contexto e custo |
| Maior artigo | < 3× a média | sinal de que precisa de chunking |
| Latência da recuperação aquecida | mediana < 1 s, p95 < 3 s | modelo local MiniLM em CPU |

**Estimativa de custo por ticket:** `tokens_do_prompt × preço_entrada + max_tokens(600) × preço_saída` do modelo em
`config.LLM_MODEL_PADRAO`. Use o preço vigente da tabela do provedor (muda; não fixe número neste repositório).
Rode `qa.avaliar_geracao` com chave e leia `usage` da resposta para o valor real — **não medido** por padrão.

## Procedimento por mudança

| Mudou | Fazer |
|---|---|
| `TOP_K`, `REGRAS`, artigos | `test_desempenho.py`; se o orçamento estourar, decida (subir o limite consciente × reduzir) e registre |
| `EMBEDDING_MODEL` | meça latência aquecida E frio (1ª chamada carrega o modelo: ~15–30 s); documente o cold start |
| volume esperado | latência sob concorrência e carga **não são cobertas** — exigem teste de carga próprio (ver abaixo) |

## Fora do escopo desta suíte (registre como "não medido" nos relatórios)

Concorrência (Chroma `PersistentClient` com vários processos), carga sustentada, memória, cold start no deploy,
latência e limites de taxa da API do LLM, retry/timeout (o código não tem; uma chamada pendurada trava o ticket).

## Armadilhas

- Teste de tempo flaky em CI compartilhado: se oscilar, aumente a folga, não remova o teste.
- Primeira execução inclui download/carga do modelo — não use para medir latência.
- Prompt "cabe" ≠ resposta boa: orçamento é só custo.

## Registrar

Mediana/p95 medidos, tokens do pior caso, e o que ficou sem medição.
