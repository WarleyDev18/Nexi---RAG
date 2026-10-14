"""Teste de mutação artesanal: mede se a suíte PEGA defeitos, não só se executa linhas.

Cada mutante troca UM trecho de código de produção por uma versão defeituosa plausível (operador invertido,
guarda removida, constante alterada), roda o pytest e espera que a suíte FALHE ("morto"). Mutante que passa
("sobrevivente") = buraco nos testes (ou mutante equivalente: justifique no campo `equivalente`).

Uso:  python -m qa.mutacao [--so ARQUIVO] [--lista] [--saida mut.json]      (leva minutos: 1 pytest por mutante)
O arquivo é SEMPRE restaurado (try/finally); se interromper com Ctrl+C à força, rode `git checkout src/`.
"""
import argparse
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent

# (arquivo, trecho original — deve ocorrer EXATAMENTE 1 vez, trecho defeituoso, descrição, equivalente?)
MUTANTES = [
    # --- recuperação: filtros e corte ---
    ("src/recuperar.py", '{"min_plan_rank": {"$lte": rank}}', '{"min_plan_rank": {"$lte": rank + 1}}', "filtro de plano deixa passar 1 nível acima", None),
    ("src/recuperar.py", '{"status": {"$eq": "active"}}', '{"status": {"$ne": "zzz"}}', "filtro de status removido (deprecated volta)", None),
    ("src/recuperar.py", "t.distancia <= config.MAX_DISTANCIA", "t.distancia <= 99", "corte de distância desligado", None),
    ("src/recuperar.py", "t.distancia <= config.MAX_DISTANCIA", "t.distancia < config.MAX_DISTANCIA", "corte exclusivo em vez de inclusivo", None),
    ("src/recuperar.py", "if plano_cliente not in config.RANK_PLANO:", "if False:", "validação de plano removida", None),
    ("src/recuperar.py", "if not isinstance(ticket, str):", "if False:", "validação de tipo do ticket removida", None),
    ("src/recuperar.py", "n_results=top_k", "n_results=1", "top_k ignorado", None),
    # --- configuração ---
    ("src/config.py", "MAX_DISTANCIA = 0.70", "MAX_DISTANCIA = 0.60", "corte mais rígido (perde acertos)", None),
    ("src/config.py", "MAX_DISTANCIA = 0.70", "MAX_DISTANCIA = 0.80", "corte frouxo (deixa passar ruído)", None),
    ("src/config.py", "TOP_K = 4", "TOP_K = 1", "topK mínimo", None),
    ("src/config.py", '"enterprise": 2', '"enterprise": 1', "enterprise com o mesmo rank de pro", None),
    # --- indexação ---
    ("src/indexar.py", '"min_plan_rank": config.RANK_PLANO[artigo["min_plan"]]', '"min_plan_rank": 0', "todo artigo vira plano Free", None),
    ("src/indexar.py", '"status": artigo["status"]', '"status": "active"', "deprecated indexado como ativo", None),
    ("src/indexar.py", "if obsoletos:", "if False:", "artigos removidos continuam no índice", None),
    ("src/indexar.py", "def indexar() -> int:\n    artigos", "def indexar() -> int:\n    return 0\n    artigos", "indexar não faz nada", None),
    # --- prompt e geração ---
    ("src/gerar.py", "temperature=0,", "temperature=1,", "temperatura alta", None),
    ("src/gerar.py", "return _TAG_TICKET.sub(", "return ticket; _TAG_TICKET.sub(", "delimitador do ticket não é neutralizado", None),
    ("src/gerar.py", "if not isinstance(saida, dict):", "if False:", "JSON não-objeto aceito", None),
    ("src/gerar.py", "REGRAS = \"\"\"Você é um assistente", "REGRAS = \"\"\"Você é um poeta", "prompt de sistema alterado", None),
    ("src/gerar.py", '"prioridade": "urgente|alta|normal"', '"prioridade": "urgente|media|normal"', "enum de prioridade do prompt diverge do contrato", None),
    ("src/gerar.py", "PLANO DO CLIENTE: {plano}", "PLANO DO CLIENTE: free", "plano do cliente fixo no prompt", None),
    # --- roteamento ---
    ("src/main.py", "if not trechos:", "if False:", "guarda 'sem contexto' removida", None),
    ("src/main.py", "if violacoes:", "if False:", "validação pós-LLM removida", None),
    ("src/main.py", '"fila_humana" if resultado["escalar"] else "rascunho_para_revisao"', '"rascunho_para_revisao" if resultado["escalar"] else "fila_humana"', "destino invertido", None),
    ("src/main.py", '"escalar": True,\n                     "motivo_escalar"', '"escalar": False,\n                     "motivo_escalar"', "saída reprovada não escala", None),
    ("src/main.py", '"resposta_sugerida": "", "fontes": [], "violacoes": violacoes', '"resposta_sugerida": resultado.get("resposta_sugerida", ""), "fontes": [], "violacoes": violacoes', "resposta reprovada sobra no rascunho", None),
    # --- validação ---
    ("src/validar.py", "MAX_PALAVRAS = 120", "MAX_PALAVRAS = 1000", "limite de palavras frouxo", None),
    ("src/validar.py", "        if f not in permitidos:", "        if False:", "fonte não recuperada aceita", None),
    ("src/validar.py", "        if c not in permitidos:", "        if False:", "citação [kb-x] não recuperada aceita", None),
    ("src/validar.py", "        if not fontes:", "        if False:", "resposta sem fonte aceita", None),
    ("src/validar.py", "        if _PROMESSA.search(resposta):", "        if False:", "promessa de reembolso aceita", None),
    ("src/validar.py", "    if vazou_instrucoes(resposta):", "    if False:", "vazamento do prompt aceito", None),
    ("src/validar.py", 'if "escalar" in res and not isinstance(res["escalar"], bool):', "if False:", "escalar não-booleano aceito", None),
    ("src/validar.py", "for i in range(len(p) - 4)}", "for i in range(len(p) - 4) if False}", "n-gramas das regras vazios", None),
    ("src/validar.py", '(aprovad|garantid|confirmad|concedid|liberad|', '(zzzzz|garantid|confirmad|concedid|liberad|', "regex de promessa sem 'aprovad'", None),
]


def aplicar(arquivo: str, original: str, mutado: str):
    caminho = RAIZ / arquivo
    texto = caminho.read_text(encoding="utf-8")
    if texto.count(original) != 1:
        raise ValueError(f"{arquivo}: trecho aparece {texto.count(original)}x (esperado 1): {original[:50]!r}")
    caminho.write_text(texto.replace(original, mutado), encoding="utf-8", newline="\n")
    return caminho, texto


def rodar_suite() -> int:
    shutil.rmtree(RAIZ / ".chroma", ignore_errors=True)  # cada execução começa com índice limpo: mutante de indexação não contamina o próximo
    env = {**os.environ, "HF_HUB_OFFLINE": "1", "PYTHONUTF8": "1"}
    p = subprocess.run([sys.executable, "-m", "pytest", "-q", "-x", "--no-header", "-p", "no:cacheprovider",
                        "--deselect", "tests/test_desempenho.py"], cwd=RAIZ, env=env, capture_output=True, text=True)
    return p.returncode


if __name__ == "__main__":  # pragma: no cover — orquestra pytest filho; as funções puras têm teste em tests/test_mutacao.py
    ap = argparse.ArgumentParser()
    ap.add_argument("--so", help="só mutantes deste arquivo (ex.: src/validar.py)")
    ap.add_argument("--indices", help="só estes mutantes, pelos números de --lista (ex.: 3,5,10)")
    ap.add_argument("--lista", action="store_true")
    ap.add_argument("--saida")
    a = ap.parse_args()
    alvo = [m for m in MUTANTES if not a.so or m[0] == a.so]
    if a.indices:
        pedidos = {int(x) for x in a.indices.split(",")}
        alvo = [m for i, m in enumerate(MUTANTES) if i in pedidos]  # índice = posição em MUTANTES (começa em 0, como --lista sem --so)
    if a.lista:
        for i, (f, _, _, d, _) in enumerate(alvo):
            print(f"{i:2} {f:18} {d}")
        raise SystemExit(0)

    base = rodar_suite()
    if base != 0:
        raise SystemExit("a suíte JÁ falha sem mutação: corrija antes de medir mutação")

    resultado = []
    for i, (arquivo, original, mutado, desc, equiv) in enumerate(alvo, 1):
        try:
            caminho, texto_orig = aplicar(arquivo, original, mutado)
        except ValueError as e:
            resultado.append({"arquivo": arquivo, "desc": desc, "status": "INVALIDO", "detalhe": str(e)})
            print(f"[{i}/{len(alvo)}] INVALIDO  {desc}: {e}")
            continue
        try:
            rc = rodar_suite()
        finally:
            caminho.write_text(texto_orig, encoding="utf-8", newline="\n")
        status = "MORTO" if rc == 1 else "SOBREVIVEU" if rc == 0 else "ERRO"  # rc>=2: erro de coleta/interno, não conta como morto
        resultado.append({"arquivo": arquivo, "desc": desc, "status": status, "equivalente": equiv})
        print(f"[{i}/{len(alvo)}] {status:10} {arquivo:18} {desc}" + (f"  (equivalente? {equiv})" if status == "SOBREVIVEU" and equiv else ""))

    validos = [r for r in resultado if r["status"] in {"MORTO", "SOBREVIVEU"}]
    mortos = sum(r["status"] == "MORTO" for r in validos)
    print(f"\nESCORE DE MUTAÇÃO: {mortos}/{len(validos)} = {mortos / max(len(validos), 1):.0%} "
          f"| inválidos/erro: {len(resultado) - len(validos)}")
    for r in resultado:
        if r["status"] != "MORTO":
            print(f"  ! {r['status']}: {r['arquivo']} — {r['desc']}")
    if a.saida:
        Path(a.saida).write_text(json.dumps(resultado, ensure_ascii=False, indent=2), encoding="utf-8")
    raise SystemExit(0 if mortos == len(validos) else 1)
