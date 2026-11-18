"""As 10 perguntas simuladas e o comportamento esperado do agente para cada uma.

Este arquivo é o contrato de comportamento: se uma mudança no prompt ou nas
ferramentas fizer o agente deixar de chamar a ferramenta certa, o teste quebra.
Ao renomear uma ferramenta de propósito, atualize os nomes aqui também.
"""

from dataclasses import dataclass, field
from typing import Any

STATUS = "consultar_status_chamado"
BASE = "pesquisar_base_conhecimento"
COMENTAR = "adicionar_comentario_chamado"
APROVAR = "aprovar_solucao_chamado"

FERRAMENTAS_ESCRITA = frozenset({COMENTAR, APROVAR})


@dataclass(frozen=True)
class CasoAgente:
    id: str
    pergunta: str
    # Ferramenta que o agente PRECISA chamar. None = não deve chamar nenhuma.
    ferramenta_esperada: str | None
    # Subconjunto dos argumentos que a chamada precisa ter (ex.: ticket_id).
    argumentos_esperados: dict[str, Any] = field(default_factory=dict)
    # A resposta final precisa conter ao menos um destes trechos (sem acento/caixa).
    # Garante que a resposta veio da ferramenta e não foi inventada.
    resposta_contem_algum: tuple[str, ...] = ()
    # Argumentos que o modelo roteirizado (modo offline) envia. Padrão: os esperados.
    argumentos_roteiro: dict[str, Any] | None = None

    @property
    def chamadas_roteiro(self) -> list[dict[str, Any]]:
        if self.ferramenta_esperada is None:
            return []
        args = self.argumentos_roteiro if self.argumentos_roteiro is not None else self.argumentos_esperados
        return [{"name": self.ferramenta_esperada, "args": dict(args)}]

    def como_referencia(self) -> dict[str, Any]:
        return {
            "ferramenta_esperada": self.ferramenta_esperada,
            "argumentos_esperados": self.argumentos_esperados,
            "resposta_contem_algum": list(self.resposta_contem_algum),
        }


CASOS: list[CasoAgente] = [
    CasoAgente(
        id="status_chamado_123",
        pergunta="Me dê o status do chamado 123",
        ferramenta_esperada=STATUS,
        argumentos_esperados={"ticket_id": 123},
        resposta_contem_algum=("em atendimento",),
    ),
    CasoAgente(
        id="resetar_senha",
        pergunta="Como reseto minha senha?",
        ferramenta_esperada=BASE,
        argumentos_roteiro={"pergunta": "redefinir senha"},
    ),
    CasoAgente(
        id="chamado_4567_resolvido",
        pergunta="O chamado 4567 já foi resolvido?",
        ferramenta_esperada=STATUS,
        argumentos_esperados={"ticket_id": 4567},
        resposta_contem_algum=("solucionado", "resolvido"),
    ),
    CasoAgente(
        id="situacao_ticket_89",
        pergunta="Qual a situação do meu ticket #89?",
        ferramenta_esperada=STATUS,
        argumentos_esperados={"ticket_id": 89},
        resposta_contem_algum=("pendente",),
    ),
    CasoAgente(
        id="responsavel_chamado_321",
        pergunta="Quem é o técnico responsável pelo chamado 321?",
        ferramenta_esperada=STATUS,
        argumentos_esperados={"ticket_id": 321},
        resposta_contem_algum=("carlos",),
    ),
    CasoAgente(
        id="configurar_vpn",
        pergunta="Como configuro a VPN no meu notebook?",
        ferramenta_esperada=BASE,
        argumentos_roteiro={"pergunta": "configurar VPN"},
    ),
    CasoAgente(
        id="impressora_nao_imprime",
        pergunta="Minha impressora não está imprimindo, o que eu faço?",
        ferramenta_esperada=BASE,
        argumentos_roteiro={"pergunta": "impressora não imprime"},
    ),
    CasoAgente(
        id="email_no_celular",
        pergunta="Como acesso meu e-mail corporativo pelo celular?",
        ferramenta_esperada=BASE,
        argumentos_roteiro={"pergunta": "e-mail corporativo celular"},
    ),
    CasoAgente(
        id="comentar_chamado_55",
        pergunta='Adicione o comentário "Já reiniciei o computador" no chamado 55',
        ferramenta_esperada=COMENTAR,
        argumentos_esperados={"ticket_id": 55},
        argumentos_roteiro={"ticket_id": 55, "mensagem": "Já reiniciei o computador"},
    ),
    CasoAgente(
        id="status_sem_numero",
        pergunta="Qual o status do meu chamado?",
        # Regra 2 do prompt: sem número, o agente pede o número e não chuta um ID.
        ferramenta_esperada=None,
        resposta_contem_algum=("numero",),
    ),
]
