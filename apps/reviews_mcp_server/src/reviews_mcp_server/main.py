from fastmcp import FastMCP

# models
import openai

# retrieval
from qdrant_client.models import Prefetch
from qdrant_client import QdrantClient
from qdrant_client.http.models import FusionQuery
from qdrant_client.http.models import MatchAny, FieldCondition, Filter


mcp = FastMCP("items_mcp_server")

###################
##### Helpers #####
###################
def get_embedding(text, model="text-embedding-3-small"):
    response = openai.embeddings.create(
        input=text,
        model=model
    )

    return response.data[0].embedding




######################
##### MCP Tools ######
######################

### Product tool ###
@mcp.tool
def retrieve_prefiltered_reviews(query: str, parent_asins: list[str], k: int = 10) -> str:
    """Retrieves reviews for a list of parent ASINs as a formatted string with each review on a single line starting with a "-".
    The search is performed using BM25 and cosine similarity with RRF and reranking afterwards to retrieve the k items.

    Args:
        query: The search string that is used to perform search for reviews
        parent_asins: The list of parent ASINs to filter the reviews by
        k: The number of reviews to retrieve

    Returns:
        A formatted string that contains the k reviews that best fit the searched query
    """
    query_embedding = get_embedding(query)

    qdrant_client = QdrantClient(url="http://qdrant:6333")

    #hybrid retrieval
    results = qdrant_client.query_points(
        collection_name="Amazon-reviews-collection-hybrid-search",
        prefetch=[
            Prefetch(
                query=query_embedding,
                using="text-embedding-3-small",
                filter=Filter(
                    must=[
                        FieldCondition(
                            key="parent_asin", 
                            match=MatchAny(
                                any=parent_asins
                            )
                        )
                    ]
                ),
                limit=20
            ),
        ],
        query=FusionQuery(fusion="rrf"),
        limit=k
    )


    retrieved_context_ids = []
    retrieved_context = []
    similarity_scores = []

    for result in results.points:
        retrieved_context_ids.append(result.payload["parent_asin"])
        retrieved_context.append(result.payload["preprocessed_content"])
        similarity_scores.append(result.score)
    

    formatted_context = ""

    for id, review in zip(retrieved_context_ids, retrieved_context):
        formatted_context += f"- ID: {id}, User Review: {review}\n"

    return formatted_context


if __name__ == "__main__":
    mcp.run(transport="http", host="0.0.0.0", port=8000)