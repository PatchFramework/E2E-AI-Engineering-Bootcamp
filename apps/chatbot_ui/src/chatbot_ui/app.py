import streamlit as st
import requests
from chatbot_ui.core.config import config


def api_call(method, url, **kwargs):

    def _show_error_popup(message):
        """Show error message as a popup in the top-right corner."""
        st.session_state["error_popup"] = {
            "visible": True,
            "message": message,
        }

    try:
        response = getattr(requests, method)(url, **kwargs)

        try:
            response_data = response.json()
        except requests.exceptions.JSONDecodeError:
            response_data = {"message": "Invalid response format from server"}

        if response.ok:
            return True, response_data

        return False, response_data

    except requests.exceptions.ConnectionError:
        _show_error_popup("Connection error. Please check your network connection.")
        return False, {"message": "Connection error"}
    except requests.exceptions.Timeout:
        _show_error_popup("The request timed out. Please try again later.")
        return False, {"message": "Request timeout"}
    except Exception as e:
        _show_error_popup(f"An unexpected error occurred: {str(e)}")
        return False, {"message": str(e)}


if "messages" not in st.session_state:
    st.session_state.messages = [{"role": "assistant", "content": "Hello! How can I assist you today?"}]
if "citations" not in st.session_state:
    st.session_state.citations = []


# Sidebar for Citations
with st.sidebar:
    st.header("Cited Products")
    if not st.session_state.citations:
        st.write("No product citations for the current response.")
    else:
        for idx, citation in enumerate(st.session_state.citations):
            # Description as clickable link
            desc = citation.get("description", "No description available")
            prod_url = citation.get("product_url", "#")
            st.markdown(f"**{idx + 1}. [{desc}]({prod_url})**")
            
            # Image
            img_url = citation.get("img_url")
            if img_url:
                st.image(img_url, use_container_width=True)
                
            # Average rating and rating number on one line
            rating = citation.get("rating")
            rating_num = citation.get("rating_number")
            
            rating_str = f"⭐ {rating:.1f}" if rating is not None else "⭐ N/A"
            rating_num_str = f"({rating_num} ratings)" if rating_num is not None else "(0 ratings)"
            
            st.write(f"{rating_str} | {rating_num_str}")
            st.markdown("---")


for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])


if prompt := st.chat_input("Hello! How can I assist you today?"):
    st.session_state.messages.append({"role": "user", "content": prompt})
    
    with st.spinner("Thinking..."):
        success, response_data = api_call("post", f"{config.API_URL}/rag", json={"query": prompt})
        
        if success and isinstance(response_data, dict):
            answer_text = response_data.get("answer", "")
            citations = response_data.get("citations", [])
            st.session_state.citations = citations
        else:
            answer_text = "Sorry, I encountered an error retrieving the response."
            st.session_state.citations = []
            
        st.session_state.messages.append({"role": "assistant", "content": answer_text})
        
    st.rerun()