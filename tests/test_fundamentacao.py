"""Testa o oráculo de fundamentação numérica (qa/fundamentacao.py) e a regra aplicada a saídas de exemplo."""
import pytest

from qa.fundamentacao import carregar_kb, numeros_sem_fundamento

KB = carregar_kb()


def res(texto, fontes):
    return {"resposta_sugerida": texto, "fontes": fontes}


def test_numero_que_esta_no_artigo_e_fundamentado():
    assert numeros_sem_fundamento(res("O link vale 30 minutos [kb-001].", ["kb-001"]), "senha", KB) == set()


def test_numero_inventado_e_detectado():
    assert numeros_sem_fundamento(res("O link vale 45 minutos [kb-001].", ["kb-001"]), "senha", KB) == {"45"}


def test_numero_do_artigo_errado_nao_vale():
    # 15 está em kb-002, mas a resposta cita só kb-001: citar a fonte errada não fundamenta
    assert numeros_sem_fundamento(res("Aguarde 15 minutos [kb-001].", ["kb-001"]), "senha", KB) == {"15"}


def test_numero_do_proprio_ticket_e_permitido():
    assert numeros_sem_fundamento(res("Sobre o erro 429, veja o limite [kb-011].", ["kb-011"]), "recebo erro 429", KB) == set()


def test_separador_de_milhar_e_normalizado():
    # kb-012 fala em 5.000 tarefas; "5000" na resposta é o mesmo número
    assert numeros_sem_fundamento(res("Acima de 5000 tarefas fica lento [kb-012].", ["kb-012"]), "lento", KB) == set()


def test_id_de_fonte_nao_conta_como_numero():
    assert numeros_sem_fundamento(res("Veja o artigo [kb-001].", ["kb-001"]), "x", KB) == set()


@pytest.mark.parametrize("entrada", [None, [], "texto", {"resposta_sugerida": 5}, {"resposta_sugerida": "a", "fontes": "kb-001"}])
def test_entradas_malformadas_nao_quebram(entrada):
    assert numeros_sem_fundamento(entrada, "x", KB) == set()


def test_fonte_inexistente_nao_fundamenta_nada():
    assert numeros_sem_fundamento(res("Vale 30 minutos.", ["kb-999"]), "x", KB) == {"30"}
