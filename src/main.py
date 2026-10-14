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
from src.validar import CATEGORIAS, PRIORIDADES, validar_saida


def _valido(valor, conjunto) -> bool:
    return isinstance(valor, str) and valor in conjunto


def triar(ticket: str, plano: str, dry_run: bool = False) -> dict:
    trechos = recuperar(ticket, plano)
    prompt = montar_prompt(ticket, plano, trechos)
    if dry_run:
        return {"trechos": [(t.id, round(t.distancia, 3)) for t in trechos], "prompt": prompt}

    # Guarda-corpo 1 (determinístico, antes do LLM): sem contexto => humano, sem gastar token nem arriscar alucinação.
    if not trechos:
        return {"categoria": "outro", "prioridade": "normal", "escalar": True,
                "motivo_escalar": "nenhum artigo relevante recuperado", "resposta_sugerida": "",
                "fontes": [], "destino": "fila_humana"}

    resultado = gerar(prompt)
    # Guarda-corpo 2 (determinístico, depois do LLM): prompt não é garantia. Saída fora do contrato
    # (chave ausente, enum, fonte que não foi recuperada, >120 palavras, promessa de reembolso...) nunca
    # vira rascunho: vai para o humano, que recebe o motivo e a saída original para revisar.
    violacoes = validar_saida(resultado, [t.id for t in trechos])
    if violacoes:
        resultado = {"categoria": resultado["categoria"] if _valido(resultado.get("categoria"), CATEGORIAS) else "outro",
                     "prioridade": resultado["prioridade"] if _valido(resultado.get("prioridade"), PRIORIDADES) else "normal",
                     "escalar": True,
                     "motivo_escalar": resultado["motivo_escalar"] if "bruto" in resultado  # já explicado por gerar()
                     else "saída do LLM reprovada na validação: " + "; ".join(violacoes),
                     "resposta_sugerida": "", "fontes": [], "violacoes": violacoes, "saida_rejeitada": resultado}
    # Propagação: em produção, isto iria para a fila humana ou viraria rascunho no helpdesk.
    resultado["destino"] = "fila_humana" if resultado["escalar"] else "rascunho_para_revisao"
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
