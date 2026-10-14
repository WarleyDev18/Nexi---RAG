"""Oráculo de contrato: o que uma saída do microagente PRECISA satisfazer para ser segura de propagar.

Usado pelos testes (com LLM falso) e por `qa/avaliar_geracao.py` (com LLM real).
Devolve uma lista de violações em texto; lista vazia = saída válida.
"""
import re

CATEGORIAS = {"auth", "billing", "features", "integrations", "performance", "data", "support", "outro"}
PRIORIDADES = {"urgente", "alta", "normal"}
CHAVES = ("categoria", "prioridade", "escalar", "resposta_sugerida", "fontes")
MAX_PALAVRAS = 120  # regra 6 do prompt

# Regra 4: nunca prometer/confirmar reembolso, desconto ou exceção.
_PROMESSA = re.compile(
    r"(reembols|desconto|exce[cç][aã]o)\w*[^.!?\n]{0,60}"
    r"(aprovad|garantid|confirmad|concedid|liberad|ser[aá] (feito|pago|devolvid))"
    r"|(aprovamos|garantimos|confirmamos|concedemos|vamos (te )?(reembolsar|devolver))",
    re.IGNORECASE,
)
_CITACAO = re.compile(r"\[(kb-\d+)\]")


def validar_saida(res, ids_recuperados) -> list[str]:
    """`res`: dict devolvido por `triar`. `ids_recuperados`: ids que o retriever entregou ao prompt."""
    if not isinstance(res, dict):
        return [f"saída não é objeto JSON (é {type(res).__name__})"]

    v = []
    for k in CHAVES:
        if k not in res:
            v.append(f"chave obrigatória ausente: {k}")

    if "categoria" in res and res["categoria"] not in CATEGORIAS:
        v.append(f"categoria fora do enum: {res['categoria']!r}")
    if "prioridade" in res and res["prioridade"] not in PRIORIDADES:
        v.append(f"prioridade fora do enum: {res['prioridade']!r}")
    if "escalar" in res and not isinstance(res["escalar"], bool):
        v.append(f"escalar não é booleano: {res['escalar']!r}")

    fontes = res.get("fontes", [])
    if not isinstance(fontes, list):
        v.append("fontes não é lista")
        fontes = []
    permitidos = set(ids_recuperados)
    for f in fontes:
        if f not in permitidos:
            v.append(f"fonte citada não foi recuperada: {f!r}")

    resposta = res.get("resposta_sugerida", "")
    if not isinstance(resposta, str):
        v.append("resposta_sugerida não é texto")
        resposta = ""
    for c in _CITACAO.findall(resposta):
        if c not in permitidos:
            v.append(f"citação no texto não foi recuperada: [{c}]")

    escalar = res.get("escalar") is True
    if not escalar:
        if not fontes:
            v.append("resposta sem escalar e sem nenhuma fonte citada")
        if not resposta.strip():
            v.append("resposta vazia sem escalar")
        if _PROMESSA.search(resposta):
            v.append("promete/confirma reembolso, desconto ou exceção sem escalar")
    if len(resposta.split()) > MAX_PALAVRAS:
        v.append(f"resposta com {len(resposta.split())} palavras (máx {MAX_PALAVRAS})")

    destino = res.get("destino")
    if destino is not None and destino != ("fila_humana" if escalar else "rascunho_para_revisao"):
        v.append(f"destino inconsistente com escalar: {destino!r}")
    return v


def seguro_para_propagar(res, ids_recuperados) -> bool:
    """Invariante central: ou vai para humano, ou cumpre o contrato inteiro."""
    if isinstance(res, dict) and res.get("destino") == "fila_humana":
        return True
    return not validar_saida(res, ids_recuperados)
