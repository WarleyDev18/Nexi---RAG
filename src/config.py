"""Configuração central do microagente — todos os "botões" do RAG num só lugar."""
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
KB_PATH = RAIZ / "data" / "kb.json"
CHROMA_DIR = RAIZ / ".chroma"
COLECAO = "orbita_kb"

# Modelo multilíngue (PT-BR incluso), roda local, ~120MB, sem custo por chamada.
EMBEDDING_MODEL = "paraphrase-multilingual-MiniLM-L12-v2"

# Modelo de geração. Trocável por variável de ambiente ORBITA_LLM_MODEL.
LLM_MODEL_PADRAO = "claude-haiku-4-5-20251001"

# Recuperação
TOP_K = 4              # ver README: "por que 4"
MAX_DISTANCIA = 0.70   # acima disso = "não achei nada relevante" (calibrado em medições, ver README)

# Ordem dos planos, para filtrar por direito de acesso (Chroma não filtra listas).
RANK_PLANO = {"free": 0, "pro": 1, "enterprise": 2}
