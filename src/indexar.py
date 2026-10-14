"""ETAPA 1 — INDEXAÇÃO.

Cada artigo da base vira um documento com 4 partes:
  id        -> estável (kb-001): permite re-indexar sem duplicar (upsert) e citar a fonte
  content   -> "título + corpo": o título carrega a intenção do artigo e melhora o match
  metadata  -> campos usados para FILTRAR e CITAR (ver abaixo)
  embedding -> vetor do `content`, gerado pelo modelo multilíngue local

Metadados escolhidos e por quê:
  category       -> permite inspecionar/medir cobertura por área (auth, billing...)
  doc_type       -> faq/runbook/policy: policy tem peso de regra, runbook é procedimento interno
  min_plan_rank  -> INT (0/1/2), não texto: o Chroma só faz comparação numérica com $lte.
                    Evita sugerir ao cliente Free um recurso que só existe no Enterprise
  status         -> 'deprecated' é indexado de propósito, mas excluído na busca (recuperar.py);
                    assim dá para auditar/reativar sem reindexar
  updated_at     -> vai no prompt para o LLM (e o humano) ver quão fresca é a fonte
  title          -> exibido na citação
"""
import json

import chromadb
from chromadb.utils import embedding_functions

from src import config


def get_colecao():
    """Coleção persistente em disco com o embedding plugado: o Chroma embeda sozinho
    na indexação e na consulta, garantindo o MESMO modelo nas duas pontas."""
    ef = embedding_functions.SentenceTransformerEmbeddingFunction(model_name=config.EMBEDDING_MODEL)
    cliente = chromadb.PersistentClient(path=str(config.CHROMA_DIR))
    return cliente.get_or_create_collection(
        name=config.COLECAO,
        embedding_function=ef,
        metadata={"hnsw:space": "cosine"},  # distância de cosseno (0 = idêntico)
    )


def montar_documento(artigo: dict) -> dict:
    return {
        "id": artigo["id"],
        "content": f"{artigo['title']}\n{artigo['content']}",
        "metadata": {
            "title": artigo["title"],
            "category": artigo["category"],
            "doc_type": artigo["doc_type"],
            "min_plan_rank": config.RANK_PLANO[artigo["min_plan"]],
            "status": artigo["status"],
            "updated_at": artigo["updated_at"],
        },
    }


def indexar() -> int:
    artigos = json.loads(config.KB_PATH.read_text(encoding="utf-8"))
    docs = [montar_documento(a) for a in artigos]
    colecao = get_colecao()
    colecao.upsert(  # upsert: rodar de novo atualiza em vez de duplicar
        ids=[d["id"] for d in docs],
        documents=[d["content"] for d in docs],
        metadatas=[d["metadata"] for d in docs],
    )
    # upsert só acrescenta: artigo removido do kb.json ficaria recuperável (e citável) para sempre
    obsoletos = set(colecao.get()["ids"]) - {d["id"] for d in docs}
    if obsoletos:
        colecao.delete(ids=sorted(obsoletos))
    return len(docs)


if __name__ == "__main__":
    print(f"{indexar()} documentos indexados em {config.CHROMA_DIR}")
