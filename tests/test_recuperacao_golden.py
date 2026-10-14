"""Qualidade da recuperação medida contra o golden set (`qa/golden_tickets.json`).

Casos com status 'limitacao_conhecida' são xfail(strict=True): documentam um defeito real (README, "Crítica
honesta") e FALHAM o build quando alguém o corrige — sinal para promover o caso a 'ok'.
"""
import pytest

from qa.metricas import avaliar_caso, carregar_golden, resumo
from src import config
from src.recuperar import recuperar

GOLDEN = carregar_golden()
OK = [c for c in GOLDEN if c["status"] == "ok"]
LIMITACOES = [c for c in GOLDEN if c["status"] != "ok"]

pytestmark = pytest.mark.usefixtures("base_indexada")


def _ids(caso):
    return [c["id"] for c in caso]


@pytest.mark.parametrize("caso", OK, ids=_ids(OK))
def test_golden_caso(caso):
    r = avaliar_caso(caso)
    assert r["acertou"], f"{caso['ticket']!r} ({caso['plano']}): esperado {caso['esperado']}, veio {list(zip(r['got'], r['dist']))}"


@pytest.mark.parametrize(
    "caso",
    [pytest.param(c, marks=pytest.mark.xfail(strict=True, reason=c.get("nota", "limitação conhecida"))) for c in LIMITACOES],
    ids=_ids(LIMITACOES),
)
def test_golden_limitacao_conhecida(caso):
    assert avaliar_caso(caso)["acertou"]


def test_metricas_agregadas_nao_regridem():
    """Pisos medidos em 14/10/2026 (recall@4=1,00; MRR=0,94; top-1=0,89), com folga para ruído de modelo."""
    r = resumo([avaliar_caso(c) for c in GOLDEN])
    assert r[f"recall@{config.TOP_K}"] >= 0.95
    assert r["MRR"] >= 0.85
    assert r["top1"] >= 0.80


# ---- invariantes: valem para QUALQUER ticket e plano, não só os do golden ----
TICKETS_QUALQUER = [c["ticket"] for c in GOLDEN] + ["asdfgh", "123456", "😀😀😀", "x" * 5000]


@pytest.mark.parametrize("plano", list(config.RANK_PLANO))
def test_invariante_plano_nunca_vaza(plano):
    teto = config.RANK_PLANO[plano]
    for t in TICKETS_QUALQUER:
        for tr in recuperar(t, plano):
            assert tr.meta["min_plan_rank"] <= teto, f"{tr.id} (plano {tr.meta['min_plan_rank']}) vazou para {plano}: {t[:40]!r}"


def test_invariante_deprecated_nunca_recuperado():
    for plano in config.RANK_PLANO:
        for t in TICKETS_QUALQUER + ["login com Google", "Entrar com Google parou de funcionar"]:
            assert all(tr.meta["status"] == "active" for tr in recuperar(t, plano))


def test_invariante_corte_e_topk_respeitados():
    for t in TICKETS_QUALQUER:
        r = recuperar(t, "enterprise")
        assert len(r) <= config.TOP_K
        assert all(tr.distancia <= config.MAX_DISTANCIA for tr in r)
        assert [tr.distancia for tr in r] == sorted(tr.distancia for tr in r), "resultado fora de ordem de relevância"


def test_topk_parametro_e_respeitado():
    assert len(recuperar("senha", "enterprise", top_k=1)) <= 1


def test_resultado_e_deterministico():
    a = [(t.id, round(t.distancia, 6)) for t in recuperar("esqueci minha senha", "free")]
    b = [(t.id, round(t.distancia, 6)) for t in recuperar("esqueci minha senha", "free")]
    assert a == b


def test_fora_de_escopo_tem_folga_de_seguranca_no_corte():
    """Se o melhor acerto de um fora-de-escopo clássico chegar a < corte+0,05, o limiar está frágil."""
    from src.indexar import get_colecao

    for t in ["qual a receita de bolo de cenoura?", "Vocês têm integração com Jira?"]:
        melhor = get_colecao().query(query_texts=[t], n_results=1, where=None)["distances"][0][0]
        assert melhor >= config.MAX_DISTANCIA + 0.05, f"{t!r}: melhor distância {melhor:.2f} muito perto do corte"


def test_indexar_e_idempotente(base_indexada):
    from src.indexar import get_colecao, indexar

    antes = get_colecao().count()
    indexar()
    assert get_colecao().count() == antes


def test_reindexar_remove_artigo_que_saiu_da_base():
    from src.indexar import get_colecao, indexar

    col = get_colecao()
    meta = {"title": "x", "category": "auth", "doc_type": "faq", "min_plan_rank": 0, "status": "active", "updated_at": "2020-01-01"}
    col.upsert(ids=["kb-fantasma"], documents=["Artigo que não está mais no kb.json"], metadatas=[meta])
    try:
        indexar()
        assert col.get(ids=["kb-fantasma"])["ids"] == []
    finally:
        col.delete(ids=["kb-fantasma"])


# ---- plano: ordem INDEPENDENTE do mapa de produção (o invariante acima compara contra config.RANK_PLANO e,
# se esse mapa for adulterado, ele passa a concordar com o defeito — a mutação 'enterprise = pro' provou isso) ----
ORDEM = ["free", "pro", "enterprise"]


def _artigos_por_plano():
    import json

    kb = json.loads(config.KB_PATH.read_text(encoding="utf-8"))
    return [(a["id"], a["min_plan"], a["title"]) for a in kb if a["status"] == "active"]


@pytest.mark.parametrize("plano", ORDEM)
def test_plano_so_recupera_artigos_do_seu_nivel_ou_inferior(plano):
    nivel = ORDEM.index(plano)
    for id_, min_plan, titulo in _artigos_por_plano():
        achou = id_ in [t.id for t in recuperar(titulo, plano)]
        if ORDEM.index(min_plan) > nivel:
            assert not achou, f"{id_} ({min_plan}) apareceu para o plano {plano}"
        else:
            assert achou, f"{id_} ({min_plan}) deveria ser recuperável no plano {plano} pelo próprio título"


def test_rank_dos_planos_e_estritamente_crescente():
    r = config.RANK_PLANO
    assert r["free"] < r["pro"] < r["enterprise"]


# ---- fronteira do corte, sem modelo: dublê da coleção devolve distâncias exatas ----
def test_corte_e_inclusivo_na_fronteira(monkeypatch):
    import src.recuperar as rec

    class Falsa:
        def query(self, **kw):
            return {"ids": [["a", "b", "c"]], "documents": [["A", "B", "C"]],
                    "distances": [[config.MAX_DISTANCIA, config.MAX_DISTANCIA + 1e-6, config.MAX_DISTANCIA - 1e-6]],
                    "metadatas": [[{}, {}, {}]]}

    monkeypatch.setattr(rec, "get_colecao", lambda: Falsa())
    assert [t.id for t in rec.recuperar("x", "free")] == ["a", "c"]  # == corte entra; acima sai


def test_recuperar_repassa_top_k_e_filtro_ao_banco(monkeypatch):
    import src.recuperar as rec

    vistos = {}

    class Falsa:
        def query(self, **kw):
            vistos.update(kw)
            return {"ids": [[]], "documents": [[]], "distances": [[]], "metadatas": [[]]}

    monkeypatch.setattr(rec, "get_colecao", lambda: Falsa())
    rec.recuperar("x", "pro", top_k=3)
    assert vistos["n_results"] == 3 and vistos["where"] == rec.montar_filtro("pro") and vistos["query_texts"] == ["x"]
