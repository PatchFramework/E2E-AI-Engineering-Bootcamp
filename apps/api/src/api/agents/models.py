from pydantic import BaseModel, Field
from typing import Annotated, List, Any
from operator import add

# state for product Q&A agent
class RagUsedContext(BaseModel):
    id: str = Field(description="ID of the item used to answer the question")
    description: str = Field(description="Description of the item used to answer the question")

# State for product Q&A agent response
class FinalQnAResponse(BaseModel):
    answer: str = Field(description="Final answer to the question")
    citations: list[RagUsedContext] = Field(description="List of items that were relevant to create the final answer")

# State for general response
class FinalAgentResponse(BaseModel):
    answer: str = Field(description="Answer to the question")

# state for Coordinator Agent
class Delegation(BaseModel):
    agent: str = Field(description="Agent to delegate the task to")
    task: str = Field(description="The task that the agent should perform")

class Plan(BaseModel):
    next_agent: str = Field(description="The next agent that should be invoked")
    plan: List[Delegation] = Field(description="A list of delevations to agents with tasks to be performed in sequence")


# overarching global state
class AgentProperties(BaseModel):
    iteration: int = 0
    final_answer: bool = False

class CoordinatorAgentProperties(BaseModel):
    iteration: int = 0
    final_answer: bool = False
    plan: List[Delegation] = []
    next_agent: str = ""


class State(BaseModel):
    messages: Annotated[List[Any], add] = []
    coordinator_agent_state: CoordinatorAgentProperties = CoordinatorAgentProperties()
    product_qna_agent_state: AgentProperties = AgentProperties()
    shopping_cart_agent_state: AgentProperties = AgentProperties()
    warehouse_manager_agent: AgentProperties = AgentProperties()
    citations: list[RagUsedContext] = []
    answer: str = ""
    user_intent: str = ""
    user_id: str = ""
    cart_id: str = ""