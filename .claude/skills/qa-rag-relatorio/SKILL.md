---
name: qa-rag-relatorio
description: Orquestra uma rodada completa de QA do RAG de triagem — executa todas as dimensões (recuperação, geração, base de conhecimento, segurança, robustez/desempenho, eficácia dos testes), preenche a matriz de cobertura de qualidade, classifica achados por severidade e atualiza docs/QA-RELATORIO.md e docs/MATRIZ-QUALIDADE.md. Use quando pedirem "rodar o QA completo", "fechar a rodada", "relatório de QA", "está pronto para release?", "o que está quebrado/sem cobertura?", ou depois de corrigir bugs para atualizar o status. Para uma área isolada use a skill daquela área.
---

# Rodada de QA e relatório (orquestrador)

## 1. Matriz de cobertura de qualidade — o que "cobertura total" significa aqui

Seis dimensões. Uma rodada só está **completa** quando cada linha tem status medido ou "não medido" com motivo.

| Dimensão | Skill | Comando | Gate |
|---|---|---|---|
| Recuperação | `qa-rag-recuperacao` | `python -m qa.avaliar_recuperacao` | invariantes 100%; recall@4 ≥ 0,95 |
| Geração e roteamento | `qa-rag-geracao` | `pytest tests/test_triagem_contrato.py tests/test_contrato_oraculo.py tests/test_fundamentacao.py` | 0 falhas |
| Base de conhecimento | `qa-rag-base-conhecimento` | `pytest tests/test_kb_*.py` | 0 falhas; avisos de frescor listados |
| Segurança | `qa-rag-seguranca` | `pytest tests/test_seguranca.py` | 0 falhas; L5 (PII) declarada |
| Robustez e desempenho | `qa-rag-robustez-desempenho` | `pytest tests/test_robustez.py tests/test_desempenho.py tests/test_cli.py` | 0 falhas |
| Eficácia dos testes | `qa-rag-eficacia-testes` | `pytest --cov=src --cov=qa --cov-branch` + `python -m qa.mutacao` | ramos ≥ 95%; mutação 100% dos não equivalentes |
| **LLM real** (transversal) | `qa-rag-geracao` / `-seguranca` | `ANTHROPIC_API_KEY=... python -m qa.avaliar_geracao` | `LEAK` = 0, `SEM-ESCALAR` = 0, `NUM` = 0 |

Mapa completo risco → teste → status em [`docs/MATRIZ-QUALIDADE.md`](../../../docs/MATRIZ-QUALIDADE.md).

## 2. Executar (nesta ordem; pare e relate se o passo 1 falhar)

```bash
HF_HUB_OFFLINE=1 pytest -q -rxXfEw -p no:cacheprovider --cov=src --cov=qa --cov-branch --cov-report=term-missing
python -m qa.avaliar_recuperacao
python -m qa.mutacao --saida mut.json          # antes de release ou depois de mudar guardas (~25 min)
ANTHROPIC_API_KEY=... python -m qa.avaliar_geracao --saida geracao.json     # só com chave
```
Rode a suíte 2× se algo oscilar: teste que não é determinístico é achado por si só.

Leitura do pytest:
- `FAILED` = regressão → severidade alta até provar o contrário; investigue antes de relatar.
- `XFAIL` = limitação/bug **aberto**; entra no relatório como aberto, ao lado do total de passes.
- `XPASS(strict)` aparece como FAILED: o problema foi resolvido. Remova a marca, mova o item para "Corrigidos"
  com o commit e, se for caso do golden, mude `status` para `ok`.
- Verde com `xfail` NÃO é "tudo bem": reporte sempre "N passam, M abertos" juntos.

## 3. Severidade (critérios, não intuição)

| Sev | Critério | Exemplos reais da rodada 1–2 |
|---|---|---|
| Crítica | conteúdo errado/prometido chega ao cliente sem humano; vazamento entre planos; dado pessoal exposto | promessa de reembolso, fonte inventada, chave `escalar` ausente virando rascunho |
| Alta | o pipeline derruba ou perde ticket; regressão numa invariante | JSON não-objeto, conteúdo vazio |
| Média | custo, defesa em profundidade, dado velho, vazamento do prompt | LLM chamado sem contexto, `</ticket>`, índice fantasma, vazamento das instruções |
| Baixa | erro pouco informativo, estilo | plano inválido, >120 palavras |

Probabilidade ordena a fila; **não** reduz a severidade.

## 4. Formato de achado

`BUG-NN · Sev · título` + **Reprodução** (comando ou teste exato) + **Esperado × Observado** + **Evidência**
(saída literal, distâncias, traceback `arquivo:linha`) + **Teste** (nome) + **Sugestão**. Sem reprodução executável
não é bug: é "hipótese a verificar".

## 5. Regras do relatório

- Números só desta rodada, com data e commit. Nunca reaproveite métrica anterior.
- Separe **medido** × **não medido** com o motivo (ex.: "LLM real: sem chave"; "carga: fora do escopo").
- Distinga **bug** (prometido e quebrado) × **limitação conhecida** (README admite) × **melhoria** (não prometido).
- Corrigiu um bug? O teste dele vira regressão normal, o mutante correspondente é adicionado (`qa-rag-eficacia-testes`)
  e o item vai para "Corrigidos". Bug corrigido sem teste de regressão não está corrigido.
- Veredito em uma frase com condição: "Não liberar para cliente real enquanto <X> estiver aberto / <Y> não medido".
- **Não corrija código de produção durante a rodada sem pedido explícito:** relate, o dono decide.
- Nada de PII, ticket real ou chave em relatório.

## 6. Critério de "pronto para liberar"

Todas as linhas da matriz verdes **e** LLM real medido **e** limitações abertas aceitas por escrito pelo dono do
produto (L1–L5). Faltando qualquer um, o veredito é "não medido/não liberar", nunca "ok com ressalvas" vago.
