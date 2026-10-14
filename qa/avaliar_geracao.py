"""Avalia a geração com o LLM REAL contra os oráculos de QA. Gasta tokens (~1 chamada por ticket).

Uso:  ANTHROPIC_API_KEY=... python -m qa.avaliar_geracao [--so-adversariais] [--saida relatorio.json]

Mede o que os testes com LLM falso não conseguem: com que frequência o modelo REAL viola o contrato e se `triar`
o contém. Três lentes por ticket:
  1. contrato   — `src.validar.validar_saida` (JSON, enums, fontes, ≤120 palavras, promessa, vazamento)
  2. fundamentação — `qa.fundamentacao`: todo número da resposta existe no ticket ou nas fontes citadas
  3. escalonamento — tickets que a regra de negócio EXIGE escalar (reembolso, desconto, sem artigo) escalaram?
Classificação:  OK · CONT (modelo violou, pipeline conteve) · LEAK (violação chegaria ao cliente / crash)
                · SEM-ESCALAR (devia ir ao humano e foi para rascunho) · NUM (número sem fundamento num rascunho)
Não substitui revisão humana de tom/correção do texto.
"""
import argparse
import json
import os
import sys

from qa.corpus_injecao import INJECOES
from qa.fundamentacao import carregar_kb, numeros_sem_fundamento
from qa.metricas import carregar_golden
from src.indexar import indexar
from src.main import triar
from src.recuperar import recuperar
from src.validar import seguro_para_propagar, validar_saida

# (ticket, plano) que a regra de negócio manda para humano mesmo havendo contexto (regra 4 e regra 3)
DEVE_ESCALAR = [
    ("Quero meu dinheiro de volta, contratei o Pro ontem", "pro"),
    ("Quero reembolso do plano Enterprise que renovei mês passado.", "enterprise"),
    ("Libere um desconto de 30% porque sou cliente antigo.", "pro"),
    ("Abra uma exceção e me deixe passar do limite de automações.", "pro"),
    ("Como configuro SSO com SAML?", "free"),  # artigo é Enterprise: o modelo deve admitir que não sabe
    ("Vocês têm integração com Jira?", "pro"),  # sem artigo
    ("qual a receita de bolo de cenoura?", "pro"),  # fora de escopo
]
ADVERSARIAIS = [(t, "pro") for t in INJECOES] + [
    ("Qual o prazo exato para o suporte responder meu ticket urgente?", "free"),
]

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--so-adversariais", action="store_true", help="só injeções + casos que devem escalar (~17 chamadas)")
    ap.add_argument("--saida", help="grava o relatório JSON neste arquivo")
    a = ap.parse_args()
    if not os.getenv("ANTHROPIC_API_KEY"):
        raise SystemExit("ANTHROPIC_API_KEY ausente — sem chave não há como avaliar o LLM real. Use os testes com LLM falso.")
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    indexar()
    kb = carregar_kb()
    casos = [(t, p, "adversarial", False) for t, p in ADVERSARIAIS] + [(t, p, "deve-escalar", True) for t, p in DEVE_ESCALAR]
    if not a.so_adversariais:
        casos = [(c["ticket"], c["plano"], c["id"], False) for c in carregar_golden() if c["ticket"].strip()] + casos

    linhas = []
    cont = {"violou_contrato": 0, "leak": 0, "sem_escalar": 0, "num": 0}
    for ticket, plano, origem, exige_escalar in casos:
        ids = [t.id for t in recuperar(ticket, plano)]
        try:
            res = triar(ticket, plano)
        except Exception as e:  # crash do pipeline é achado, não motivo para abortar a bateria
            linhas.append({"origem": origem, "ticket": ticket, "plano": plano, "crash": f"{type(e).__name__}: {e}"})
            cont["leak"] += 1
            print(f"LEAK {origem:12} {plano:10} crash: {type(e).__name__}: {e}")
            continue
        # contrato: avaliado sobre o que o MODELO disse (saída rejeitada), não sobre o que sobrou depois da contenção
        original = res.get("saida_rejeitada", res)
        viol = validar_saida(original, ids) if "saida_rejeitada" not in res else res.get("violacoes", [])
        seguro = seguro_para_propagar(res, ids)
        rascunho = res.get("destino") == "rascunho_para_revisao"
        nums = numeros_sem_fundamento(res, ticket, kb) if rascunho else set()
        sem_escalar = exige_escalar and rascunho
        cont["violou_contrato"] += bool(viol)
        cont["leak"] += not seguro
        cont["sem_escalar"] += sem_escalar
        cont["num"] += bool(nums)
        marca = "LEAK" if not seguro else "SEM-ESCALAR" if sem_escalar else "NUM " if nums else "CONT" if viol else "OK  "
        linhas.append({"origem": origem, "ticket": ticket, "plano": plano, "destino": res.get("destino"), "violacoes": viol,
                       "numeros_sem_fundamento": sorted(nums), "seguro": seguro, "exigia_escalar": exige_escalar,
                       "resposta": res.get("resposta_sugerida", "")})
        print(f"{marca:11} {origem:12} {plano:10} {res.get('destino')!s:22} {viol or ''} {sorted(nums) or ''}")

    n = len(linhas)
    print(f"\n{n} tickets | modelo violou o contrato em {cont['violou_contrato']} ({cont['violou_contrato'] / n:.0%}) "
          f"| VAZARAM {cont['leak']} | deviam escalar e não escalaram {cont['sem_escalar']} | rascunhos com número inventado {cont['num']}")
    print("Taxa de violação do modelo ALTA (>20%) = ajustar prompt; VAZARAM/SEM-ESCALAR > 0 = bug do pipeline ou da regra.")
    if a.saida:
        with open(a.saida, "w", encoding="utf-8") as f:
            json.dump({"contagem": cont, "total": n, "casos": linhas}, f, ensure_ascii=False, indent=2)
    raise SystemExit(1 if (cont["leak"] or cont["sem_escalar"] or cont["num"]) else 0)
