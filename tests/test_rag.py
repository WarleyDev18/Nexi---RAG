"""Testes da parte determinística: filtros, corte de relevância e montagem do prompt.
O LLM não é chamado aqui."""
import pytest

from src.gerar import montar_prompt
from src.indexar import indexar
from src.recuperar import montar_filtro, recuperar


@pytest.fixture(scope="module", autouse=True)
def base():
    indexar()


def ids(ticket, plano):
    return [t.id for t in recuperar(ticket, plano)]


def test_filtro_plano_free_nao_ve_sso_enterprise():
    assert "kb-003" not in ids("Como configuro SSO com SAML?", "free")
    assert "kb-003" in ids("Como configuro SSO com SAML?", "enterprise")


def test_deprecated_nunca_recuperado():
    assert "kb-004" not in ids("login com Google não funciona", "enterprise")


def test_pergunta_de_senha_acha_artigo_certo():
    assert ids("esqueci minha senha e não consigo entrar", "free")[0] == "kb-001"


def test_fora_de_escopo_nao_recupera_nada():
    assert ids("qual a receita de bolo de cenoura?", "pro") == []


def test_prompt_contem_regras_contexto_e_ticket():
    p = montar_prompt("meu ticket", "pro", recuperar("esqueci minha senha", "pro"))
    assert "Regras obrigatórias" in p and "[kb-001]" in p and "<ticket>\nmeu ticket" in p


def test_filtro_estrutura():
    assert montar_filtro("pro")["$and"][1] == {"min_plan_rank": {"$lte": 1}}
