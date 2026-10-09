"""Fluxo completo: ticket -> recuperar -> montar prompt -> LLM -> roteamento.

Uso:
  python -m src.indexar
  python -m src.main "Esqueci a senha e não consigo entrar" --plano free
  python -m src.main "..." --dry-run      # mostra recuperação + prompt, sem chamar o LLM
"""
import argparse
import json

from src.gerar import gerar, montar_prompt
from src.recuperar import recuperar


def triar(ticket: str, plano: str, dry_run: bool = False) -> dict:
    trechos = recuperar(ticket, plano)
    prompt = montar_prompt(ticket, plano, trechos)
    if dry_run:
        return {"trechos": [(t.id, round(t.distancia, 3)) for t in trechos], "prompt": prompt}

    resultado = gerar(prompt)
    # Guarda-corpo determinístico (não depende do LLM): sem contexto => humano.
    if not trechos:
        resultado["escalar"] = True
        resultado.setdefault("motivo_escalar", "nenhum artigo relevante recuperado")
    # Propagação: em produção, isto iria para a fila humana ou viraria rascunho no helpdesk.
    resultado["destino"] = "fila_humana" if resultado.get("escalar") else "rascunho_para_revisao"
    return resultado


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("ticket")
    ap.add_argument("--plano", default="free", choices=["free", "pro", "enterprise"])
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    out = triar(a.ticket, a.plano, a.dry_run)
    if a.dry_run:
        print("Recuperados (id, distância):", out["trechos"], "\n\n" + out["prompt"])
    else:
        print(json.dumps(out, ensure_ascii=False, indent=2))
