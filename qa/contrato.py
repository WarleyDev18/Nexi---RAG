"""Atalho: o oráculo de contrato vive em `src/validar.py` (é o mesmo código que protege a produção).
Os testes e `qa/avaliar_geracao.py` o importam daqui."""
from src.validar import (CATEGORIAS, CHAVES, MAX_PALAVRAS, PRIORIDADES,  # noqa: F401
                         seguro_para_propagar, validar_saida)
