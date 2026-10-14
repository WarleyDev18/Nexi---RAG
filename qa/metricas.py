"""Métricas de recuperação sobre o golden set (`qa/golden_tickets.json`)."""
import json
from pathlib import Path

from src import config
from src.recuperar import recuperar

GOLDEN = Path(__file__).parent / "golden_tickets.json"


def carregar_golden() -> list[dict]:
    return json.loads(GOLDEN.read_text(encoding="utf-8"))


def avaliar_caso(caso: dict) -> dict:
    trechos = recuperar(caso["ticket"], caso["plano"])
    got = [t.id for t in trechos]
    esp = caso["esperado"]
    if not esp:  # caso "deve vir vazio"
        return {**caso, "got": got, "dist": [round(t.distancia, 2) for t in trechos],
                "acertou": got == [], "rr": None, "recall": None, "top1": None}
    pos = [got.index(e) + 1 for e in esp if e in got]
    return {**caso, "got": got, "dist": [round(t.distancia, 2) for t in trechos],
            "acertou": len(pos) == len(esp),  # todos os esperados apareceram no topK
            "recall": len(pos) / len(esp),
            "rr": (1 / min(pos)) if pos else 0.0,
            "top1": bool(got) and got[0] in esp}


def resumo(resultados: list[dict]) -> dict:
    com = [r for r in resultados if r["recall"] is not None and r["status"] == "ok"]
    vaz = [r for r in resultados if r["recall"] is None and r["status"] == "ok"]
    return {
        "k": config.TOP_K, "corte": config.MAX_DISTANCIA,
        "casos_ok_com_resposta": len(com),
        f"recall@{config.TOP_K}": sum(r["recall"] for r in com) / len(com) if com else None,
        "MRR": sum(r["rr"] for r in com) / len(com) if com else None,
        "top1": sum(r["top1"] for r in com) / len(com) if com else None,
        "fora_de_escopo_corretos": f"{sum(r['acertou'] for r in vaz)}/{len(vaz)}",
        "limitacoes_conhecidas": len([r for r in resultados if r["status"] != "ok"]),
    }
