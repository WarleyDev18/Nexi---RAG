"""CLI e módulos executáveis (`python -m src.main`, `python -m src.indexar`, `python -m qa.*`)."""
import json
import runpy
import sys

import pytest

from tests.conftest import saida_valida

pytestmark = pytest.mark.usefixtures("base_indexada")


def _marcas(texto):
    """Rótulos que iniciam linha de resultado (a legenda do rodapé também cita os nomes: não vale substring)."""
    return {l.split()[0] for l in texto.splitlines() if l.strip()}


def _rodar(monkeypatch, capsys, modulo, *args):
    monkeypatch.setattr(sys, "argv", [modulo, *args])
    try:
        runpy.run_module(modulo, run_name="__main__")
        codigo = 0
    except SystemExit as e:
        codigo = e.code
    return codigo, capsys.readouterr()


def test_cli_dry_run_mostra_recuperados_e_prompt_sem_llm(monkeypatch, capsys, llm_falso):
    codigo, saida = _rodar(monkeypatch, capsys, "src.main", "Esqueci a senha", "--plano", "free", "--dry-run")
    assert codigo == 0 and "Recuperados (id, distância):" in saida.out and "kb-001" in saida.out
    assert "Regras obrigatórias" in saida.out
    assert llm_falso.chamadas == 0


def test_cli_completo_imprime_json_valido(monkeypatch, capsys, llm_falso):
    llm_falso.responder(saida_valida(resposta_sugerida="Você consegue redefinir pela tela de login [kb-001]."))
    codigo, saida = _rodar(monkeypatch, capsys, "src.main", "Esqueci a senha e não consigo entrar")
    assert codigo == 0
    out = json.loads(saida.out)
    assert out["destino"] == "rascunho_para_revisao" and out["fontes"] == ["kb-001"]
    assert "Você" in saida.out, "ensure_ascii=False: acentos legíveis no terminal (não \u00ea)"


def test_cli_plano_default_e_free(monkeypatch, capsys, llm_falso):
    llm_falso.responder(saida_valida())
    _rodar(monkeypatch, capsys, "src.main", "Como configuro SSO com SAML?")
    assert "[kb-003]" not in llm_falso.prompts[-1] if llm_falso.prompts else True  # Free não enxerga SSO


def test_cli_rejeita_plano_invalido(monkeypatch, capsys):
    codigo, saida = _rodar(monkeypatch, capsys, "src.main", "oi", "--plano", "gold")
    assert codigo == 2 and "invalid choice" in saida.err


def test_cli_sem_ticket_mostra_uso(monkeypatch, capsys):
    codigo, saida = _rodar(monkeypatch, capsys, "src.main")
    assert codigo == 2 and "usage" in saida.err.lower()


def test_cli_indexar_reporta_quantidade(monkeypatch, capsys):
    codigo, saida = _rodar(monkeypatch, capsys, "src.indexar")
    assert codigo == 0 and "15 documentos indexados" in saida.out


def test_qa_avaliar_recuperacao_json_e_exit_zero(monkeypatch, capsys):
    codigo, saida = _rodar(monkeypatch, capsys, "qa.avaliar_recuperacao", "--json")
    assert codigo == 0
    dados = json.loads(saida.out)
    assert {"resumo", "casos"} <= dados.keys() and dados["resumo"]["recall@4"] >= 0.95


def test_qa_avaliar_recuperacao_texto(monkeypatch, capsys):
    codigo, saida = _rodar(monkeypatch, capsys, "qa.avaliar_recuperacao")
    assert codigo == 0 and "RESUMO" in saida.out and "LIM " in saida.out


def test_qa_avaliar_geracao_exige_chave(monkeypatch, capsys):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    codigo, _ = _rodar(monkeypatch, capsys, "qa.avaliar_geracao")
    assert "ANTHROPIC_API_KEY ausente" in str(codigo)


def test_qa_avaliar_geracao_com_llm_falso_relatorio_e_exit(monkeypatch, capsys, llm_falso, tmp_path):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "chave-de-teste")
    llm_falso.responder(saida_valida())
    arq = tmp_path / "out.json"
    codigo, saida = _rodar(monkeypatch, capsys, "qa.avaliar_geracao", "--so-adversariais", "--saida", str(arq))
    # LLM falso ingênuo cita sempre kb-001 (nem sempre recuperado): o validador do pipeline contém tudo => exit 0
    assert codigo == 0 and "CONT" in _marcas(saida.out) and not {"SEM-ESCALAR", "LEAK"} & _marcas(saida.out), saida.out
    linhas = json.loads(arq.read_text(encoding="utf-8"))
    casos = linhas["casos"]
    assert linhas["total"] == len(casos) >= 17 and all(c["seguro"] for c in casos)
    assert "VAZARAM" in saida.out


def test_qa_avaliar_geracao_detecta_vazamento_do_pipeline(monkeypatch, capsys, llm_falso):
    """Se o pipeline deixasse passar uma violação, o script tem que sair com exit 1 (senão não serve como gate)."""
    import src.main as main

    monkeypatch.setenv("ANTHROPIC_API_KEY", "chave-de-teste")
    monkeypatch.setattr(main, "triar", lambda t, p, dry_run=False: {"destino": "rascunho_para_revisao", "escalar": False,
                                                                       "resposta_sugerida": "Reembolso aprovado", "fontes": []})
    codigo, saida = _rodar(monkeypatch, capsys, "qa.avaliar_geracao", "--so-adversariais")
    assert codigo == 1 and "LEAK" in _marcas(saida.out)


def test_qa_avaliar_geracao_acusa_modelo_que_nao_escala_quando_deve(monkeypatch, capsys):
    """Pipeline hipotético que devolve rascunho VÁLIDO para pedido de reembolso: o contrato passa, mas a regra
    de negócio (escalar) foi violada — só a lente de escalonamento pega isso."""
    import src.main as main
    from src.recuperar import recuperar

    def triar_ingenuo(ticket, plano, dry_run=False):
        ids = [t.id for t in recuperar(ticket, plano)]
        if not ids:
            return {"destino": "fila_humana", "escalar": True}
        return saida_valida(categoria="billing", resposta_sugerida=f"Veja o artigo [{ids[0]}].", fontes=[ids[0]],
                            destino="rascunho_para_revisao")

    monkeypatch.setenv("ANTHROPIC_API_KEY", "chave-de-teste")
    monkeypatch.setattr(main, "triar", triar_ingenuo)
    codigo, saida = _rodar(monkeypatch, capsys, "qa.avaliar_geracao", "--so-adversariais")
    assert codigo == 1 and "SEM-ESCALAR" in _marcas(saida.out), saida.out


def test_qa_avaliar_geracao_crash_do_pipeline_conta_como_vazamento(monkeypatch, capsys):
    import src.main as main

    def explode(ticket, plano, dry_run=False):
        raise RuntimeError("falha inesperada")

    monkeypatch.setenv("ANTHROPIC_API_KEY", "chave-de-teste")
    monkeypatch.setattr(main, "triar", explode)
    codigo, saida = _rodar(monkeypatch, capsys, "qa.avaliar_geracao", "--so-adversariais")
    assert codigo == 1 and "LEAK" in _marcas(saida.out) and "crash: RuntimeError" in saida.out


def test_qa_avaliar_geracao_modo_completo_inclui_o_golden(monkeypatch, capsys, llm_falso):
    from qa.metricas import carregar_golden

    monkeypatch.setenv("ANTHROPIC_API_KEY", "chave-de-teste")
    llm_falso.responder(saida_valida())
    _, saida = _rodar(monkeypatch, capsys, "qa.avaliar_geracao")
    esperados = len([c for c in carregar_golden() if c["ticket"].strip()]) + 18
    assert f"{esperados} tickets" in saida.out
