"""Robustez de entrada: nenhum texto de ticket pode derrubar a recuperação nem o roteamento.
Fuzz determinístico (semente fixa) + casos de borda que aparecem em ticket real."""
import random
import string
import time

import pytest

from src import config
from src.main import triar
from src.recuperar import recuperar
from tests.conftest import saida_valida

pytestmark = pytest.mark.usefixtures("base_indexada")

BORDA = [
    "", " ", "\n\n\n", "\t", "a", "?", "😀" * 50, "ñáéíóúç " * 30, "SELECT * FROM kb; DROP TABLE kb;--",
    "<script>alert(1)</script>", "{{7*7}} ${jndi:ldap://x}", "\\", '"', "'", "{'a': 1}", "[]", "null", "0",
    "a" * 20000, "esqueci a senha " * 2000, "​​​", "ＥＳＱＵＥＣＩ　Ａ　ＳＥＮＨＡ", "senha\x00senha",
    "Esqueci a senha\r\nE agora?\r\n", "مرحبا لا أستطيع تسجيل الدخول", "我忘记了密码",
]


def _aleatorios(n=25, semente=20261014):
    rnd = random.Random(semente)
    alfabeto = string.printable + "áéíóúãõçñ€€😀"
    return ["".join(rnd.choice(alfabeto) for _ in range(rnd.randint(1, 300))) for _ in range(n)]


@pytest.mark.parametrize("ticket", BORDA, ids=[f"borda{i}" for i in range(len(BORDA))])
def test_recuperar_aceita_qualquer_texto(ticket):
    for plano in config.RANK_PLANO:
        r = recuperar(ticket, plano)
        assert len(r) <= config.TOP_K


def test_fuzz_recuperar_nunca_levanta_excecao():
    for t in _aleatorios():
        recuperar(t, "enterprise")


def test_fuzz_triar_sempre_devolve_destino_valido(llm_falso):
    llm_falso.responder(saida_valida())
    for t in BORDA + _aleatorios(10):
        res = triar(t, "pro")
        assert res["destino"] in {"fila_humana", "rascunho_para_revisao"}, repr(t[:40])


def test_ticket_gigante_nao_trava():
    inicio = time.perf_counter()
    recuperar("esqueci a senha " * 6000, "free")  # ~100 mil caracteres
    assert time.perf_counter() - inicio < 20


def test_ticket_gigante_ainda_acha_o_assunto():
    """O embedding trunca a entrada: o assunto nos primeiros tokens tem que bastar."""
    assert "kb-001" in [t.id for t in recuperar("esqueci a senha " * 500, "free")]
