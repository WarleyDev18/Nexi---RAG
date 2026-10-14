"""A ferramenta de mutação também precisa ser confiável: mutante velho (trecho que não existe mais) viraria
'INVALIDO' silencioso e a cobertura de defeitos cairia sem ninguém ver."""
from pathlib import Path

import pytest

import qa.mutacao as mut
from src import config


@pytest.mark.parametrize("arquivo, original, mutado, desc, equiv", mut.MUTANTES, ids=[m[3][:40] for m in mut.MUTANTES])
def test_todo_mutante_se_aplica_exatamente_uma_vez_ao_codigo_atual(arquivo, original, mutado, desc, equiv):
    texto = (config.RAIZ / arquivo).read_text(encoding="utf-8")
    assert texto.count(original) == 1, f"mutante velho: {desc!r} — {original[:60]!r} ocorre {texto.count(original)}x"
    assert original != mutado, "mutante idêntico ao original não muta nada"


def test_mutantes_cobrem_todos_os_arquivos_de_producao():
    alvo = {m[0] for m in mut.MUTANTES}
    assert {"src/recuperar.py", "src/indexar.py", "src/gerar.py", "src/main.py", "src/validar.py", "src/config.py"} <= alvo


def test_aplicar_troca_e_devolve_o_original_para_restaurar(tmp_path, monkeypatch):
    monkeypatch.setattr(mut, "RAIZ", tmp_path)
    (tmp_path / "a.py").write_text("x = 1\ny = 2\n", encoding="utf-8")
    caminho, original = mut.aplicar("a.py", "x = 1", "x = 99")
    assert caminho.read_text(encoding="utf-8") == "x = 99\ny = 2\n"
    assert original == "x = 1\ny = 2\n"


@pytest.mark.parametrize("conteudo", ["nada aqui", "x = 1\nx = 1\n"], ids=["ausente", "duplicado"])
def test_aplicar_recusa_trecho_ausente_ou_ambiguo_e_nao_altera_o_arquivo(tmp_path, monkeypatch, conteudo):
    monkeypatch.setattr(mut, "RAIZ", tmp_path)
    f = tmp_path / "a.py"
    f.write_text(conteudo, encoding="utf-8")
    with pytest.raises(ValueError, match="esperado 1"):
        mut.aplicar("a.py", "x = 1", "x = 2")
    assert f.read_text(encoding="utf-8") == conteudo


def test_rodar_suite_limpa_o_indice_e_traduz_codigo_de_saida(tmp_path, monkeypatch):
    monkeypatch.setattr(mut, "RAIZ", tmp_path)
    (tmp_path / ".chroma").mkdir()
    (tmp_path / ".chroma" / "lixo").write_text("x")

    class P:
        returncode = 1

    monkeypatch.setattr(mut.subprocess, "run", lambda *a, **k: P())
    assert mut.rodar_suite() == 1
    assert not (tmp_path / ".chroma").exists(), "índice de uma execução vazaria para a próxima"
