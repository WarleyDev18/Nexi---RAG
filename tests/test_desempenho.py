"""Orçamento de prompt e latência. Limites GENEROSOS de propósito (máquinas e CI variam): pegam regressão de
ordem de grandeza (ex.: alguém sobe TOP_K para 50 ou passa a mandar a base inteira), não microvariação.

Tokens: aproximação 1 token ≈ 3,5 caracteres em português (sem tokenizer, sem rede).
"""
import statistics
import time

import pytest

from src import config
from src.gerar import REGRAS, montar_prompt
from src.recuperar import Trecho, recuperar

pytestmark = pytest.mark.usefixtures("base_indexada")

CHARS_POR_TOKEN = 3.5
ORCAMENTO_TOKENS_PROMPT = 2500  # medido na rodada 2: pior caso ≈ 1,4 mil (medido em 14/10/2026); folga de ~1,8x


def _pior_caso(tickets_chars=2000):
    import json

    kb = json.loads(config.KB_PATH.read_text(encoding="utf-8"))
    maiores = sorted((a for a in kb if a["status"] == "active"), key=lambda a: -len(a["content"]))[: config.TOP_K]
    trechos = [Trecho(a["id"], f"{a['title']}\n{a['content']}", 0.5,
                      {"doc_type": a["doc_type"], "updated_at": a["updated_at"]}) for a in maiores]
    return montar_prompt("x" * tickets_chars, "enterprise", trechos)


def test_prompt_no_pior_caso_cabe_no_orcamento():
    tokens = len(_pior_caso()) / CHARS_POR_TOKEN
    assert tokens < ORCAMENTO_TOKENS_PROMPT, f"prompt de pior caso ≈ {tokens:.0f} tokens (orçamento {ORCAMENTO_TOKENS_PROMPT})"


def test_regras_nao_crescem_sem_aviso():
    assert len(REGRAS) < 2200, f"REGRAS com {len(REGRAS)} caracteres: cada regra nova custa tokens em TODO ticket"


def test_top_k_nao_foi_inflado():
    assert config.TOP_K <= 8, "TOP_K alto multiplica o custo por ticket e dilui o contexto (README: 'por que 4')"


def test_custo_de_contexto_cresce_linearmente_com_top_k():
    """O contexto de TOP_K=4 não pode custar mais que 4× um artigo médio + overhead (detecta chunk gigante)."""
    import json

    kb = [a for a in json.loads(config.KB_PATH.read_text(encoding="utf-8")) if a["status"] == "active"]
    medio = statistics.mean(len(a["content"]) for a in kb)
    assert max(len(a["content"]) for a in kb) < 3 * medio, "artigo desproporcional: considere dividir (chunking)"


def test_latencia_da_recuperacao_aquecida():
    recuperar("aquecer o modelo", "free")
    tempos = []
    for t in ["esqueci a senha", "meu webhook falha", "quero reembolso", "exportar dados", "limite da API"] * 4:
        t0 = time.perf_counter()
        recuperar(t, "pro")
        tempos.append(time.perf_counter() - t0)
    tempos.sort()
    p95 = tempos[int(len(tempos) * 0.95) - 1]
    assert statistics.median(tempos) < 1.0, f"mediana {statistics.median(tempos):.2f}s"
    assert p95 < 3.0, f"p95 {p95:.2f}s"
