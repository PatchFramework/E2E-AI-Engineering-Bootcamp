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

# persistent conversations
from langgraph.checkpoint.postgres import PostgresSaver
import os

import json

#############################
## Checkpointer Env vars ####
#############################
db = os.environ["MULTI_TURN_POSTGRES_DB"]
user = os.environ["MULTI_TURN_POSTGRES_USER"]
password = os.environ["MULTI_TURN_POSTGRES_PASSWORD"]
HOST = "postgres"
PORT = "5432"

###############
## Helpers ####
###############

def _process_graph_events(chunk):
    """Process debug events to display user friendly state updates"""
    def _is_node_start(chunk):
        return chunk[1].get("type") == "task"
    
    def _tool_to_text(tool_call):
        if tool_call.get("name") == "retrieve_formatted_products":
            return f"Looking for items: {tool_call.get("args").get("query", "")}" 
        elif tool_call.get("name") == "retrieve_prefiltered_reviews":
            return f"Looking for user reviews..." 
        
    if _is_node_start(chunk):
        if chunk[1].get("payload", {}).get("name") == "agent_node":
            return "Planning..."
                
        elif chunk[1].get("payload", {}).get("name") == "tool_node":
            message = " ".join([_tool_to_text(tool_call) for tool_call in chunk[1].get('payload', {}).get('input', {}).messages[-1].tool_calls])
            return message


def string_to_sse(string: str):
    """Converts a string to a Server-Sent Event (SSE)"""
    return f"data: {string}\n\n"

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



#####################
## Agent Execution ##
#####################

def rag_agent_stream_wrapper(question: str, thread_id: str) -> dict:

    qdrant_client = QdrantClient(url="http://qdrant:6333")

    initial_state = {
        "messages": [HumanMessage(content=question)],
        "iteration": 0,
    }

    config = {
        "configurable": {
            "thread_id": thread_id
        }
    }

    with PostgresSaver.from_conn_string(
        f"postgresql://{user}:{password}@{HOST}:{PORT}/{db}"
        ) as checkpointer:
        
        # Compile graph with checkpointing
        app = workflow.compile(checkpointer=checkpointer)

        for chunk in app.stream(
            input=initial_state,
            config=config,
            stream_mode=["debug", "values"]
        ):
            processed_chunk = _process_graph_events(chunk)

            if processed_chunk:
                yield string_to_sse(processed_chunk)

            if chunk[0] == "values":
                result = chunk[1] #update the result over and over again until no new SSE events are generated

    print("Received final result and will extract product information for:", result)

    used_context = []
    for citation in result.get("citations", []):
        citation_id = citation.get("id")
        if citation_id is not None:
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
                                value=citation_id
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
                    product_url = f"https://www.amazon.com/dp/{citation_id}"
                    
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
            
    yield string_to_sse(
        json.dumps(
            {
                "type": "final_answer",
                "data": {
                    "answer": result.get("answer", ""),
                    "used_context": used_context,
                    "trace_id": result.get("trace_id", "")
                }
            }
        )
    )

