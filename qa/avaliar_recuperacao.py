"""Relatório de qualidade da recuperação. Uso:  python -m qa.avaliar_recuperacao [--json]

Não chama LLM. Indexa a base, roda o golden set e imprime recall@K, MRR, top-1 e os casos que falham.
"""
import argparse
import json
import sys

from qa.metricas import avaliar_caso, carregar_golden, resumo
from src.indexar import indexar

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", action="store_true", help="saída em JSON (para CI/comparar execuções)")
    a = ap.parse_args()
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    indexar()
    res = [avaliar_caso(c) for c in carregar_golden()]
    if a.json:
        print(json.dumps({"resumo": resumo(res), "casos": res}, ensure_ascii=False, indent=2))
        raise SystemExit(0)

    for r in res:
        marca = "OK  " if r["acertou"] else ("LIM " if r["status"] != "ok" else "FAIL")
        print(f"{marca} {r['id']} [{r['plano']:10}] {r['ticket'][:48]!r:52} esp={r['esperado']} got={list(zip(r['got'], r['dist']))}")
    print("\nRESUMO", json.dumps(resumo(res), ensure_ascii=False, indent=2))
    # exit code != 0 só para regressão real (status 'ok' que falhou); limitações conhecidas não quebram
    raise SystemExit(1 if any((not r["acertou"]) and r["status"] == "ok" for r in res) else 0)
