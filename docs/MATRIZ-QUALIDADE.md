# Matriz de cobertura de qualidade — RAG de triagem (Órbita Desk)

Atualizada em **14/10/2026** (rodada 2). Cada risco tem um teste que o pega e um status **medido**. "Cobertura total"
aqui significa: nenhuma dimensão de qualidade sem teste, e testes cuja eficácia foi medida por mutação (não só por linhas).

## Resumo medido

| Medida | Valor |
|---|---|
| Testes | **331** · 325 passam · 6 `xfail` estritos (5 limitações de recuperação + L5 PII) · 0 falhas |
| Cobertura de `src/` e `qa/` (linhas + ramos) | **99%** (`src/` 100%) |
| Teste de mutação | **35/35** mutantes mortos (30 na 1ª execução, 5 sobreviventes viraram testes e morreram) |
| Recuperação (golden, 18 casos com resposta + 5 fora de escopo) | recall@4 = 1,00 · MRR = 0,94 · top-1 = 0,89 · 5/5 fora de escopo |
| Prompt de pior caso | ≈ 1.370 tokens (orçamento 2.500) |
| **LLM real** | **NÃO medido** (sem `ANTHROPIC_API_KEY`) |

## Matriz

Status: ✅ coberto e verde · 🟡 coberto parcialmente / limitação aberta · ⛔ não coberto.

| # | Dimensão | Risco | Teste(s) | Skill | Status |
|---|---|---|---|---|---|
| 1 | Recuperação | Cliente vê artigo de plano superior | `test_plano_so_recupera...`, `test_invariante_plano_nunca_vaza`, `test_rank_dos_planos...` | recuperacao | ✅ |
| 2 | Recuperação | Artigo `deprecated` volta | `test_invariante_deprecated...`, `test_artigo_deprecated_nao_volta...` | recuperacao | ✅ |
| 3 | Recuperação | Perde o artigo certo / traz ruído | golden (23 `ok`), `test_metricas_agregadas_nao_regridem`, fronteira do corte | recuperacao | ✅ |
| 4 | Recuperação | Artigo de plano superior gated ⇒ Free recebe irrelevante (L1) | golden v06, v07 (`xfail`) | recuperacao | 🟡 aberto |
| 5 | Recuperação | Ticket composto cobre 1 assunto (L2) | golden g19 (`xfail`) | recuperacao | 🟡 aberto |
| 6 | Recuperação | Corte frágil 0,69×0,70 (L3); ticket curto escala à toa (L4) | golden v08, v09 (`xfail`) | recuperacao | 🟡 aberto |
| 7 | Geração | Saída malformada / chave ausente / tipo errado vira rascunho | `test_saida_ruim_do_llm_nunca_chega_ao_cliente`, `test_valores_de_tipo_errado...` | geracao | ✅ |
| 8 | Geração | Fonte ou citação inventada | `[fonte-inventada]`, oráculo | geracao | ✅ |
| 9 | Geração | Promessa de reembolso/desconto/exceção | `test_promessa_de_reembolso...`, `test_oraculo_*` | geracao / seguranca | ✅ |
| 10 | Geração | Crash do pipeline (JSON não-objeto, conteúdo vazio) | `[json-lista]`, `[json-string]`, `[resposta-sem-conteudo]` | geracao | ✅ |
| 11 | Geração | Sem contexto ainda chama (e gasta) o LLM | `test_sem_trechos_nao_deve_nem_chamar_o_llm` | geracao | ✅ |
| 12 | Geração | Número inventado na resposta | `test_fundamentacao.py` (oráculo) + `avaliar_geracao` (lente NUM) | geracao | 🟡 só QA, não em produção |
| 13 | Geração | Qualidade/tom do texto | amostragem humana | geracao | ⛔ manual |
| 14 | Base de conhecimento | Artigo mal escrito/ofuscado/duplicado | `test_kb_qualidade.py` (top-1 pelo título, quase-duplicatas) | base-conhecimento | ✅ |
| 15 | Base de conhecimento | PII/segredo na base; conteúdo velho | `test_base_nao_contem_*`, `test_conteudo_ativo_nao_esta_velho` (aviso) | base-conhecimento | ✅ |
| 16 | Base de conhecimento | Fatos contraditórios entre artigos | procedimento manual (`grep` de números) | base-conhecimento | ⛔ manual |
| 17 | Base de conhecimento | Artigo apagado continua no índice | `test_reindexar_remove_artigo...` | recuperacao | ✅ |
| 18 | Segurança | Injeção fecha `</ticket>` ou escapa do delimitador | `test_injecao_fica_presa...` (10 ataques) | seguranca | ✅ |
| 19 | Segurança | Vazamento do prompt de sistema | `test_modelo_que_vaza_as_regras...`, `test_vazou_instrucoes` | seguranca | ✅ |
| 20 | Segurança | Modelo REAL cai na injeção | `qa.avaliar_geracao --so-adversariais` | seguranca | ⛔ requer chave |
| 21 | Segurança | PII do ticket vai ao LLM sem máscara (L5) | `test_dado_pessoal_do_ticket_e_mascarado...` (`xfail`) | seguranca | 🟡 aberto |
| 22 | Segurança | Chave de API versionada; `.env` fora do `.gitignore` | `test_nenhum_segredo_versionado`, `test_env_esta_no_gitignore` | seguranca | ✅ |
| 23 | Robustez | Entrada de borda derruba o fluxo | `test_robustez.py` (26 casos + fuzz com semente) | robustez-desempenho | ✅ |
| 24 | Robustez | CLI: argumentos, exit code, acentos | `test_cli.py` | robustez-desempenho | ✅ |
| 25 | Desempenho | Prompt/custo estoura; latência regride | `test_desempenho.py` | robustez-desempenho | ✅ |
| 26 | Desempenho | Concorrência, carga, cold start, timeout/retry do LLM | — | robustez-desempenho | ⛔ não coberto |
| 27 | Eficácia | Teste verde que não detecta defeito | `qa.mutacao` (35 mutantes) + `test_mutacao.py` + cobertura de ramos | eficacia-testes | ✅ |
| 28 | Eficácia | Ferramenta de QA quebrada dá falso verde | `test_cli.py` (avaliar_*), `test_mutacao.py`, `test_contrato_oraculo.py` | eficacia-testes | ✅ |

## Lacunas que continuam abertas (honestas)

- **⛔ LLM real** (linhas 13, 20): a taxa de violação do modelo, o comportamento sob injeção e a qualidade do texto só
  se medem com `python -m qa.avaliar_geracao` e chave. É a maior lacuna para uma liberação.
- **⛔ Carga/concorrência/timeouts** (26): o código não tem timeout nem retry na chamada ao LLM.
- **🟡 L1–L5**: limitações de desenho (recuperação e PII). Travadas em `xfail` estrito, não resolvidas.
- **⛔ Contradição entre artigos** (16): exige leitura humana; o teste só pega duplicata por vocabulário.
- Dados 100% sintéticos: o golden foi escrito por nós e tende a ser mais limpo que ticket real.
