# Microagente RAG — triagem de tickets de suporte

Protótipo de RAG (Retrieval-Augmented Generation) que recebe o texto de um ticket de suporte e devolve, em JSON:
categoria, prioridade, se deve **escalar para humano**, uma **resposta sugerida** e as **fontes citadas**.

> **Cenário fictício.** "Órbita Desk" é um SaaS de gestão de projetos inventado para este exercício; a base de
> conhecimento (`data/kb.json`, 15 artigos) é sintética. Nada aqui vem de um sistema real.

```
ticket ──► [2 Recuperação] ──► [3 Aumento] ──► [3 Geração] ──► JSON ──► fila humana | rascunho p/ revisão
            Chroma + filtros     regras +        Claude
            + topK + corte       contexto +
                                 ticket
[1 Indexação] artigos ─► id/content/metadata/embedding ─► Chroma (disco)
```

## Como rodar

```bash
python -m venv .venv && source .venv/bin/activate     # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python -m src.indexar                                  # etapa 1
python -m src.main "Esqueci a senha e não consigo entrar" --plano free --dry-run   # etapas 2 e 3 (prompt), sem LLM
export ANTHROPIC_API_KEY=...                           # com a chave, roda a geração completa
python -m src.main "Esqueci a senha e não consigo entrar" --plano free
pytest                                                 # testes de filtro, corte e prompt (sem LLM)
```

## QA

Matriz de risco → teste → status: [docs/MATRIZ-QUALIDADE.md](docs/MATRIZ-QUALIDADE.md) · achados e histórico: [docs/QA-RELATORIO.md](docs/QA-RELATORIO.md).
Sete skills de QA para o Claude Code em [.claude/skills/](.claude/skills/): `qa-rag-recuperacao`, `-geracao`, `-base-conhecimento`, `-seguranca`, `-robustez-desempenho`, `-eficacia-testes` e o orquestrador `-relatorio`.

```bash
pip install -r requirements-dev.txt
pytest -rxX                                    # suíte inteira, sem LLM e sem rede de LLM (LLM falso)
python -m qa.avaliar_recuperacao               # recall@K, MRR, top-1 no golden set
python -m qa.mutacao                           # teste de mutação (35 mutantes, ~25 min)
ANTHROPIC_API_KEY=... python -m qa.avaliar_geracao   # LLM real: contrato, escalonamento, fundamentação (exige chave)
```
`xfail(strict)` = limitação conhecida: ao resolver uma, o teste falha pedindo para remover a marca.

## Onde está cada etapa

| Etapa | Arquivo | O que mostra |
|---|---|---|
| 1. Indexação | [src/indexar.py](src/indexar.py) | documento = `id` + `content` + `metadata` + `embedding`, persistido no Chroma |
| 2. Recuperação | [src/recuperar.py](src/recuperar.py) | query em linguagem natural, `topK`, filtros por metadado, corte por distância |
| 3. Aumento + geração | [src/gerar.py](src/gerar.py) | prompt = regras + contexto + ticket; chamada ao LLM; parsing seguro |
| Fluxo e propagação | [src/main.py](src/main.py) | encadeia tudo e roteia o resultado (humano × rascunho) |

## Por que RAG faz sentido aqui (e onde não faria)

**Faz sentido porque** a resposta correta depende de fatos que mudam e que o LLM não pode saber: limites por plano
(50 automações no Pro), prazos (link de senha vale 30 min), política de reembolso. Colocar tudo no prompt não escala
(a base cresce) e *fine-tuning* seria caro e ficaria velho a cada mudança de política. Com RAG, atualizar um artigo
e reindexar basta, e cada afirmação pode ser rastreada até um `id`, o que é essencial em suporte.

**Não faria sentido (ou seria exagero) se:** a base coubesse em ~2 páginas (colar no prompt resolve), se as
perguntas fossem consultas estruturadas ("qual o plano da conta X?", que pede SQL/API, não busca semântica), ou se
o risco de erro fosse tão alto que só humano deveria responder. Por isso o protótipo gera **rascunho**, não resposta
automática.

## Decisões e por quê

### Metadados
| Campo | Por quê |
|---|---|
| `min_plan_rank` (int 0/1/2) | Evita sugerir a um cliente Free um recurso Enterprise. É **inteiro** porque o Chroma só compara números com `$lte`; texto exigiria listar planos permitidos. |
| `status` | Artigos `deprecated` ficam indexados (auditoria, reativação) mas **nunca** são recuperados. |
| `doc_type` (faq/runbook/policy) | Vai para o prompt: uma *policy* é regra, um *runbook* é orientação interna que não deve virar promessa ao cliente. |
| `updated_at` | Permite ao LLM e ao humano desconfiar de fonte velha. Hoje só informa; não filtra. |
| `category`, `title` | Citação legível e métrica de cobertura por área. |

Decidi **não** guardar `min_plan` como texto nem `plans` como lista: Chroma não filtra dentro de listas.

### Filtros (aplicados no banco, antes do topK)
`status == active` **e** `min_plan_rank <= plano_do_cliente`. É pré-filtro de propósito: filtrar *depois* de pegar
o topK pode deixar zero resultados úteis (os 4 melhores podem ser todos de plano superior).

### topK = 4 e corte de distância = 0,70
Medi distâncias de cosseno reais em 8 tickets (modelo `paraphrase-multilingual-MiniLM-L12-v2`):

| Tipo de ticket | Melhor acerto | Ruído típico |
|---|---|---|
| Em escopo e claro (senha, webhook, lentidão, exportar) | 0,48–0,57 | 0,63+ |
| Fora de escopo ("receita de bolo") | 0,91 | tudo ≥ 0,91 |
| Em escopo mas sem artigo ("integração com Jira") | 0,81 | tudo ≥ 0,81 |

- **topK = 4:** os acertos reais ficam nas 1–3 primeiras posições; mais que 4 só acrescenta ruído e custo de
  tokens. Menos que 3 arrisca perder um artigo complementar (ex.: senha esquecida + conta bloqueada, que são dois
  artigos distintos e ambos úteis).
- **Corte 0,70:** o topK sempre devolve K itens, mesmo ruins. Com 0,75 eu vi ruído passando (ticket de reembolso
  trazia o artigo de senha a 0,75); 0,70 elimina isso nos casos medidos e ainda separa fora-de-escopo (≥ 0,81).
  Se nada passa no corte, o código **escala para humano sem depender do LLM**.
- O 0,70 foi calibrado em **8 exemplos**, não em um conjunto de avaliação. É um ponto de partida, não um valor validado.

### Regras de negócio no prompt
Só usar o contexto; citar `[id]`; admitir quando o contexto é insuficiente; nunca prometer reembolso/exceção;
tratar o texto do ticket como dado (mitiga *prompt injection*); responder só em JSON. Duas regras são reforçadas
**fora** do LLM, porque prompt não é garantia: JSON inválido vira "escalar", e zero trechos vira "escalar".

## Crítica honesta — limitações do protótipo

1. **Limiar não é garantia de relevância.** Medi um caso real de falha: um cliente Free perguntando de SSO recebe
   o artigo de SLA (distância 0,65, passa no corte) porque o artigo certo está filtrado por plano. O contexto é
   "relevante o bastante" para o vetor e inútil para a pergunta. Dependo do LLM para dizer "não sei" nesse caso — e
   não o testei sob volume.
2. **Alucinação remanescente.** As regras reduzem, não eliminam. O modelo pode combinar dois artigos e inferir um
   prazo que nenhum afirma, ou citar `[kb-001]` para uma frase que o artigo não sustenta. A citação *parece*
   verificação, mas hoje ninguém checa se o id citado existe/apoia a frase. Falta um passo de validação (ids
   citados ⊆ ids recuperados, no mínimo).
3. **Contexto insuficiente em perguntas compostas.** Um ticket com dois problemas (ex.: cobrança + integração) é
   embutido como **um** vetor; o topK pode cobrir só um dos assuntos. Melhoria: quebrar o ticket em sub-perguntas
   antes de buscar.
4. **A chamada ao LLM não foi executada de ponta a ponta nesta entrega.** Validei indexação, recuperação,
   filtros, corte e montagem do prompt (6 testes + dry-run). O trecho `gerar()` segue a API do SDK, mas **não o
   rodei contra a API** por falta de chave no ambiente de desenvolvimento. Trate a qualidade das respostas como
   não medida.
5. **Sem avaliação sistemática.** Não há conjunto de tickets rotulados com a resposta esperada, então não sei
   precisão/recall da recuperação nem a taxa de escalonamento correta. Os testes cobrem comportamento
   determinístico, não qualidade.
6. **Embedding pequeno e genérico.** Um modelo MiniLM multilíngue entende português razoavelmente, mas não
   vocabulário do produto nem siglas ("SAML", "429"); busca híbrida (BM25 + vetor) ajudaria em termos exatos.
7. **Custo de indexação e manutenção.** Aqui é desprezível (15 artigos, embedding local e gratuito). Em escala,
   o custo real está em: reindexar quando o modelo de embedding muda (todos os vetores ficam incompatíveis),
   manter artigos atualizados e *chunking* — artigos longos precisarão ser divididos, o que o protótipo não faz
   (1 artigo = 1 vetor).
8. **Dados e privacidade.** Tickets reais contêm dados pessoais; mandar o texto a um LLM externo exige
   mascaramento e base legal. Não tratado aqui.
9. **Escala e frescor.** Chroma local em disco serve ao protótipo; não há atualização incremental automática
   nem controle de versão dos artigos.

## Próximos passos (se virasse produto)
Conjunto de avaliação rotulado → ajustar topK/corte com métricas; validação de citações; busca híbrida;
*chunking*; reranker; mascaramento de PII; monitorar taxa de escalonamento e feedback do atendente.
