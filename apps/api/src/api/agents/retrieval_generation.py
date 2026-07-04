from qdrant_client.http.models import MatchValue, FieldCondition, Filter
import openai
from qdrant_client import QdrantClient
from langsmith import traceable, get_current_run_tree
import instructor
from pydantic import BaseModel, Field


class RAGContextUsed(BaseModel):
    id: str =Field(description="The ID of the item used to answer the questions")

class RAGResponse(BaseModel):
    answer: str = Field(description="Answer to the question asked")
    citations: list[RAGContextUsed] = Field(description="Relevant list of items used to answer the question")


@traceable(
    name="embed_query",
    run_type="embedding",
    metadata={
        "ls_provider": "openai",
        "ls_model_name": "text-embedding-3-small"
    }
)
def get_embedding(text, model="text-embedding-3-small"):
    response = openai.embeddings.create(
        input=text,
        model=model
    )

    current_run = get_current_run_tree()
    if current_run:
        current_run.metadata["usage_metadata"] = {
            "input_tokens": response.usage.prompt_tokens,
            "total_tokens": response.usage.total_tokens,
        }

    return response.data[0].embedding


@traceable(
    name="retrieve_data",
    run_type="retriever"
)
def retrieve_data(query, qdrant_client, k=5):

    query_embedding = get_embedding(query)

    results = qdrant_client.query_points(
        collection_name="Amazon-items-collection-01",
        query=query_embedding,
        limit=k
    )

    retrieved_context_ids = []
    retrieved_context = []
    similarity_scores = []
    retrieved_context_ratings = []

    for result in results.points:
        retrieved_context_ids.append(result.payload["parent_asin"])
        retrieved_context.append(result.payload["preprocessed_description"])
        similarity_scores.append(result.score)
        retrieved_context_ratings.append(result.payload["average_rating"])

    return {
        "retrieved_context_ids": retrieved_context_ids,
        "retrieved_context": retrieved_context,
        "similarity_scores": similarity_scores,
        "retrieved_context_ratings": retrieved_context_ratings
    }


@traceable(
    name="format_retrieved_context",
    run_type="prompt"
)
def process_context(context):

    formatted_context = ""

    for id, chunk, rating in zip(context["retrieved_context_ids"], context["retrieved_context"], context["retrieved_context_ratings"]):
        formatted_context += f"- ID: {id}, rating: {rating}, description: {chunk}\n"

    return formatted_context


@traceable(
    name="build_prompt",
    run_type="prompt"
)
def build_prompt(preprocessed_context, question):

    prompt = f"""
You are a shopping assistant that can answer questions about the products in stock.

You will be given a question and a list of context.

Instructions:
- Answer the question based on the provided context only.
- Never use word context and refer to it as the available products.
- Do not use markdown formatting.

Context:
{preprocessed_context}

Question:
{question}    
"""

    return prompt


@traceable(
    name="generate_answer",
    run_type="llm",
    metadata={
        "ls_provider": "openai",
        "ls_model_name": "gpt-5.4-nano"
    }
)
def generate_answer(prompt):
    client = instructor.from_provider(
        "openai/gpt-5.4-nano",
        mode=instructor.Mode.RESPONSES_TOOLS #use responses rather than completions API
    )

    response, raw_response = client.create_with_completion(
        messages=[
            {"role": "system", "content": prompt}
        ],
        reasoning={"effort": "none"},
        response_model=RAGResponse
    )

    current_run = get_current_run_tree()
    if current_run:
        current_run.metadata["usage_metadata"] = {
            "input_tokens": raw_response.usage.input_tokens,
            "output_tokens": raw_response.usage.output_tokens,
            "total_tokens": raw_response.usage.total_tokens,
        }

    return response


@traceable(
    name="rag_pipeline",
)
def rag_pipeline(question, qdrant_client, top_k=5):

    retrieved_context = retrieve_data(question, qdrant_client, k=top_k)
    preprocessed_context = process_context(retrieved_context)
    prompt = build_prompt(preprocessed_context, question)
    answer = generate_answer(prompt)

    final_answer = {
        "answer": answer.answer,
        "question": question,
        "retrieved_context_ids": retrieved_context["retrieved_context_ids"],
        "retrieved_context": retrieved_context["retrieved_context"],
        "citations": answer.citations,
    }

    return final_answer


def rag_pipeline_wrapper(question, top_k=10):
    qdrant_client = QdrantClient(url="http://qdrant:6333")

    result = rag_pipeline(question, qdrant_client, top_k=top_k)
    
    used_context = []
    for citation in result.get("citations", []):
        # extract the information for the cited items
        points = qdrant_client.scroll(
            collection_name="Amazon-items-collection-01",
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
    
        