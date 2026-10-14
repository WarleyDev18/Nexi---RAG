---
name: qa-rag-relatorio
description: Executa a bateria completa de QA do microagente RAG de triagem (testes, métricas de recuperação, avaliação opcional com LLM real), classifica os achados por severidade e atualiza docs/QA-RELATORIO.md. Use quando pedirem "rodar o QA", "fechar a rodada de testes", "relatório de QA", "o que está quebrado?", "está pronto para release?", ou depois de qualquer correção de bug para atualizar o status.
---

# Rodada de QA e relatório (RAG Órbita Desk)

## 1. Executar (nesta ordem; pare e relate se o passo 1 falhar)

```bash
python -m pytest -q -rxXfE                      # passed / xfailed (bugs conhecidos) / FAILED (regressão) / XPASS (bug corrigido!)
python -m qa.avaliar_recuperacao                # recall@K, MRR, top-1, fora-de-escopo
ANTHROPIC_API_KEY=... python -m qa.avaliar_geracao   # só se houver chave; senão registre "não medido"
```

Interpretação dos resultados do pytest:
- `FAILED` = regressão nova → severidade alta até provar o contrário. Investigue antes de relatar.
- `XFAIL` = bug conhecido, ainda aberto. Não é falha, mas **conta no relatório como aberto**.
- `XPASS(strict)` aparece como FAILED com "XPASS": o bug foi corrigido. Remova a marca `xfail`, mova o item para
  "Corrigidos" no relatório (com o commit) e, se for limitação do golden, mude `status` para `ok`.
- Verde total com muitos `xfail` **não** é "tudo bem": reporte "N passam, M bugs abertos" sempre juntos.

## 2. Severidade (use estes critérios, não intuição)

| Sev | Critério | Exemplos (rodada 1, hoje corrigidos) |
|---|---|---|
| Crítica | Conteúdo incorreto/prometido chega ao cliente sem humano; vazamento entre planos | promessa de reembolso (BUG-09), fonte inventada (BUG-02), fail-open (BUG-01) |
| Alta | O pipeline derruba ou perde ticket | JSON não-objeto / conteúdo vazio (BUG-04/05) |
| Média | Custo, segurança em profundidade, dado velho | LLM chamado sem contexto (BUG-06), `</ticket>` (BUG-08), índice fantasma (BUG-07), enum (BUG-03) |
| Baixa | Erro pouco informativo, regra de estilo | plano inválido (BUG-11), >120 palavras (BUG-10) |

Probabilidade importa para priorizar, severidade não muda por ela: um bug crítico raro continua crítico.

## 3. Formato de cada achado (em `docs/QA-RELATORIO.md`)

`BUG-NN · Severidade · Título curto` + **Reprodução** (comando ou teste exato) + **Esperado** × **Observado** +
**Evidência** (saída literal, distâncias, traceback com arquivo:linha) + **Teste** (nome do xfail) + **Sugestão**.
Um achado sem reprodução executável não entra como bug — entra como "hipótese a verificar".

## 4. Regras do relatório

- Números só de execução desta rodada, com data. Nunca copie a métrica da rodada anterior.
- Separe **medido** de **não medido** (ex.: LLM real sem chave). Liste o que ficou de fora e por quê.
- Distinga **bug** (contrato/README prometido e quebrado) de **limitação conhecida** (README admite) de
  **melhoria** (não estava prometido). Misturar infla a contagem e desacredita o relatório.
- Veredito final em uma frase com a condição: "Não liberar para uso com cliente enquanto BUG-01/02/09 estiverem abertos".
- Não corrija código de produção durante a rodada de QA sem pedido explícito: relate, o dono decide.
