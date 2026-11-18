"""Regressão de comportamento do agente: ferramenta certa para cada pergunta.

Dois modos, mesmos 10 casos (``agent_eval/casos.py``) e mesmo avaliador LangChain:

* ``roteiro`` (sempre roda, offline): modelo determinístico. Quebra quando uma
  ferramenta é renomeada/removida, muda de schema ou para de executar.
* ``llm`` (opt-in, marcador ``llm``): modelo real definido em ``AGENT_EVAL_MODEL``.
  Quebra quando uma mudança no prompt ou nas descrições das ferramentas faz o
  modelo escolher errado ou responder sem consultar o GLPI.

    python -m pytest tests/test_agent_eval.py                 # só offline
    AGENT_EVAL_MODEL=openai:gpt-4.1-mini python -m pytest tests/test_agent_eval.py -m llm
"""

import json

import pytest

from agent_eval.avaliador import ChamadaFerramentaEvaluator
from agent_eval.casos import CASOS, FERRAMENTAS_ESCRITA, STATUS, CasoAgente
from agent_eval.dubles import (
    GLPIClientStub,
    ModeloInventaResposta,
    ModeloRoteirizado,
    contexto_teste,
    modelo_real,
    resumo_trajetoria,
)
from src.agent import criar_agente, criar_ferramentas
from src.prompts import SYSTEM_PROMPT


def _nomes_ferramentas() -> set[str]:
    return {t.name for t in criar_ferramentas(contexto_teste(GLPIClientStub()))}


@pytest.fixture(scope="module")
def avaliador() -> ChamadaFerramentaEvaluator:
    return ChamadaFerramentaEvaluator(_nomes_ferramentas(), FERRAMENTAS_ESCRITA)


@pytest.fixture(
    scope="module",
    params=["roteiro", pytest.param("llm", marks=pytest.mark.llm)],
)
def fabrica_modelo(request):
    if request.param == "roteiro":
        roteiro = {caso.pergunta: caso.chamadas_roteiro for caso in CASOS}
        return lambda: ModeloRoteirizado(roteiro=roteiro)
    modelo = modelo_real()
    if modelo is None:
        pytest.skip("Defina AGENT_EVAL_MODEL para avaliar com um LLM real.")
    return lambda: modelo


def _executar(modelo, pergunta: str) -> tuple[dict, GLPIClientStub]:
    client = GLPIClientStub()
    resultado = criar_agente(modelo, contexto_teste(client)).invoke({"pergunta": pergunta})
    return resultado, client


def _avaliar(avaliador, caso: CasoAgente, resultado: dict) -> dict:
    return avaliador.evaluate_agent_trajectory(
        input=caso.pergunta,
        prediction=resultado["output"],
        agent_trajectory=resultado["intermediate_steps"],
        reference=json.dumps(caso.como_referencia()),
    )


def test_suite_tem_dez_perguntas_incluindo_as_obrigatorias():
    perguntas = [caso.pergunta for caso in CASOS]
    assert len(perguntas) == 10
    assert len(set(perguntas)) == 10
    assert "Me dê o status do chamado 123" in perguntas
    assert "Como reseto minha senha?" in perguntas


def test_ferramentas_esperadas_existem_no_agente():
    # Renomear/remover uma ferramenta sem atualizar os casos falha aqui, com mensagem clara.
    esperadas = {caso.ferramenta_esperada for caso in CASOS} - {None}
    assert esperadas <= _nomes_ferramentas()


def test_prompt_orienta_o_uso_das_ferramentas():
    assert "consultar_status_chamado" in SYSTEM_PROMPT
    assert "pesquisar_base_conhecimento" in SYSTEM_PROMPT


@pytest.mark.parametrize("caso", CASOS, ids=lambda caso: caso.id)
def test_agente_chama_a_ferramenta_correta(caso: CasoAgente, fabrica_modelo, avaliador):
    resultado, client = _executar(fabrica_modelo(), caso.pergunta)
    avaliacao = _avaliar(avaliador, caso, resultado)

    assert avaliacao["score"] == 1, (
        f"{avaliacao['reasoning']}\ntrajetória: {resumo_trajetoria(resultado['intermediate_steps'])}"
    )
    if caso.ferramenta_esperada is None:
        assert client.calls == [], "o agente não deveria ter consultado o GLPI"


# --- O avaliador precisa reprovar os comportamentos ruins (senão ele não protege nada). ---

CASO_STATUS = next(caso for caso in CASOS if caso.pergunta == "Me dê o status do chamado 123")


def test_avaliador_reprova_resposta_inventada_sem_ferramenta(avaliador):
    resultado, client = _executar(ModeloInventaResposta(), CASO_STATUS.pergunta)
    avaliacao = _avaliar(avaliador, CASO_STATUS, resultado)

    assert avaliacao["score"] == 0
    assert "não chamou 'consultar_status_chamado'" in avaliacao["reasoning"]
    assert client.calls == []


def test_avaliador_reprova_ferramenta_errada(avaliador):
    modelo = ModeloRoteirizado(roteiro={
        CASO_STATUS.pergunta: [{"name": "pesquisar_base_conhecimento", "args": {"pergunta": "chamado 123"}}],
    })
    avaliacao = _avaliar(avaliador, CASO_STATUS, _executar(modelo, CASO_STATUS.pergunta)[0])

    assert avaliacao["score"] == 0
    assert "não chamou" in avaliacao["reasoning"]


def test_avaliador_reprova_numero_de_chamado_errado(avaliador):
    modelo = ModeloRoteirizado(roteiro={CASO_STATUS.pergunta: [{"name": STATUS, "args": {"ticket_id": 321}}]})
    avaliacao = _avaliar(avaliador, CASO_STATUS, _executar(modelo, CASO_STATUS.pergunta)[0])

    assert avaliacao["score"] == 0
    assert "argumentos" in avaliacao["reasoning"]


def test_avaliador_reprova_escrita_nao_pedida(avaliador):
    modelo = ModeloRoteirizado(roteiro={CASO_STATUS.pergunta: [
        {"name": STATUS, "args": {"ticket_id": 123}},
        {"name": "aprovar_solucao_chamado", "args": {"ticket_id": 123}},
    ]})
    avaliacao = _avaliar(avaliador, CASO_STATUS, _executar(modelo, CASO_STATUS.pergunta)[0])

    assert avaliacao["score"] == 0
    assert "escrita não pedida" in avaliacao["reasoning"]


def test_avaliador_reprova_ferramenta_inexistente(avaliador):
    modelo = ModeloRoteirizado(roteiro={CASO_STATUS.pergunta: [{"name": "status_chamado", "args": {"ticket_id": 123}}]})
    avaliacao = _avaliar(avaliador, CASO_STATUS, _executar(modelo, CASO_STATUS.pergunta)[0])

    assert avaliacao["score"] == 0
    assert "inexistente" in avaliacao["reasoning"]
