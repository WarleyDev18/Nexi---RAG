---
name: qa-rag-eficacia-testes
description: Mede se a suíte de testes do RAG realmente pega defeitos (cobertura de linhas/ramos com pytest-cov e teste de mutação artesanal em qa/mutacao.py), investiga mutantes sobreviventes e mantém os testes confiáveis (xfail estrito pelo motivo certo, sem flakiness). Use antes de liberar, depois de adicionar muitos testes ou código novo, ou quando pedirem "a cobertura está boa?", "os testes são fortes?", "rodar mutação", "tem teste que passa sem testar nada?", "por que esse xfail?". Não use para achar bugs no produto (use as skills por área).
---

# Eficácia dos testes ("testar o testador")

**Objetivo:** teste verde só vale se ele FALHARIA com o defeito. Cobertura de linha diz que o código executou, não
que alguém conferiu o resultado. Esta skill mede os dois.

## Comandos

```bash
pip install pytest-cov
HF_HUB_OFFLINE=1 pytest -q --cov=src --cov=qa --cov-branch --cov-report=term-missing   # cobertura de linhas e ramos
python -m qa.mutacao --lista                       # mutantes disponíveis (35)
python -m qa.mutacao --so src/validar.py           # só um arquivo (~1 pytest por mutante)
python -m qa.mutacao --saida mut.json              # tudo (~25 min); exit 1 se algum sobreviver
```
Mutação edita `src/` temporariamente e restaura em `try/finally`. **Não edite `src/` ou `tests/` enquanto roda.**
Se interromper à força: `git checkout -- src/` e apague `.chroma/`.

## Critérios

| Medida | Piso | Observação |
|---|---|---|
| Cobertura de ramos de `src/` | ≥ 95% | o que sobra deve ser justificado (ex.: `if __name__`) |
| Cobertura de `qa/` | ≥ 90% | ferramenta de QA sem teste vira fonte de falso verde |
| **Escore de mutação** | 100% dos mutantes **não equivalentes** mortos | sobrevivente = buraco ou mutante equivalente |
| `xfail` | todos `strict=True`, com `reason` apontando bug/limitação | `xfail` frouxo some em silêncio |
| Testes por rodada | ≥ 1 mutante novo para cada guarda nova | senão a guarda pode ser removida sem ninguém notar |

## Como tratar um mutante sobrevivente

1. Reaplique o mutante à mão (copie a troca de `qa/mutacao.py`) e rode a suíte para confirmar `SOBREVIVEU`.
2. É **equivalente**? (muda sintaxe, não comportamento; ex.: `<` vs `<=` só difere em distância exatamente 0,70.)
   Se sim: preencha o campo `equivalente` no mutante com a justificativa e siga. Não use isso como desculpa:
   precisa de argumento, não de preguiça.
3. Senão, **escreva o teste que o mata** (falha com o mutante, passa sem): o menor possível, com assert específico.
4. Reexecute só aquele mutante e depois a suíte completa. Registre o teste novo no relatório.

## Acrescentar mutantes

Em `MUTANTES` (`qa/mutacao.py`): `(arquivo, trecho_original_que_ocorre_1x, trecho_defeituoso, descrição, equivalente|None)`.
Para cada guarda nova no código, crie o mutante que a **remove** (`if False:`) e o que a **inverte**. Valide:
o script avisa `INVALIDO` se o trecho não ocorre exatamente 1 vez (código mudou e o mutante ficou velho).

## Confiabilidade dos testes

- **xfail pelo motivo certo:** `pytest --runxfail -k <teste> --tb=short` e leia a mensagem. Cada `xfail` deve falhar
  exatamente com o sintoma documentado — não por import, fixture ou saída-base inválida (erro real da rodada 1).
- **Determinismo:** rode a suíte 2× seguidas e compare. Semente fixa no fuzz; nenhum teste depende de ordem
  (`-p no:randomly` não é necessário, mas `pytest -p no:cacheprovider` evita estado entre execuções).
- **Estado compartilhado:** a coleção Chroma (`.chroma/`) é persistente. Testes que a alteram limpam no `finally`;
  a mutação apaga o diretório a cada execução.
- **Sem rede/LLM:** nenhum teste da suíte padrão pode chamar a API (fixture `llm_falso`). Teste que precisa de
  chave vai em `qa/` como script, nunca em `tests/`.
- **Asserts vazios:** `assert x` sobre coleção possivelmente vazia passa por engano. Prefira comparar com o valor
  esperado completo. Ao revisar, troque o assert por um valor errado e veja falhar.
- **Parametrização com `ids`:** sem ids legíveis o relatório vira `[case0]`.

## Armadilhas

- 100% de cobertura com 0 asserts úteis é possível. Por isso mutação.
- Mutante equivalente inflado esconde buraco. Justifique um a um.
- Mutar `config.py` sem recalibrar pisos: o teste das métricas pode matar o mutante pelo motivo certo, mas confirme.
- Mutação lenta: use `--so` durante o desenvolvimento, completa antes de liberar.

## Registrar

Cobertura (linhas e ramos) por pacote, escore de mutação, lista de sobreviventes com decisão
(teste novo × equivalente justificado), e testes adicionados.
