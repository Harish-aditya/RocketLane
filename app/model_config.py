"""Optional provider-neutral model setup; deterministic agents are the default."""
from .agents import IntakeAgent, CommunicationAgent


def agents_for_model(model_name=None):
    if not model_name:
        return IntakeAgent(), CommunicationAgent()
    try:
        from langchain.chat_models import init_chat_model
    except ImportError as exc:
        raise ValueError('Model-backed agents require requirements-models.txt and your provider package') from exc
    model = init_chat_model(model_name, temperature=0)
    return IntakeAgent(model), CommunicationAgent(model)
