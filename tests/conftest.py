def pytest_configure(config):
    config.addinivalue_line(
        "markers",
        "llm: avaliação com LLM real (requer AGENT_EVAL_MODEL); sem a variável, é pulada.",
    )
