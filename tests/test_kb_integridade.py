"""Integridade da base de conhecimento e da montagem de documentos. Rápido: não carrega o modelo de embedding."""
import json
import re
from collections import Counter
from datetime import date

import pytest

from qa.contrato import CATEGORIAS
from src import config
from src.gerar import REGRAS
from src.indexar import montar_documento

KB = json.loads(config.KB_PATH.read_text(encoding="utf-8"))
CAMPOS = {"id", "title", "category", "doc_type", "min_plan", "status", "updated_at", "content"}


def test_kb_ids_unicos_e_no_formato():
    ids = [a["id"] for a in KB]
    assert not [i for i, n in Counter(ids).items() if n > 1], "ids duplicados"
    assert all(re.fullmatch(r"kb-\d{3}", i) for i in ids)


@pytest.mark.parametrize("artigo", KB, ids=[a["id"] for a in KB])
def test_artigo_tem_todos_os_campos_validos(artigo):
    assert CAMPOS <= artigo.keys(), f"faltam: {CAMPOS - artigo.keys()}"
    assert artigo["min_plan"] in config.RANK_PLANO
    assert artigo["status"] in {"active", "deprecated"}
    assert artigo["doc_type"] in {"faq", "runbook", "policy"}
    assert artigo["category"] in CATEGORIAS
    assert len(artigo["content"].strip()) > 40, "conteúdo curto demais para ser fonte"
    assert date.fromisoformat(artigo["updated_at"]) <= date.today(), "updated_at no futuro"


def test_kb_cobre_os_casos_que_os_filtros_precisam():
    """Se alguém tirar estes artigos, os testes de filtro passam a ser vácuo."""
    assert any(a["status"] == "deprecated" for a in KB), "sem artigo deprecated: filtro de status não é testado"
    assert any(a["min_plan"] == "enterprise" for a in KB)
    assert any(a["min_plan"] == "pro" for a in KB)
    assert any(a["doc_type"] == "policy" for a in KB)


def test_golden_referencia_apenas_ids_existentes():
    from qa.metricas import carregar_golden

    ids = {a["id"] for a in KB}
    for caso in carregar_golden():
        assert set(caso["esperado"]) <= ids, f"{caso['id']} espera artigo inexistente"
        assert caso["plano"] in config.RANK_PLANO


@pytest.mark.parametrize("artigo", KB, ids=[a["id"] for a in KB])
def test_montar_documento_preserva_metadados(artigo):
    d = montar_documento(artigo)
    assert d["id"] == artigo["id"]
    assert d["content"] == f"{artigo['title']}\n{artigo['content']}"  # título entra no vetor
    m = d["metadata"]
    assert isinstance(m["min_plan_rank"], int) and not isinstance(m["min_plan_rank"], bool)
    assert m["min_plan_rank"] == config.RANK_PLANO[artigo["min_plan"]]
    assert m["status"] == artigo["status"]
    # Chroma só aceita str/int/float/bool nos metadados: lista ou None quebra a indexação em produção
    assert all(isinstance(v, (str, int, float, bool)) for v in m.values())


def test_enums_do_contrato_batem_com_o_prompt():
    """O oráculo (qa/contrato.py) e o prompt (gerar.REGRAS) não podem divergir em silêncio."""
    linha_cat = re.search(r'"categoria": "([^"]+)"', REGRAS).group(1)
    linha_pri = re.search(r'"prioridade": "([^"]+)"', REGRAS).group(1)
    from qa.contrato import PRIORIDADES

    assert set(linha_cat.split("|")) == CATEGORIAS
    assert set(linha_pri.split("|")) == PRIORIDADES
