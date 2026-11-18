"""Ferramentas LangChain de leitura no GLPI: status de chamado e base de conhecimento.

Assim como em ``glpi_write_tools``, o LLM informa apenas os argumentos de negócio.
O cliente GLPI autenticado fica preso à fábrica ``criar_ferramentas_leitura`` e não
aparece no schema das ferramentas.
"""

import json
import logging
from typing import Any

import requests
from langchain_core.tools import StructuredTool, ToolException
from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator

from src.article_search import MAX_PERGUNTA
from src.errors import GLPIConfigError, erro_glpi_por_status
from src.knowledge_service import ArticlesFetchError, processar_pergunta

logger = logging.getLogger("glpi_chat_bot")

MSG_RESPOSTA_INESPERADA = "O GLPI retornou uma resposta inesperada."
LIMITE_CONTEUDO_ARTIGO = 1500


class StatusChamadoInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    ticket_id: int = Field(ge=1, description="Número (ID) do chamado no GLPI.")


class PesquisaBaseInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    pergunta: str = Field(
        min_length=1,
        max_length=MAX_PERGUNTA,
        description="Dúvida do usuário, em linguagem natural, a pesquisar na base de conhecimento.",
    )

    @field_validator("pergunta")
    @classmethod
    def validate_pergunta(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("A pergunta não pode ser vazia.")
        return value


def _nome(valor: Any) -> str | None:
    if isinstance(valor, dict):
        valor = valor.get("name")
    texto = str(valor).strip() if valor is not None else ""
    return texto or None


def _responsaveis(chamado: dict[str, Any]) -> list[str]:
    team = chamado.get("team")
    if not isinstance(team, list):
        return []
    return [
        membro.get("display_name") or membro.get("name")
        for membro in team
        if isinstance(membro, dict)
        and membro.get("role") == "assigned"
        and (membro.get("display_name") or membro.get("name"))
    ]


def _mensagem_erro_rede(exc: requests.RequestException) -> str:
    if isinstance(exc, requests.Timeout):
        return "O GLPI demorou demais para responder. Tente novamente em instantes."
    if isinstance(exc, requests.ConnectionError):
        return "Não foi possível conectar ao GLPI. Ele pode estar fora do ar."
    return "Não foi possível concluir a chamada ao GLPI."


def _consultar_status(client: Any, ticket_id: int) -> str:
    try:
        result = client.ticket_detail(ticket_id)
    except requests.RequestException as exc:
        logger.error("Falha de comunicação com o GLPI ao consultar chamado.", exc_info=exc)
        raise ToolException(_mensagem_erro_rede(exc)) from exc
    except ValueError as exc:
        raise ToolException(GLPIConfigError().mensagem) from exc

    status_code = result.get("status_code") if isinstance(result, dict) else None
    if not isinstance(status_code, int):
        raise ToolException(MSG_RESPOSTA_INESPERADA)
    if status_code in (403, 404):
        raise ToolException(f"Chamado #{ticket_id} não encontrado ou sem permissão de acesso.")
    if status_code >= 400:
        raise ToolException(erro_glpi_por_status(status_code, result.get("data")).mensagem)

    chamado = result.get("data")
    if not isinstance(chamado, dict):
        raise ToolException(MSG_RESPOSTA_INESPERADA)

    resumo = {
        "id": chamado.get("id", ticket_id),
        "titulo": _nome(chamado.get("name")),
        "status": _nome(chamado.get("status")),
        "categoria": _nome(chamado.get("category")),
        "aberto_em": chamado.get("date"),
        "atualizado_em": chamado.get("date_mod"),
        "solucionado_em": chamado.get("date_solve"),
        "fechado_em": chamado.get("date_close"),
        "responsaveis": _responsaveis(chamado),
    }
    return json.dumps({k: v for k, v in resumo.items() if v not in (None, [])}, ensure_ascii=False)


def _pesquisar_base(client: Any, pergunta: str) -> str:
    try:
        resultado = processar_pergunta(pergunta, client)
    except ArticlesFetchError as exc:
        raise ToolException(str(exc)) from exc
    except requests.RequestException as exc:
        logger.error("Falha de comunicação com o GLPI ao pesquisar artigos.", exc_info=exc)
        raise ToolException(_mensagem_erro_rede(exc)) from exc
    except ValueError as exc:
        raise ToolException(str(exc)) from exc

    artigos = [
        {
            "id": artigo["id"],
            "titulo": artigo["titulo"],
            "conteudo": artigo["conteudo"][:LIMITE_CONTEUDO_ARTIGO],
        }
        for artigo in resultado["artigos"]
    ]
    if not artigos:
        return json.dumps(
            {"artigos": [], "aviso": "Nenhum artigo relevante encontrado na base de conhecimento."},
            ensure_ascii=False,
        )
    return json.dumps({"artigos": artigos}, ensure_ascii=False)


def _mensagem_validacao(exc: ValidationError) -> str:
    detalhes = "; ".join(
        f"{'.'.join(str(parte) for parte in erro['loc'])}: {erro['msg']}"
        for erro in exc.errors()
    )
    return f"Argumentos inválidos. {detalhes}"


def criar_ferramentas_leitura(client: Any) -> list[StructuredTool]:
    """Cria as ferramentas de leitura presas ao cliente GLPI da requisição atual."""

    def consultar_status_chamado(ticket_id: int) -> str:
        return _consultar_status(client, ticket_id)

    def pesquisar_base_conhecimento(pergunta: str) -> str:
        return _pesquisar_base(client, pergunta)

    return [
        StructuredTool.from_function(
            func=consultar_status_chamado,
            name="consultar_status_chamado",
            description=(
                "Consulta no GLPI o status atual de um chamado pelo número: título, status, "
                "categoria, datas e técnicos responsáveis. Use sempre que o usuário perguntar "
                "sobre a situação, andamento ou responsável de um chamado específico."
            ),
            args_schema=StatusChamadoInput,
            handle_tool_error=True,
            handle_validation_error=_mensagem_validacao,
        ),
        StructuredTool.from_function(
            func=pesquisar_base_conhecimento,
            name="pesquisar_base_conhecimento",
            description=(
                "Pesquisa artigos na base de conhecimento do GLPI. Use para dúvidas de "
                "procedimento ou de como resolver um problema (senha, VPN, e-mail, impressora, "
                "Wi-Fi etc.) antes de orientar o usuário."
            ),
            args_schema=PesquisaBaseInput,
            handle_tool_error=True,
            handle_validation_error=_mensagem_validacao,
        ),
    ]
