# internal imports 
from langchain_core.messages import HumanMessage
from .models import *
from .agents import *
from .tools import TOOLS

# langgraph
from langgraph.graph import StateGraph, START, END
from langgraph.prebuilt import ToolNode

# retrievel within the wrapper
from qdrant_client.http.models import MatchValue, FieldCondition, Filter
from qdrant_client.models import VectorParams, Distance, SparseVectorParams, Modifier, PayloadSchemaType, PointStruct, Document, Prefetch, RrfQuery, Rrf


#####################################
## Construct Tools into tool node ###
#####################################
tool_node = ToolNode(TOOLS)


#######################
## Conditional Edges ##
#######################

def intent_router_conditional_edges(state: State) -> dict:
    if state.question_relevant:
        return "agent_node"
    else:
        return "end"

def tool_router_conditional_edges(state: State) -> dict:
    if state.final_answer:
        return "end"
    elif state.iteration >= 3:
        return "end"
    elif len(state.messages[-1].tool_calls) > 0:
        return "tools"
    else:
        return "end"

#################
###   Graph ###
#################

# Instantiate state graph
workflow = StateGraph(State)

# Add nodes
workflow.add_node("intent_router_node", intent_router_node)
workflow.add_node("agent_node", agent_node)
workflow.add_node("tools", tool_node)

# Add edges
workflow.add_edge(START, "intent_router_node")
workflow.add_conditional_edges(
    "intent_router_node",
    intent_router_conditional_edges,
    {
        "agent_node": "agent_node",
        "end": END
    }
)
workflow.add_conditional_edges(
    "agent_node",
    tool_router_conditional_edges,
    {
        "tools": "tools",
        "end": END
    }
)
workflow.add_edge("tools", "agent_node")

# Compile graph
app = workflow.compile()



#####################
## Agent Execution ##
#####################
def run_agent(question: str) -> dict:
    initial_state = {
        "messages": [HumanMessage(content=question)],
        "iteration": 0,
    }

    result = app.invoke(initial_state)
    return result




def rag_agent_wrapper(question):
    qdrant_client = QdrantClient(url="http://qdrant:6333")

    result = run_agent(question)
    print("Received final result and will extract product information for:", result)
    
    used_context = []
    for citation in result.get("citations", []):
        # extract the information for the cited items
        points = qdrant_client.scroll(
            collection_name="Amazon-items-collection-hybrid-search",
            with_payload=True,
            with_vectors=False,
            scroll_filter=Filter(
                must=[
                    FieldCondition(
                        key="parent_asin",
                        match=MatchValue(
                            value=citation.id
                        )
                    )
                ]
            ),
            limit=1
        )
        
        if points and points[0]:
            payload = points[0][0].payload
            description = payload.get("preprocessed_description")
            
            if description:
                img_url = payload.get("image") or None
                product_url = f"https://www.amazon.com/dp/{citation.id}"
                
                rating = payload.get("average_rating")
                if rating is not None:
                    rating = float(rating)
                
                rating_number = payload.get("rating_number")
                if rating_number is not None:
                    rating_number = int(rating_number)

                used_context.append(
                    {
                        "description": description,
                        "img_url": img_url,
                        "product_url": product_url,
                        "rating": rating,
                        "rating_number": rating_number
                    }
                )
            
    return {
        "answer": result["answer"],
        "used_context": used_context
    }

