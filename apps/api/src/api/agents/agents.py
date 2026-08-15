from langchain_core.messages import AIMessage
from .models import *
from .tools import PRODUCT_TOOLS, SHOPPING_CART_TOOLS, WAREHOUSE_TOOLS
from api.core.config import config

from openai import OpenAI

# langchain
from langchain_openai import ChatOpenAI
from langchain_core.tools import tool
from langchain_core.messages import SystemMessage, HumanMessage, convert_to_openai_messages

# langsmith
from langsmith import traceable, get_current_run_tree

# templating
from jinja2 import Template

import instructor


#################
##  LLM RUNNER ##
#################
SUPPORTED_PROVIDERS = ["OpenAI"]
def run_llm(provider, model_name, messages, max_tokens=500):
    assert provider in SUPPORTED_PROVIDERS, f"Unsupported provider: {provider}. Only the following providers are supported: {SUPPORTED_PROVIDERS}"
    
    if provider == "OpenAI":
        client = OpenAI(api_key=config.OPENAI_API_KEY)
        return client.chat.completions.create(
            model=model_name,
            messages=messages,
            max_completion_tokens=max_tokens,
            reasoning_effort="minimal"
        ).choices[0].message.content



#################
###### NODES ####   
#################

####### PRODUCT Q&A AGENT #######
@traceable(
    name="product_qna_agent_node",
    run_type="llm",
    metadata={
        "ls_provider": "openai",
        "ls_model_name": "gpt-5.4-mini"
    }
)
def product_qna_agent_node(state: State) -> dict:
    jinja_prompt_template = """# Role: 
    - You are a shopping assistant that answers customer questions about the available products on our marketplace.

    # Goal: 
    - Give the customer a direct and polite answer to their question given the output of available tools. If the tools did not yield any relevant information mention that you are not able to find information on it, if there is no information in the context.

    # Instructions:
    - Use available tools to answer product related questions
    - Once you have retrieved the product information and can answer the user's question, you MUST call the FinalQnAResponse tool with your final answer and the corresponding product ASINs (parent_asin) as citations.
    - Never fabricate information about products that are not mentioned in the context or through tool calls
    - When describing products use relevant details
    - If there are no products returned by any tools, ask the customer to rephrase their request and you were not able to find anything related to this request
    - If the customer doesn't state anything related to products in their request ask them to specify which product they are interested in
    - Refer to data in context always as "available products" and never as "context"
    - Try answering queries that are not precise by broadening the search radius i.e. product categories instead of specific brand
    """
    template = Template(jinja_prompt_template)

    prompt = template.render()

    llm_client = ChatOpenAI(
        model="gpt-5.4-mini",
        reasoning_effort="low",
        use_responses_api=True
    )

    if state.product_qna_agent_state.iteration >= 2:
        llm_client_with_tools = llm_client.bind_tools(
            [FinalQnAResponse],
            tool_choice="required"
        )
    else:
        llm_client_with_tools = llm_client.bind_tools(
            [*PRODUCT_TOOLS, FinalQnAResponse],
            tool_choice="required"
        )

    response = llm_client_with_tools.invoke([
        SystemMessage(content=prompt),
        *state.messages
    ])

    final_answer = False
    answer = ""
    citations = []


    def sanitise_repsonse(response):
        for tool_call in response.tool_calls:
            if tool_call.get("name") == "FinalQnAResponse":
                answer = tool_call.get("args").get("answer")
                break
                # removing any toolcall suggestions by doing so
        return AIMessage(content=answer)

    if len(response.tool_calls) > 0:
        for tool_call in response.tool_calls:
            if tool_call.get("name") == "FinalQnAResponse":
                final_answer = True
                answer = tool_call.get("args").get("answer")
                citations.extend(tool_call.get("args").get("citations"))

                response = sanitise_repsonse(response)
                break

    return {
        "messages": [response],
        "product_qna_agent_state": {
            "iteration": state.product_qna_agent_state.iteration + 1,
            "final_answer": final_answer
        },
        "answer": answer,
        "citations": citations,
    }

### SHOPPING CART AGENT ###
@traceable(
    name="shopping_cart_agent",
    run_type="llm",
    metadata={
        "ls_provider": "openai",
        "ls_model_name": "gpt-5.4-mini"
    }
)
def shopping_cart_agent(state) -> dict:
    
    prompt_template = """You are a part of the shopping assistant that can manage the user's shopping cart.

## Instructions

- Use names specificly provided in the available tools. Don't add any additional text to the names.
- You can run multipple tools at once.
- Once you have completed the requested actions or have the final answer, you MUST call the FinalAgentResponse tool to submit your final response to the user.
- As the final answer you should return an answer in a form of actions performed.

## Additional information about the user

- User ID: {{ user_id }}
- Cart ID: {{ cart_id }}
"""

    template = Template(prompt_template)

    prompt = template.render(
        user_id=state.user_id,
        cart_id=state.cart_id
    )

    llm = ChatOpenAI(
        model="gpt-5.4-mini",
        reasoning_effort="low",
        use_responses_api=True
    )
    if state.shopping_cart_agent_state.iteration >= 2:
        llm_with_tools = llm.bind_tools(
            [FinalAgentResponse],
            tool_choice="required"
        )
    else:
        llm_with_tools = llm.bind_tools(
            [*SHOPPING_CART_TOOLS, FinalAgentResponse],
            tool_choice="required"
        )

    response = llm_with_tools.invoke(
        [
            SystemMessage(content=prompt),
            *state.messages
        ]
    )

    final_answer = False
    answer = ""

    def sanitise_response(response):

        for tool_call in response.tool_calls:
            if tool_call.get("name") == "FinalAgentResponse":
                answer = tool_call.get("args").get("answer")

        return AIMessage(content=answer)

    if len(response.tool_calls) > 0:
        for tool_call in response.tool_calls:
            if tool_call.get("name") == "FinalAgentResponse":
                final_answer = True
                answer = tool_call.get("args").get("answer")

                response = sanitise_response(response)

    return {
        "messages": [response],
        "shopping_cart_agent_state": {
            "iteration": state.shopping_cart_agent_state.iteration + 1,
            "final_answer": final_answer
        },
        "answer": answer
    }


### WAREHOUSE AGENT ###
@traceable(
    name="warehouse_manager_agent",
    run_type="llm",
    metadata={
        "ls_provider": "openai",
        "ls_model_name": "gpt-5.4-mini"
    }
)
def warehouse_manager_agent(state) -> dict:
    
    prompt_template = """You are a part of the shopping assistant that can manage available inventory in the warehouses.

## Instructions

- Once you have checked availability or completed the reservations, you MUST call the FinalAgentResponse tool to submit your final answer to the user.
- As the final answer you should return an answer to the users query in a form of actions performed.
- You must always check the availability of the items in the warehouses before reserving them.
- Only reserve items in warehouses if entire order can be reserved or the user has confirmed that they want a partial reservation.
- If you cannot reserve any items, return an answer that the order cannot be reserved.
- If you can reserve some items, return an answer that the order can be partially reserved and include the details.
- If only partial quantity can be reserved in some warehouses, try to combine the required quantity from different warehouses.
- Try to reserve items from the closest warehouse to the user first if users location is provided.
- As the final answer you should return an answer in a form of actions performed.
"""

    template = Template(prompt_template)

    prompt = template.render()

    llm = ChatOpenAI(
        model="gpt-5.4-mini",
        reasoning_effort="low",
        use_responses_api=True
    )
    if state.warehouse_manager_agent.iteration >= 4:
        llm_with_tools = llm.bind_tools(
            [FinalAgentResponse],
            tool_choice="required"
        )
    else:
        llm_with_tools = llm.bind_tools(
            [*WAREHOUSE_TOOLS, FinalAgentResponse],
            tool_choice="required"
        )

    response = llm_with_tools.invoke(
        [
            SystemMessage(content=prompt),
            *state.messages
        ]
    )

    final_answer = False
    answer = ""

    def sanitise_response(response):

        for tool_call in response.tool_calls:
            if tool_call.get("name") == "FinalAgentResponse":
                answer = tool_call.get("args").get("answer")

        return AIMessage(content=answer)

    if len(response.tool_calls) > 0:
        for tool_call in response.tool_calls:
            if tool_call.get("name") == "FinalAgentResponse":
                final_answer = True
                answer = tool_call.get("args").get("answer")

                response = sanitise_response(response)

    return {
        "messages": [response],
        "warehouse_manager_agent": {
            "iteration": state.warehouse_manager_agent.iteration + 1,
            "final_answer": final_answer
        },
        "answer": answer
    }

### COORDINATOR AGENT ###
@traceable(
    name="coordinator_agent",
    run_type="llm",
    metadata={
        "ls_provider": "openai",
        "ls_model_name": "gpt-5.4-mini"
    }
)
def coordinator_agent(state) -> dict:
    
    prompt_template = """You are a coordinator agent as part of a shopping assisant.

    ## Role
    - You are responsible to create plans to solve the user query by delegating tasks to other agents
    - If none of the stated agents are helpful to answer the user query, than generate an answer yourself, that instructs the user to clarify or state that you cannot help with the query.

    ## Task
    - You get a conversation history with the user that should be used to understand the user request
    - You create a plan that uses the available agents to come to a final answer to the query
    - After the plan is created you should output the next agent to invoke and the task to be performed by that agent
    - Once an agent finishes a task it will report back to you, you should then decide if the plan needs any updates and what the next step will be
    - If a subagent has successfully completed the task and answered the user query in the conversation history, do not delegate or plan further. You must call FinalAgentResponse to return the subagent's answer as the final response to the user.
    - If there is a sequence of tasks to be performed by one agent you should combine them into a single task
    - Do not route to any agents if the user request is unclear or irrelevant for the shopping assistant with the given agents

    ## Available Agents
    ### product_qna_agent:
    - user query relates to products, inventory or purchasing
    - Queries about product specs, features, availability, pricing, comparisons, ratings and recommendations
    - if the query is about an item that should be added, deleted or shown in the shopping cart it is not a product_q&a question, but rather a shopping_cart query 
    
    ### shopping_cart_agent:
    - queries to add, list or delete items from a shopping cart
    - questions about products in the shopping cart are not part of the shopping_cart, they belong to the product_q&a questions

    ### warehouse_agent: 
    - The user is asking to reserve items from the warehouses or about availability of the items in warehouses

    ## Examples:
    <example>
    Question: "Do you have books under 20USD?"
    Next Agent: product_gna_agent
    </example>

    <example>
    Question: "I don't want to buy the Shoes anymore"
    Next Agent: shopping_cart_agent
    </example> 

    <example>
    Question: "Please reserve my shopping cart items"
    Next Agent: warehouse_agent
    </example>
    
    <example>
    Question: "Do you have books under 20USD?"
    History:
    - User: Do you have books under 20USD?
    - product_qna_agent (FinalQnAResponse): Yes, we have Book A for 15USD.
    Next Agent: FinalAgentResponse(answer="Yes, we have Book A for 15USD.")
    </example>
"""

    template = Template(prompt_template)

    prompt = template.render(
        user_id=state.user_id,
        cart_id=state.cart_id
    )

    # guard condition if the coordinator is invoked with the final answer from a subagent (AIMessage without tool_calls)
    if len(state.messages) > 0 and \
       isinstance(state.messages[-1], AIMessage) and \
       len(state.messages[-1].tool_calls) == 0:
       
        last_msg = state.messages[-1]
        if isinstance(last_msg.content, list):
            answer = ""
            for item in last_msg.content:
                if isinstance(item, dict):
                    if item.get("type") == "text":
                        answer += item.get("text", "")
                elif isinstance(item, str):
                    answer += item
        else:
            answer = last_msg.content
        return {
            "messages": [],
            "coordinator_agent_state": {
                "iteration": state.coordinator_agent_state.iteration + 1,
                "final_answer": True,
                "plan": state.coordinator_agent_state.plan,
                "next_agent": ""
            },
            "answer": answer
        }

    # core logic if it is not a final answer
    llm = ChatOpenAI(
        model="gpt-5.4-mini",
        reasoning_effort="low",
        use_responses_api=True
    )
    llm_with_tools = llm.bind_tools(
        [Plan, FinalAgentResponse],
        tool_choice="required"
    )

    response = llm_with_tools.invoke(
        [
            SystemMessage(content=prompt),
            *state.messages
        ]
    )

    current_run = get_current_run_tree()
    if current_run:
        current_run.metadata["usage_metadata"] = {
            "input_tokens": response.usage_metadata["input_tokens"],
            "output_tokens": response.usage_metadata["output_tokens"],
            "total_tokens": response.usage_metadata["total_tokens"],
        }

        trace_id = str(current_run.trace_id)
    else:
        trace_id = ""

    final_answer = False
    answer = ""
    plan = []
    next_agent = ""

    def sanitise_response(response):

        for tool_call in response.tool_calls:
            if tool_call.get("name") == "FinalAgentResponse":
                answer = tool_call.get("args").get("answer")

        return AIMessage(content=answer)

    if len(response.tool_calls) > 0:
        if response.tool_calls[0].get("name") == "Plan":
            plan = response.tool_calls[0].get("args").get("plan")
            next_agent = response.tool_calls[0].get("args").get("next_agent")
            response = None
        else:
            for tool_call in response.tool_calls:
                if tool_call.get("name") == "FinalAgentResponse":
                    final_answer = True
                    answer = tool_call.get("args").get("answer")

                    response = sanitise_response(response)

    return {
        "messages": [response] if response is not None else [],
        "coordinator_agent_state": {
            "iteration": state.coordinator_agent_state.iteration + 1,
            "final_answer": final_answer,
            "plan": plan,
            "next_agent": next_agent
        },
        "answer": answer,
        "trace_id": trace_id
    }


# #######  Coordinator Agent Node #######

# @traceable(
#     name="route_intent",
#     run_type="llm",
#     metadata={
#         "ls_provider": "openai",
#         "ls_model_name": "gpt-5.4-mini"
#     }
# )
# def intent_router_node(state: State) -> dict:

#     instruction = """
#     # Role: 
#     - You are a relevancy router for a shopping assistent that answers questions about available products.

#     # Task: 
#     - Determine if the user query reltes to products, inventory or purchasing
#     - Queries about product specs, features, availability, pricing, comparisons, ratings and recommendations are relevant
#     - Queries about store policies, personal information, personal advise unrelated to products or unrelated topics to the shop products are not relevant
    
#     # Examples:
#     <example>
#     Query: "Do you have Speakers under 150$"
#     Relevant: Yes
#     </example>

#     <example>
#     Query: "Can you help me do my homework?"
#     Relevant: No - not related to products
#     </example>

#     <example>
#     Query: "Which Tablet has the cheapest price?"
#     Relevant: Yes
#     </example>

#     <example>
#     Query: "How do I return an Item?"
#     Relevant: No - about store policy, not product information
#     </example>
#     """

#     template = Template(instruction)
#     prompt = template.render()
        
#     client = instructor.from_provider(
#         "openai/gpt-5.4-nano",
#         mode=instructor.Mode.RESPONSES_TOOLS
#     )

#     response, raw_response = client.create_with_completion(
#         messages=[
#             {"role": "system", "content": prompt},
#             convert_to_openai_messages(state.messages[-1])
#         ],
#         reasoning={"effort": "none"},
#         response_model=IntentRouterResponse
#     )

#     current_run = get_current_run_tree()
#     if current_run:
#         # additional metadata for token consumption to calculate costs
#         current_run.metadata["usage_metadata"] = {
#             "input_tokens": raw_response.usage.input_tokens,
#             "output_tokens": raw_response.usage.output_tokens,
#             "total_tokens": raw_response.usage.total_tokens
#         }
#         # extract the trace id to associate it with feedback
#         trace_id = str(current_run.trace_id)
#     else:
#         trace_id = ""

#     return {
#         "question_relevant": response.question_relevant,
#         "answer": response.answer,
#         "trace_id": trace_id
#     }