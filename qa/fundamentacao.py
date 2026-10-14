"""Oráculo de fundamentação: os NÚMEROS da resposta (prazos, limites, valores) têm que vir de algum lugar.

É o tipo de alucinação mais perigoso em suporte ("o link vale 45 minutos") e o único que dá para checar sem
LLM-juiz: todo número citado na `resposta_sugerida` precisa aparecer no ticket do cliente ou nos artigos
citados em `fontes`. Não prova que o texto está CERTO (isso é revisão humana / LLM-juiz), só pega o número
inventado. Fica na suíte de QA, não em produção: um número legítimo reescrito por extenso ("meia hora")
geraria falso positivo e escalaria respostas boas.
"""
import json
import re

from src import config

_NUM = re.compile(r"\d+(?:[.,]\d+)*")


def _numeros(texto: str) -> set[str]:
    """Normaliza '5.000' e '5,000' para '5000'; '2.0' fica '20' nos dois lados, então a comparação é simétrica."""
    return {re.sub(r"[.,]", "", n) for n in _NUM.findall(texto)}


def carregar_kb() -> dict[str, str]:
    artigos = json.loads(config.KB_PATH.read_text(encoding="utf-8"))
    return {a["id"]: f"{a['title']}\n{a['content']}" for a in artigos}


def numeros_sem_fundamento(res: dict, ticket: str, kb: dict[str, str] | None = None) -> set[str]:
    """Números da resposta ausentes do ticket e dos artigos citados. Vazio = fundamentada."""
    kb = kb if kb is not None else carregar_kb()
    resposta = res.get("resposta_sugerida", "") if isinstance(res, dict) else ""
    if not isinstance(resposta, str):
        return set()
    # [kb-001] é id de fonte, não afirmação numérica
    resposta = re.sub(r"\[kb-\d+\]", "", resposta)
    fontes = res.get("fontes", []) if isinstance(res, dict) else []
    base = _numeros(ticket)
    for f in fontes if isinstance(fontes, list) else []:
        base |= _numeros(kb.get(f, "")) if isinstance(f, str) else set()
    return _numeros(resposta) - base
