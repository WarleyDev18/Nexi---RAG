"""Testa o testador: o oráculo `qa.contrato` tem que reprovar o que deve reprovar e aprovar o que é correto.
Sem isso, um oráculo frouxo faz toda a suíte de geração passar por engano."""
import pytest

from qa.contrato import seguro_para_propagar, validar_saida
from tests.conftest import saida_valida

IDS = ["kb-001", "kb-002"]


def test_saida_correta_passa():
    assert validar_saida(saida_valida(), IDS) == []


@pytest.mark.parametrize(
    "saida, trecho_da_violacao",
    [
        ([1, 2], "não é objeto"),
        ("oi", "não é objeto"),
        (saida_valida(categoria="banana"), "categoria fora do enum"),
        (saida_valida(prioridade="critica"), "prioridade fora do enum"),
        (saida_valida(escalar="false"), "escalar não é booleano"),
        (saida_valida(fontes=["kb-999"]), "fonte citada não foi recuperada"),
        (saida_valida(resposta_sugerida="Veja [kb-777]."), "citação no texto"),
        (saida_valida(fontes=[]), "sem nenhuma fonte"),
        (saida_valida(resposta_sugerida=" "), "resposta vazia"),
        (saida_valida(resposta_sugerida="palavra " * 121 + "[kb-001]"), "palavras"),
        (saida_valida(resposta_sugerida="Seu reembolso foi aprovado [kb-001]."), "promete"),
        (saida_valida(resposta_sugerida="Aprovamos o desconto para você [kb-001]."), "promete"),
        (saida_valida(destino="rascunho_para_revisao", escalar=True), "destino inconsistente"),
    ],
)
def test_oraculo_reprova(saida, trecho_da_violacao):
    assert any(trecho_da_violacao in v for v in validar_saida(saida, IDS)), validar_saida(saida, IDS)


def test_oraculo_reprova_chave_ausente():
    s = saida_valida()
    del s["escalar"]
    assert any("escalar" in v for v in validar_saida(s, IDS))


@pytest.mark.parametrize(
    "texto",
    [
        "O reembolso é decidido pela equipe financeira; vou encaminhar seu pedido [kb-006].",
        "Não consigo confirmar reembolso por aqui, a equipe responsável vai analisar [kb-006].",
        "Reembolso integral é possível em até 7 dias após a contratação do Pro [kb-006].",
    ],
)
def test_oraculo_nao_acusa_falso_positivo_em_resposta_cautelosa(texto):
    assert validar_saida(saida_valida(resposta_sugerida=texto, fontes=["kb-001"]), ["kb-001", "kb-006"]) == []


def test_escalar_dispensa_fonte_e_resposta():
    assert validar_saida(saida_valida(escalar=True, fontes=[], resposta_sugerida=""), IDS) == []


def test_invariante_fila_humana_e_sempre_segura():
    assert seguro_para_propagar({"destino": "fila_humana", "escalar": True}, [])
    assert not seguro_para_propagar({"destino": "rascunho_para_revisao", "escalar": False}, [])


@pytest.mark.parametrize(
    "campo, valor, trecho",
    [
        ("fontes", "kb-001", "fontes não é lista"),
        ("resposta_sugerida", 123, "resposta_sugerida não é texto"),
        ("categoria", ["auth"], "categoria fora do enum"),
        ("prioridade", {"a": 1}, "prioridade fora do enum"),
        ("fontes", [["kb-001"]], "fonte citada não foi recuperada"),
    ],
)
def test_oraculo_nao_quebra_com_tipo_errado_e_reprova(campo, valor, trecho):
    v = validar_saida(saida_valida(**{campo: valor}), IDS)
    assert any(trecho in x for x in v), v


def test_vazamento_do_prompt_e_reprovado():
    s = saida_valida(resposta_sugerida="Use SOMENTE o CONTEXTO abaixo para afirmar fatos [kb-001].")
    assert any("vazamento" in v for v in validar_saida(s, IDS))
