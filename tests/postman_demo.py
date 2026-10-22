"""Servidor LOCAL de demonstração para Postman, sem conexão com um GLPI real.

Iniciar explicitamente: python -B -m uvicorn tests.postman_demo:app
    --host 127.0.0.1 --port 8001
Não é importado pela aplicação normal. O token abaixo é apenas um marcador
de teste público; não é uma credencial GLPI.
"""
import os

from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError

# A demonstração exercita a validação normal, sem bypass de autenticação.
os.environ['APP_ENV'] = 'test'
os.environ['DEV_BYPASS_API_VALIDATION'] = 'false'

import src.main as application
from src.config.pydantic.chat import ChatResponse
from src.config.pydantic.request import PydanticRequestValidationMiddleware


DEMO_TOKEN = 'somente-simulacao-tarefa3'
ARTICLES = [
    {'id': 9001, 'name': '[SIMULADO] Configurar VPN no Windows',
     'content': '<p>Artigo fictício de teste: configuração de VPN no Windows.</p>'},
    {'id': 9002, 'name': '[SIMULADO] Configurar VPN no macOS',
     'content': '<p>Artigo fictício de teste: configuração de VPN no macOS.</p>'},
    {'id': 9003, 'name': '[SIMULADO] Assinatura de email',
     'content': '<p>Artigo fictício de teste: configurar assinatura de email.</p>'},
    {'id': 9004, 'name': '[SIMULADO] Conexão Wi-Fi',
     'content': '<p>Artigo fictício de teste: conexão wifi.</p>'},
]


class DemoArticlesClient:
    access_token = None

    def knowledgebase_articles(self, *, start, limit):
        if self.access_token != DEMO_TOKEN:
            return {'status_code': 401, 'data': {'detail': 'Token de demonstração inválido.'}}
        return {
            'status_code': 200 if start + limit >= len(ARTICLES) else 206,
            'data': ARTICLES[start:start + limit],
        }


# Troca apenas o cliente externo neste processo de teste. A rota real mantém
# seu processamento, seus modelos Pydantic e a exigência de Bearer original.
application._new_glpi_client = DemoArticlesClient

class SimulationMarker:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        async def send_marked(message):
            if message['type'] == 'http.response.start':
                message = dict(message)
                message['headers'] = list(message.get('headers', [])) + [
                    (b'x-glpi-simulation', b'true'),
                ]
            await send(message)
        await self.app(scope, receive, send_marked)


app = FastAPI(title='SIMULAÇÃO LOCAL — Tarefa 3 — sem GLPI real')
app.add_middleware(PydanticRequestValidationMiddleware)
app.add_middleware(SimulationMarker)
app.add_exception_handler(RequestValidationError, application.pydantic_validation_error_handler)
app.add_api_route('/api/chat', application.chat, methods=['POST'], response_model=ChatResponse)


@app.get('/health')
def health():
    return {'status': 'ok', 'modo': 'SIMULACAO', 'glpi_real': False}
