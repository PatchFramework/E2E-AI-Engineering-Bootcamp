# internal imports 
from langchain_core.messages import HumanMessage
from .models import *
from .agents import *
from .tools import PRODUCT_TOOLS, SHOPPING_CART_TOOLS, WAREHOUSE_TOOLS, get_shopping_cart_for_sse

# langgraph
from langgraph.graph import StateGraph, START, END
from langgraph.prebuilt import ToolNode

# retrievel within the wrapper
from qdrant_client.http.models import MatchValue, FieldCondition, Filter
from qdrant_client.models import VectorParams, Distance, SparseVectorParams, Modifier, PayloadSchemaType, PointStruct, Document, Prefetch, RrfQuery, Rrf
from qdrant_client import QdrantClient

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
        elif tool_call.get("name") == "get_shopping_cart":
            return "Looking at the shopping cart..."
        elif tool_call.get("name") == "remove_from_cart":
            return "Removing item from shopping cart..."
        elif tool_call.get("name") == "add_to_shopping_cart":
            return "Adding item to shopping cart..."
        elif tool_call.get("name") == "check_warehouse_availability":
            return "Checking stock levels..."
        elif tool_call.get("name") == "reserve_warehouse_items":
            return f"Reserving {tool_call.get("args").get("product_ids", [])} items..."
        
    if _is_node_start(chunk):
        if chunk[1].get("payload", {}).get("name") == "coordinator_agent":
            return "Analysing the question..."
        if chunk[1].get("payload", {}).get("name") == "product_qna_agent_node":
            return "Planning for which product information to look..."
        if chunk[1].get("payload", {}).get("name") == "shopping_cart_agent_node":
            return "Planning what to do with the shopping cart..."
        if chunk[1].get("payload", {}).get("name") == "warehouse_agent_node":
            return "Planning what to do with the warehouse inventory..."
        elif chunk[1].get("payload", {}).get("name").endswith("tool_node"):
            message = " ".join([_tool_to_text(tool_call) for tool_call in chunk[1].get('payload', {}).get('input', {}).messages[-1].tool_calls])
            return message


def string_to_sse(string: str):
    """Converts a string to a Server-Sent Event (SSE)"""
    return f"data: {string}\n\n"



#####################################
## Construct Tools into tool nodes ###
#####################################
product_tool_node = ToolNode(PRODUCT_TOOLS)
shopping_cart_tool_node = ToolNode(SHOPPING_CART_TOOLS)
warehouse_tool_node = ToolNode(WAREHOUSE_TOOLS)


#######################
## Conditional Edges ##
#######################

def coordinator_conditional_edges(state: State) -> dict:
    if state.coordinator_agent_state.final_answer:
        return "end"
    elif state.coordinator_agent_state.iteration > 5:
        return "end"
    elif state.coordinator_agent_state.next_agent != "": #return the name of the next agent directly
        return state.coordinator_agent_state.next_agent # in prod should check if the agent actually exists
    else:
        return "end"

def product_qna_tool_router_conditional_edges(state: State) -> dict:
    if state.product_qna_agent_state.final_answer:
        return "end"
    elif state.product_qna_agent_state.iteration >= 3:
        return "end"
    elif len(state.messages[-1].tool_calls) > 0:
        return "tools"
    else:
        return "end"

def shopping_cart_tool_router_conditional_edges(state: State) -> dict:
    if state.shopping_cart_agent_state.final_answer:
        return "end"
    elif state.shopping_cart_agent_state.iteration >= 3:
        return "end"
    elif len(state.messages[-1].tool_calls) > 0:
        return "tools"
    else:
        return "end"

def warehouse_manager_tool_conditional_edges(state: State) -> str:

    if state.warehouse_manager_agent.final_answer:
        return "end"
    elif state.warehouse_manager_agent.iteration >= 5:
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

product_tool_node = ToolNode(PRODUCT_TOOLS)
shopping_cart_tool_node = ToolNode(SHOPPING_CART_TOOLS)
warehouse_tool_node = ToolNode(WAREHOUSE_TOOLS)

# nodes
# coordinator agent
workflow.add_node("coordinator_agent_node", coordinator_agent)

#Product Q&A Agent
workflow.add_node("product_qna_agent_node", product_qna_agent_node)
workflow.add_node("product_tool_node", product_tool_node)

# Shopping Cart Agent
workflow.add_node("shopping_cart_agent_node", shopping_cart_agent)
workflow.add_node("shopping_cart_tool_node", shopping_cart_tool_node)

# Warehouse Agent
workflow.add_node("warehouse_agent_node", warehouse_manager_agent)
workflow.add_node("warehouse_tool_node", warehouse_tool_node)

# edges
workflow.add_edge(START, "coordinator_agent_node")
workflow.add_conditional_edges(
    "coordinator_agent_node",
    coordinator_conditional_edges,
    {
        "product_qna_agent": "product_qna_agent_node",
        "shopping_cart_agent": "shopping_cart_agent_node",
        "warehouse_agent": "warehouse_agent_node",
        "end": END
    }
)
# product agent edges
workflow.add_conditional_edges(
    "product_qna_agent_node",
    product_qna_tool_router_conditional_edges,
    {
        "tools": "product_tool_node",
        "end": "coordinator_agent_node"
    }
)
workflow.add_edge("product_tool_node", "product_qna_agent_node")

# shopping cart edges
workflow.add_conditional_edges(
    "shopping_cart_agent_node",
    shopping_cart_tool_router_conditional_edges,
    {
        "tools": "shopping_cart_tool_node",
        "end": "coordinator_agent_node"
    }
)
workflow.add_edge("shopping_cart_tool_node", "shopping_cart_agent_node")


# warehouse edges
workflow.add_conditional_edges(
    "warehouse_agent_node",
    warehouse_manager_tool_conditional_edges,
    {
        "tools": "warehouse_tool_node",
        "end": "coordinator_agent_node"
    }
)
workflow.add_edge("warehouse_tool_node", "warehouse_agent_node")



#####################
## Agent Execution ##
#####################

def rag_agent_stream_wrapper(question: str, thread_id: str) -> dict:

    qdrant_client = QdrantClient(url="http://qdrant:6333")

    initial_state = { #reset the state of all subagents as well
        "messages": [HumanMessage(content=question)],
        "user_id": thread_id, #the user and cart ids are ephemeral and bound to the client session which defines the thread id
        "cart_id": thread_id,
        "coordinator_agent_state": {
            "iteration": 0,
            "final_answer": False,
            "plan": [],
            "next_agent": ""
        },
        "product_qna_agent_state": {
            "iteration": 0,
            "final_answer": False
        },
        "shopping_cart_agent_state": {
            "iteration": 0,
            "final_answer": False
        },
        "warehouse_manager_agent": {
            "iteration": 0,
            "final_answer": False
        }
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

    shopping_cart = get_shopping_cart_for_sse(user_id=thread_id, cart_id=thread_id)
    shopping_cart_items = [
        {
            "name": item.get("name"),
            "product_image_url": item.get("product_image_url"),
            "quantity": int(item.get("quantity")) if item.get("quantity") is not None else None,
            "price": float(item.get("price")) if item.get("price") is not None else None,
            "total_price": float(item.get("total_price")) if item.get("total_price") is not None else None,
            "currency": item.get("currency"),
        }
        for item in shopping_cart
    ]
            
    yield string_to_sse(
        json.dumps(
            {
                "type": "final_answer",
                "data": {
                    "answer": result.get("answer", ""),
                    "used_context": used_context,
                    "trace_id": result.get("trace_id", ""),
                    "shopping_cart": shopping_cart_items,
                    
                }
            }
        )
    )

