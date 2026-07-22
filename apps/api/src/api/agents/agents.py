from langchain_core.messages import AIMessage
from .models import *
from .tools import *
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

####### RAG AGENT #######
@traceable(
    name="rag_agent_node",
    run_type="llm",
    metadata={
        "ls_provider": "openai",
        "ls_model_name": "gpt-5.4-mini"
    }
)
def agent_node(state: State) -> dict:
    jinja_prompt_template = """# Role: 
    - You are a shopping assistant that answers customer questions about the available products on our marketplace.

    # Goal: 
    - Give the customer a direct and polite answer to their question given the output of available tools. If the tools did not yield any relevant information mention that you are not able to find information on it, if there is no information in the context.

    # Instructions:
    - Use available tools to answer product related questions
    - Never fabricate information about products that are not mentioned in the context or through tool calls
    - When describing products use relevant details
    - If there are no products returned by any tools, ask the customer to rephrase their request and you were not able to find anything related to this request
    - If the customer doesn't state anything related to products in their request ask them to specify which product they are interested in
    - Refer to data in context always as "available products" and never as "context"
    - Try answering queries that are not precise by broadening the search radius i.e. product categories instead of specific brand
    - When you have gathered all information and are ready to provide the final answer to the customer, you MUST call the `FinalResponse` tool with your answer and list of citations. Do NOT respond with plain text when finishing; always use the `FinalResponse` tool.

    # Procedure:
    - Before every tool call check if you have enough information to answer the question already
    - If there is not sufficient information in context you should use tool calls to retrieve the relevant information
    - At the end, if you have sufficient information you should call the `FinalResponse` tool with your answer and list of citations. Otherwise, you should ask the customer to rephrase their request and you were not able to find anything related to this request.
    """
    template = Template(jinja_prompt_template)

    prompt = template.render()

    llm_client = ChatOpenAI(
        model="gpt-5.4-mini",
        reasoning_effort="none",
        use_responses_api=True
    )

    llm_client_with_tools = llm_client.bind_tools(
        [retrieve_formatted_context, FinalResponse],
        tool_choice="required"
    )

    response = llm_client_with_tools.invoke([
        SystemMessage(content=prompt),
        *state.messages
    ])

    current_run = get_current_run_tree()
    if current_run:
        current_run.metadata["usage_metadata"] = {
            "input_tokens": response.usage_metadata["input_tokens"],
            "output_tokens": response.usage_metadata["output_tokens"],
            "total_tokens": response.usage_metadata["total_tokens"]
        }

    final_answer = False
    answer = ""
    citations = []
    if len(response.tool_calls) > 0:
        for tool_call in response.tool_calls:
            print("Got tool call: ", tool_call)
            if tool_call.get("name") == "FinalResponse":
                final_answer = True
                answer = tool_call.get("args").get("answer")
                citations.extend(tool_call.get("args").get("citations"))

                # remove dangling tool calls that might cause errors
                response = AIMessage(content=answer)
                break

    return {
        "messages": [response],
        "final_answer": final_answer,
        "answer": answer,
        "citations": citations,
        "iteration": state.iteration + 1
    }



#######  INTENT ROUTER NODE #######

@traceable(
    name="route_intent",
    run_type="llm",
    metadata={
        "ls_provider": "openai",
        "ls_model_name": "gpt-5.4-mini"
    }
)
def intent_router_node(state: State) -> dict:

    instruction = """
    # Role: 
    - You are a relevancy router for a shopping assistent that answers questions about available products.

    # Task: 
    - Determine if the user query reltes to products, inventory or purchasing
    - Queries about product specs, features, availability, pricing, comparisons, ratings and recommendations are relevant
    - Queries about store policies, personal information, personal advise unrelated to products or unrelated topics to the shop products are not relevant
    
    # Examples:
    <example>
    Query: "Do you have Speakers under 150$"
    Relevant: Yes
    </example>

    <example>
    Query: "Can you help me do my homework?"
    Relevant: No - not related to products
    </example>

    <example>
    Query: "Which Tablet has the cheapest price?"
    Relevant: Yes
    </example>

    <example>
    Query: "How do I return an Item?"
    Relevant: No - about store policy, not product information
    </example>
    """

    template = Template(instruction)
    prompt = template.render()
        
    client = instructor.from_provider(
        "openai/gpt-5.4-nano",
        mode=instructor.Mode.RESPONSES_TOOLS
    )

    response, raw_response = client.create_with_completion(
        messages=[
            {"role": "system", "content": prompt},
            convert_to_openai_messages(state.messages[-1])
        ],
        reasoning={"effort": "none"},
        response_model=IntentRouterResponse
    )

    current_run = get_current_run_tree()
    if current_run:
        current_run.metadata["usage_metadata"] = {
            "input_tokens": raw_response.usage.input_tokens,
            "output_tokens": raw_response.usage.output_tokens,
            "total_tokens": raw_response.usage.total_tokens
        }

    return {
        "question_relevant": response.question_relevant,
        "answer": response.answer
    }