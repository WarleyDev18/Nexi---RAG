# Relatório de QA — Microagente RAG de triagem (Órbita Desk)

**Rodada 1 · 14/10/2026 · commit base `4c64b1e`** · Python 3.13, chromadb + sentence-transformers (`paraphrase-multilingual-MiniLM-L12-v2`)

## Veredito

**Não liberar para uso com cliente real** enquanto BUG-01, BUG-02 e BUG-09 estiverem abertos: hoje uma saída
malformada, com fonte inventada ou prometendo reembolso é roteada como `rascunho_para_revisao` sem nenhuma checagem
determinística. A etapa de recuperação está saudável (recall@4 = 1,00 no golden) e o desenho "rascunho, não resposta
automática" mitiga, mas não substitui as guardas.

## O que foi e o que NÃO foi medido

| Área | Medido | Como |
|---|---|---|
| Integridade da KB e montagem de documentos | sim | `tests/test_kb_integridade.py` |
| Recuperação (filtros, corte, topK, métricas) | sim | golden de 28 tickets (23 `ok` + 5 limitações) + invariantes em 3 planos |
| Geração / roteamento | **só com LLM falso** | `tests/test_triagem_contrato.py` |
| **Qualidade das respostas do LLM real** | **NÃO medido** | sem `ANTHROPIC_API_KEY` no ambiente; rodar `python -m qa.avaliar_geracao` |
| Carga, latência, custo por ticket | não medido | fora do escopo desta rodada |
| PII / LGPD | não testado | README já registra como não tratado |

## Resultado dos testes

`121 testes: 104 passam · 17 xfail (bugs/limitações conhecidos, estritos) · 0 falhas`. Os 6 testes originais continuam verdes.

Recuperação (18 casos `ok` com resposta, 5 de fora de escopo): **recall@4 = 1,00 · MRR = 0,94 · top-1 = 0,89 · fora de escopo 5/5**.
Top-1 falha em 2 casos, ambos com o artigo certo dentro do topK: SLA (kb-015 em 3º, atrás de reembolso e cobrança)
e ticket em inglês (kb-001 em 2º, atrás de kb-002).

## Bugs abertos (todos reproduzidos em teste `xfail(strict)`)

| ID | Sev | Título | Teste |
|---|---|---|---|
| BUG-01 | Crítica | Chave `escalar` ausente na saída do LLM vira **rascunho** (falha aberta) | `test_saida_ruim_do_llm_nunca_chega_ao_cliente[sem-chave-escalar]` |
| BUG-02 | Crítica | Fonte inventada (`kb-999`) é aceita; ninguém checa fontes ⊆ recuperados | `...[fonte-inventada]` |
| BUG-09 | Crítica | "Seu reembolso foi aprovado!" vai para rascunho; regra 4 só existe no prompt | `test_promessa_de_reembolso_nao_chega_ao_cliente` |
| BUG-04 | Alta | LLM devolve JSON que não é objeto (`[1,2,3]`, `"oi"`) → `AttributeError`, ticket se perde | `...[json-lista]`, `...[json-string]` |
| BUG-05 | Alta | Resposta sem conteúdo → `IndexError` em `gerar.py:57` | `...[resposta-sem-conteudo]` |
| BUG-06 | Média | Sem trechos recuperados o LLM é chamado mesmo assim (custo + risco de alucinar); o guarda-corpo só age depois | `test_sem_trechos_nao_deve_nem_chamar_o_llm` |
| BUG-08 | Média | Ticket com `</ticket>` fecha o delimitador e injeta texto fora dele (2 ocorrências no prompt) | `test_ticket_nao_fecha_o_delimitador` |
| BUG-07 | Média | Reindexar não remove artigo apagado de `kb.json` (`upsert` só acrescenta) | `test_reindexar_remove_artigo_que_saiu_da_base` |
| BUG-03 | Média | `categoria`/`prioridade` fora do enum do prompt (`"banana"`) passam | `...[enum-invalido]` |
| BUG-10 | Baixa | Resposta com 151 palavras passa (limite de 120 só no prompt) | `...[mais-de-120-palavras]` |
| BUG-11 | Baixa | Plano desconhecido vaza `KeyError: 'gold'` (`recuperar.py:24`) em vez de erro de validação | `test_plano_invalido_gera_erro_de_validacao` |

**Reprodução rápida de qualquer um:** `pytest --runxfail -k "<trecho do nome>" --tb=short`.

### Detalhe dos três críticos

- **BUG-01** — `src/main.py:27`: `"fila_humana" if resultado.get("escalar") else "rascunho_para_revisao"`. Chave ausente
  → `None` → rascunho. O padrão deveria ser o lado seguro: ausente/ inválido ⇒ humano.
  Observado: `{"categoria":"auth","resposta_sugerida":"x","fontes":["kb-001"]}` → `destino=rascunho_para_revisao`.
- **BUG-02** — `fontes:["kb-999"]` (id inexistente) → `rascunho_para_revisao`. O README (limitação 2) já admite,
  mas o impacto é maior que "alucinação remanescente": a citação é o que dá ao atendente a confiança de aprovar sem ler.
- **BUG-09** — o oráculo detecta a frase (`qa/contrato.py`), o pipeline não. Mesma lógica de BUG-01/02: validação
  determinística pós-LLM (resposta cautelosa não é acusada — ver `test_oraculo_nao_acusa_falso_positivo...`).

> Correção sugerida única para BUG-01/02/03/04/05/09/10: uma função `validar_saida` (o oráculo de `qa/contrato.py` já serve
> de base) chamada em `triar` depois de `gerar`; qualquer violação ⇒ `escalar=True`, `destino=fila_humana`, motivo registrado.

## Limitações conhecidas (README as admite; agora medidas e travadas)

| ID | Caso | Observação medida |
|---|---|---|
| L1 | Free pergunta de SSO (v06) / de automações Pro (v07) | artigo certo é de plano superior e fica filtrado; kb-015 (0,68) / kb-012 (0,55) passam no corte como "relevantes". O sistema não sabe que **existe** resposta bloqueada por plano → sem oportunidade de upsell nem sinal de escalar |
| L2 | Ticket composto (g19: senha + webhook + reembolso) | 1 vetor cobre 1 assunto; só kb-001 vem. kb-010 e kb-006 faltam |
| L3 | Corte frágil (v08) | "Entrar com Google" (artigo descontinuado) recebe kb-002 a **0,69** — 0,01 do corte de 0,70. kb-012 chega a 0,70 exato e ainda passa (`<=`) |
| L4 | Ticket curto/ruidoso (v09: `SENHA!!!!!!!!!!!`) | melhor distância 0,85 → escala sem necessidade (falha segura, mas ruidosa) |

Observação sobre o corte (0,70): 19 trechos com distância entre 0,65 e 0,70 passam no corte, espalhados por 13 dos 28 casos; entre eles há acertos legítimos (kb-005 a 0,65 em "cartão falhou") e ruído (kb-015 a 0,68 em SSO/Slack, kb-002 a 0,69 em "Entrar com Google").
A faixa útil e a de ruído **se sobrepõem** — um único limiar não separa os dois. Não ajuste só o número; considere
reranker, busca híbrida ou checagem de relevância pelo LLM (já listados nos "Próximos passos" do README).

## Pontos positivos verificados

Filtro de plano e de `deprecated` não vazou em nenhum dos 3 planos × 32 tickets (incluindo vazio, emoji, 5.000 caracteres);
resultado determinístico; `upsert` idempotente; JSON inválido/texto livre vai para humano; fora de escopo sempre escala;
`temperature=0` e modelo configurável por `ORBITA_LLM_MODEL` confirmados; `kb.json` consistente (ids únicos, enums e datas válidos).

## Para a próxima rodada

1. Rodar `python -m qa.avaliar_geracao` com chave real e anexar a taxa de violações do modelo (`CONT` × `LEAK`).
2. Ampliar o golden com tickets reais **anonimizados** (hoje todos são escritos por nós: tendem a ser limpos demais).
3. Corrigir BUG-01/02/09 primeiro; ao corrigir, o `xfail` estrito falha avisando para remover a marca.
4. Medir latência e tokens por ticket (a base cabe em ~2 páginas por artigo; confirmar custo do topK=4).
