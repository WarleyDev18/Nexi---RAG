"""Qualidade da BASE DE CONHECIMENTO (não do código): o RAG é tão bom quanto os artigos que indexa.

Complementa `test_kb_integridade.py` (formato) com o que afeta a resposta: cada artigo é achável, não há
duplicata/contradição óbvia, não há dado pessoal na base e o conteúdo não está velho.
"""
import json
import re
import warnings
from datetime import date

import pytest

from src import config
from src.recuperar import recuperar

KB = json.loads(config.KB_PATH.read_text(encoding="utf-8"))
ATIVOS = [a for a in KB if a["status"] == "active"]
DEPRECATED = [a for a in KB if a["status"] == "deprecated"]


@pytest.mark.usefixtures("base_indexada")
@pytest.mark.parametrize("artigo", ATIVOS, ids=[a["id"] for a in ATIVOS])
def test_cada_artigo_ativo_e_achavel_pelo_proprio_titulo(artigo):
    """Teste de saúde do índice: se o título de um artigo não o recupera (no plano que o enxerga), o artigo
    está mal escrito, mal indexado ou ofuscado por outro."""
    ids = [t.id for t in recuperar(artigo["title"], artigo["min_plan"])]
    assert artigo["id"] in ids, f"{artigo['id']} não volta nem pelo título exato; veio {ids}"


@pytest.mark.usefixtures("base_indexada")
@pytest.mark.parametrize("artigo", ATIVOS, ids=[a["id"] for a in ATIVOS])
def test_titulo_exato_traz_o_artigo_em_primeiro(artigo):
    ids = [t.id for t in recuperar(artigo["title"], artigo["min_plan"])]
    assert ids and ids[0] == artigo["id"], f"{artigo['id']}: top-1 foi {ids[:1]} (outro artigo ofusca este)"


@pytest.mark.usefixtures("base_indexada")
@pytest.mark.parametrize("artigo", DEPRECATED, ids=[a["id"] for a in DEPRECATED])
def test_artigo_deprecated_nao_volta_nem_pelo_titulo_exato(artigo):
    for plano in config.RANK_PLANO:
        assert artigo["id"] not in [t.id for t in recuperar(artigo["title"], plano)]


def test_titulos_unicos():
    titulos = [a["title"].strip().lower() for a in KB]
    assert len(titulos) == len(set(titulos))


def _palavras(texto):
    return set(re.findall(r"\w{4,}", texto.lower()))


def test_sem_artigos_quase_duplicados():
    """Dois artigos ativos com >70% de vocabulário em comum competem pelo mesmo top-1 e podem se contradizer."""
    for i, a in enumerate(ATIVOS):
        for b in ATIVOS[i + 1:]:
            pa, pb = _palavras(a["content"]), _palavras(b["content"])
            jaccard = len(pa & pb) / len(pa | pb)
            assert jaccard < 0.70, f"{a['id']} e {b['id']} têm {jaccard:.0%} de vocabulário em comum"


PII = {
    "e-mail": re.compile(r"[\w.+-]+@[\w-]+\.[\w.]+"),
    "CPF": re.compile(r"\b\d{3}\.?\d{3}\.?\d{3}-?\d{2}\b"),
    "CNPJ": re.compile(r"\b\d{2}\.?\d{3}\.?\d{3}/?\d{4}-?\d{2}\b"),
    "telefone": re.compile(r"\(?\b\d{2}\)?\s?9?\d{4}-?\d{4}\b"),
}


@pytest.mark.parametrize("tipo", PII)
def test_base_nao_contem_dado_pessoal(tipo):
    for a in KB:
        assert not PII[tipo].search(a["title"] + " " + a["content"]), f"{a['id']} contém {tipo}"


def test_base_nao_contem_segredo():
    bruto = config.KB_PATH.read_text(encoding="utf-8")
    assert not re.search(r"sk-ant-|api[_-]?key|password\s*[:=]|bearer\s+[a-z0-9]{16,}", bruto, re.IGNORECASE)


def test_conteudo_ativo_nao_esta_velho():
    """Aviso (não falha): artigo ativo sem revisão há > 24 meses. O teste não quebra o build só porque o tempo passou."""
    velhos = [a["id"] for a in ATIVOS if (date.today() - date.fromisoformat(a["updated_at"])).days > 730]
    if velhos:
        warnings.warn(f"artigos ativos sem revisão há mais de 24 meses: {velhos}")


def test_deprecated_mais_antigo_que_todo_ativo_da_mesma_categoria():
    """Um artigo descontinuado atualizado DEPOIS dos ativos da categoria indica status esquecido."""
    for d in DEPRECATED:
        recentes = [a for a in ATIVOS if a["category"] == d["category"] and a["updated_at"] < d["updated_at"]]
        assert not recentes, f"{d['id']} (deprecated) é mais novo que {[a['id'] for a in recentes]}"
