"""Avaliador de trajetória do agente, no padrão LangChain Evaluation.

Implementa ``AgentTrajectoryEvaluator`` de ``langchain_classic.evaluation``: recebe a
pergunta, a resposta final e os passos intermediários (``(AgentAction, observação)``)
e devolve ``{"score", "value", "reasoning"}``. É determinístico (não usa LLM juiz),
então serve como gate de CI.
"""

import json
import unicodedata
from collections.abc import Iterable, Sequence
from typing import Any

from langchain_classic.evaluation.schema import AgentTrajectoryEvaluator
from langchain_core.agents import AgentAction


def normalizar(texto: str) -> str:
    sem_acento = unicodedata.normalize("NFKD", texto)
    return "".join(c for c in sem_acento if not unicodedata.combining(c)).casefold()


def _argumentos(action: AgentAction) -> dict[str, Any]:
    entrada = action.tool_input
    if isinstance(entrada, dict):
        return entrada
    if isinstance(entrada, str):
        try:
            valor = json.loads(entrada)
        except json.JSONDecodeError:
            return {"__input__": entrada}
        return valor if isinstance(valor, dict) else {"__input__": valor}
    return {"__input__": entrada}


def _contem_argumentos(reais: dict[str, Any], esperados: dict[str, Any]) -> bool:
    # Compara como texto para aceitar ticket_id=123 e ticket_id="123".
    return all(chave in reais and str(reais[chave]).strip() == str(valor) for chave, valor in esperados.items())


class ChamadaFerramentaEvaluator(AgentTrajectoryEvaluator):
    """Verifica se o agente usou a ferramenta certa em vez de inventar a resposta.

    Regras (todas precisam passar para ``score == 1``):

    1. Nenhuma chamada a ferramenta inexistente (pega renomeações quebradas).
    2. Se há ``ferramenta_esperada``: ela foi chamada ao menos uma vez com os
       ``argumentos_esperados``. Se é ``None``: nenhuma ferramenta foi chamada.
    3. Nenhuma ferramenta de escrita foi chamada sem ter sido a esperada
       (efeito colateral não pedido pelo usuário).
    4. A resposta final contém ao menos um trecho de ``resposta_contem_algum``.
    """

    def __init__(self, ferramentas_validas: Iterable[str], ferramentas_escrita: Iterable[str]) -> None:
        self.ferramentas_validas = frozenset(ferramentas_validas)
        self.ferramentas_escrita = frozenset(ferramentas_escrita)

    @property
    def requires_reference(self) -> bool:
        return True

    @property
    def evaluation_name(self) -> str:
        return "chamada_de_ferramenta"

    def _evaluate_agent_trajectory(
        self,
        *,
        prediction: str,
        agent_trajectory: Sequence[tuple[AgentAction, str]],
        input: str,  # noqa: A002
        reference: str | None = None,
        **kwargs: Any,
    ) -> dict:
        esperado = json.loads(reference or "{}")
        ferramenta = esperado.get("ferramenta_esperada")
        args_esperados = esperado.get("argumentos_esperados") or {}
        trechos = esperado.get("resposta_contem_algum") or []

        chamadas = [(action.tool, _argumentos(action)) for action, _ in agent_trajectory]
        nomes = [nome for nome, _ in chamadas]
        falhas: list[str] = []

        desconhecidas = sorted({nome for nome in nomes if nome not in self.ferramentas_validas})
        if desconhecidas:
            falhas.append(f"chamou ferramenta(s) inexistente(s): {desconhecidas}")

        if ferramenta is None:
            if chamadas:
                falhas.append(f"não deveria chamar ferramentas, mas chamou {nomes}")
        elif ferramenta not in nomes:
            falhas.append(f"não chamou {ferramenta!r} (chamadas: {nomes or 'nenhuma'})")
        elif not any(nome == ferramenta and _contem_argumentos(args, args_esperados) for nome, args in chamadas):
            reais = [args for nome, args in chamadas if nome == ferramenta]
            falhas.append(f"chamou {ferramenta!r} com argumentos {reais}, esperado conter {args_esperados}")

        escrita_indevida = sorted({nome for nome in nomes if nome in self.ferramentas_escrita and nome != ferramenta})
        if escrita_indevida:
            falhas.append(f"executou escrita não pedida: {escrita_indevida}")

        if trechos and not any(normalizar(t) in normalizar(prediction or "") for t in trechos):
            falhas.append(f"resposta não contém nenhum de {trechos}: {prediction!r}")

        ok = not falhas
        return {
            "score": int(ok),
            "value": "Y" if ok else "N",
            "reasoning": "ok" if ok else "; ".join(falhas),
        }
