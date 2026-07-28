from a2a.server.apps import A2AStarletteApplication
from a2a.server.request_handlers import DefaultRequestHandler
from a2a.types import AgentCard, AgentSkill
from a2a.client import A2AClient

def serve(executor, store):
    card = AgentCard(name="research", skills=[AgentSkill(id="search")])
    handler = DefaultRequestHandler(agent_executor=executor, task_store=store)
    return A2AStarletteApplication(agent_card=card, http_handler=handler)

async def delegate(url, msg):
    client = A2AClient(url=url)
    return await client.send_message(msg)
