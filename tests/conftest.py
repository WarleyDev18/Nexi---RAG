"""Fixtures compartilhadas da suíte de QA.

- `base_indexada`: indexa a KB uma vez por sessão (o modelo de embedding é o custo dominante, ~40 s).
- `llm_falso`: substitui o SDK `anthropic` por um dublê controlável — nenhum teste de QA gasta token.
"""
import sys
import types

import pytest


@pytest.fixture(scope="session")
def base_indexada():
    from src.indexar import indexar

    indexar()


class LLMFalso:
    """Devolve exatamente o que o teste mandar. `responder(None)` simula resposta sem conteúdo."""

    def __init__(self):
        self.texto = "{}"
        self.chamadas = 0
        self.prompts = []
        self.kwargs = []

    def responder(self, saida):
        import json

        self.texto = saida if (isinstance(saida, str) or saida is None) else json.dumps(saida, ensure_ascii=False)


@pytest.fixture
def llm_falso(monkeypatch):
    falso = LLMFalso()

    class _Bloco:
        def __init__(self, t):
            self.text = t

    class _Mensagem:
        def __init__(self, blocos):
            self.content = blocos

    class _Messages:
        def create(self, **kw):
            falso.chamadas += 1
            falso.prompts.append(kw["messages"][0]["content"])
            falso.kwargs.append(kw)
            return _Mensagem([] if falso.texto is None else [_Bloco(falso.texto)])

    class _Cliente:
        def __init__(self, *a, **k):
            self.messages = _Messages()

    monkeypatch.setitem(sys.modules, "anthropic", types.SimpleNamespace(Anthropic=_Cliente))
    return falso


def saida_valida(**sobrescrever):
    """Saída 'perfeita' do LLM para o ticket de senha; os testes estragam um campo por vez."""
    base = {
        "categoria": "auth",
        "prioridade": "normal",
        "escalar": False,
        "motivo_escalar": "",
        "resposta_sugerida": "Clique em 'Esqueci minha senha' na tela de login; o link vale 30 minutos [kb-001].",
        "fontes": ["kb-001"],
    }
    base.update(sobrescrever)
    return base
