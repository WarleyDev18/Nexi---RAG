---
name: qa-rag-base-conhecimento
description: Audita a qualidade da base de conhecimento do RAG (data/kb.json) — artigo achável pelo próprio título, ofuscamento entre artigos, duplicatas, contradições, deprecated, dado pessoal e segredo na base, frescor — e valida artigo novo ou editado antes de indexar. Use ao adicionar/editar/remover artigo, mudar metadados, reindexar, ou quando pedirem "revisar a base", "esse artigo novo está bom?", "tem artigo duplicado/velho?", "o RAG responde com informação desatualizada". Não use para métricas de busca em tickets (qa-rag-recuperacao).
---

# QA da base de conhecimento

**Objetivo:** o RAG só é tão correto quanto os artigos. Erro de conteúdo vira resposta errada **com citação**, que
parece verificada. Esta skill testa a base como dado, não o código.

## Comandos

```bash
pytest tests/test_kb_integridade.py tests/test_kb_qualidade.py -q -rxXw    # formato + qualidade; -w mostra avisos de frescor
```

## Critérios de aprovação (todos obrigatórios para um artigo entrar)

| # | Critério | Teste | Se falhar |
|---|---|---|---|
| 1 | Campos e enums válidos, `id` único `kb-NNN`, data não futura, conteúdo ≥ 40 caracteres | `test_artigo_tem_todos_os_campos_validos` | o upsert quebra ou o artigo vira fonte vazia |
| 2 | Metadados só `str/int/float/bool` | `test_montar_documento_preserva_metadados` | Chroma rejeita a indexação |
| 3 | **Achável pelo próprio título** (no plano que o enxerga) | `test_cada_artigo_ativo_e_achavel_pelo_proprio_titulo` | mal escrito/mal indexado |
| 4 | **Top-1 pelo próprio título** | `test_titulo_exato_traz_o_artigo_em_primeiro` | outro artigo o ofusca → decida: fundir, reescrever ou diferenciar |
| 5 | `deprecated` não volta nem pelo título exato | `test_artigo_deprecated_nao_volta...` | filtro de status quebrado |
| 6 | Título único; sem par ativo com ≥ 70% de vocabulário comum | `test_titulos_unicos`, `test_sem_artigos_quase_duplicados` | competem pelo top-1 e podem se contradizer |
| 7 | **Sem PII** (e-mail, CPF, CNPJ, telefone) e sem segredo | `test_base_nao_contem_dado_pessoal`, `..._segredo` | a base inteira vai ao LLM e ao disco |
| 8 | Deprecated não é mais novo que ativo da mesma categoria | `test_deprecated_mais_antigo_que...` | status esquecido |
| 9 | Frescor: ativo sem revisão > 24 meses | `test_conteudo_ativo_nao_esta_velho` (**aviso**, não falha) | revisar com o dono do conteúdo |

## Procedimento para artigo novo ou editado

1. Rode os testes acima. Todo `FAILED` bloqueia.
2. **Teste de ofuscamento (manual, 2 min):** escreva 3 tickets de cliente (não copie o título) que o artigo deve
   responder, mais 2 tickets de artigos vizinhos que NÃO devem mudar. Adicione-os ao `qa/golden_tickets.json`
   e rode `python -m qa.avaliar_recuperacao --json` antes e depois: nenhum caso `ok` pode perder o top-1.
3. **Coerência de fatos entre artigos:** busque os números do artigo novo nos demais (`grep -n "30 minutos" data/kb.json`).
   Prazo/limite/preço divergente entre artigos é bug de conteúdo que nenhum teste automático pega.
4. **Metadado de plano:** confirme `min_plan` com quem é dono do produto. Errar para BAIXO expõe recurso pago;
   errar para CIMA esconde a resposta (o cliente cai em escalar).
5. `doc_type`: `policy` = regra que o suporte não pode contrariar; `runbook` = orientação interna, **não** deve
   virar promessa ao cliente; confira que o texto do runbook não é redigido como se fosse oferta.
6. Remoção: use `status: deprecated` (auditável). Remover do JSON funciona (a indexação apaga o fantasma), mas some a trilha.
7. Reindexe e rode a suíte completa.

## Armadilhas

- Artigo longo com vários assuntos = um vetor "médio" que não acha nenhum bem. Mantenha 1 assunto por artigo; o
  protótipo não faz chunking (`test_custo_de_contexto_cresce_linearmente...` avisa se um artigo ficar > 3× a média).
- Título genérico ("Informações") ofusca tudo. Título = intenção do cliente ("Como redefinir a senha").
- Sinônimos e siglas que o cliente usa ("travou", "SAML", "429") devem aparecer no corpo: o embedding é pequeno
  e não conhece vocabulário do produto.
- `updated_at` só informa; nada filtra por ela. Conteúdo velho ativo continua sendo citado.
- Dados da base fictícia (Órbita Desk) não podem ser misturados com dados reais de cliente.

## Registrar

Artigos auditados (ids), testes que falharam e por quê, ofuscamentos encontrados, divergências de fatos entre
artigos, e a lista de artigos com aviso de frescor.
