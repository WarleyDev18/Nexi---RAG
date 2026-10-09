"""ETAPA 2 — RECUPERAÇÃO (retrieval).

A query em linguagem natural é o próprio texto do ticket. Busca semântica por
similaridade de cosseno, com filtros de metadados aplicados NO BANCO (pré-filtro),
não depois: filtrar depois de pegar o topK poderia deixar 0 resultados úteis.
"""
from dataclasses import dataclass

from src import config
from src.indexar import get_colecao


@dataclass
class Trecho:
    id: str
    texto: str
    distancia: float
    meta: dict


def montar_filtro(plano_cliente: str) -> dict:
    """1. status == 'active'           -> nunca recuperar artigo descontinuado
    2. min_plan_rank <= rank(plano)  -> só o que o plano do cliente realmente inclui"""
    rank = config.RANK_PLANO[plano_cliente]
    return {"$and": [{"status": {"$eq": "active"}}, {"min_plan_rank": {"$lte": rank}}]}


def recuperar(ticket: str, plano_cliente: str, top_k: int = config.TOP_K) -> list[Trecho]:
    res = get_colecao().query(
        query_texts=[ticket],
        n_results=top_k,
        where=montar_filtro(plano_cliente),
    )
    trechos = [
        Trecho(id=i, texto=d, distancia=dist, meta=m)
        for i, d, dist, m in zip(
            res["ids"][0], res["documents"][0], res["distances"][0], res["metadatas"][0]
        )
    ]
    # topK sempre devolve K itens, mesmo que todos sejam ruins. Sem este corte o LLM
    # recebe lixo e tende a "forçar" uma resposta.
    return [t for t in trechos if t.distancia <= config.MAX_DISTANCIA]
