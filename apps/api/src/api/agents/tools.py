import os
os.environ["HF_HOME"] = os.getenv("HF_HOME", "/tmp/huggingface")
os.environ["TORCH_DYNAMO_DISABLE"] = "1"

from typing import List
from langsmith import traceable, get_current_run_tree
from langchain.tools import tool

# models
import openai
from sentence_transformers import CrossEncoder

# retrieval
from qdrant_client.models import Document, Prefetch, RrfQuery, Rrf
from qdrant_client import QdrantClient


###################
##### Helpers #####
###################
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

model = None

def get_or_load_reranker() -> CrossEncoder:
    global model
    
    if model is not None:
        return model
    else:
        # detect ideal accelerator, if available
        import torch as T
        def get_device():
            if T.cuda.is_available():
                return "cuda"
            elif hasattr(T.backends, "mps") and T.backends.mps.is_available():
                # Check if MPS is built and available on Mac
                return "mps"
            return "cpu"

        model = CrossEncoder('cross-encoder/ms-marco-MiniLM-L-6-v2', device=get_device())
        return model


# immediately preload the reranker
get_or_load_reranker()

def rerank_data(query, results, only_k: int = None, additional_lists_to_sort: list[list] = None):
    model = get_or_load_reranker()
    
    rerank_scores = model.rank(query, results)

    reranked_results = []
    if additional_lists_to_sort is not None:
        reranked_additional_lists_to_sort = [[] for _ in range(len(additional_lists_to_sort))]

    for rerank in rerank_scores:
        reranked_idx = rerank["corpus_id"]
        # guard positions that are not in the k items we want
        if only_k is not None and reranked_idx > only_k:
            continue

        reranked_results.append(results[reranked_idx])

        # if given also rerank the other lists to sort
        if additional_lists_to_sort is not None:
            for li_id, li in enumerate(additional_lists_to_sort):
                reranked_additional_lists_to_sort[li_id].append(li[reranked_idx])

    return reranked_results, *reranked_additional_lists_to_sort





###################
###   RAG TOOLS ###
###################


@tool
@traceable(
    name="embed_and_retrieve",
    run_type="embedding",
    metadata={
        "ls_provider": "openai",
        "ls_model_name": "text-embedding-3-small"
    }
)
def retrieve_formatted_context(query: str, k: int = 10) -> str:
    """Retrieves information about available products as a formatted string with each products id, rating and description on a single line starting with a "-".
    The search is performed using BM25 and cosine similarity with RRF and reranking afterwards to retrieve the k items.

    Arg:
        query: The search string that is used to perform search for products
        k: Top k items that will be returned by the tool

    Returns:
        A formatted string that contains the k products that best fit the searched query
    """
    query_embedding = get_embedding(query)
    
    qdrant_client = QdrantClient(url="http://qdrant:6333")

    #hybrid retrieval
    results = qdrant_client.query_points(
        collection_name="Amazon-items-collection-hybrid-search",
        prefetch=[
            Prefetch(
                query=query_embedding,
                using="text-embedding-3-small",
                limit=k
            ),
            Prefetch(
                query=Document(
                    text=query,
                    model="qdrant/bm25"
                ),
                using="bm25",
                limit=k
            )
        ],
        query=RrfQuery(rrf=Rrf(weights=[0.4, 0.6])),
        limit=2*k
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
    
    # reranking
    reranked_retrieved_context, reranked_context_ids, reranked_context_ratings = rerank_data(
        query, 
        retrieved_context, 
        only_k=k, 
        additional_lists_to_sort=[retrieved_context_ids, retrieved_context_ratings])

    # formatting the retrieved & reranked context
    formatted_context = ""

    for id, chunk, rating in zip(reranked_context_ids, reranked_retrieved_context, reranked_context_ratings):
        formatted_context += f"- ID: {id}, rating: {rating}, description: {chunk}\n"

    return formatted_context
    
    # return {
    #     "retrieved_context_ids": retrieved_context_ids,
    #     "retrieved_context": retrieved_context,
    #     "similarity_scores": similarity_scores,
    #     "retrieved_context_ratings": retrieved_context_ratings
    # }



##################
## Expose Tools ##
##################
TOOLS: List[tool] = [retrieve_formatted_context]