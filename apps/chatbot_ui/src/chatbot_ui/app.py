import streamlit as st
import requests
from chatbot_ui.core.config import config
import uuid
import json

def get_thread_id():
    if "thread_id" not in st.session_state:
        st.session_state.thread_id = str(uuid.uuid4())
    return st.session_state.thread_id

thread_id = get_thread_id()

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


def api_call_stream(method, url, **kwargs):

    def _show_error_popup(message):
        """Show error message as a popup in the top-right corner."""
        st.session_state["error_popup"] = {
            "visible": True,
            "message": message,
        }

    try:
        response = getattr(requests, method)(url, **kwargs)
        response.raise_for_status()
        for line in response.iter_lines():
            yield line
    except requests.exceptions.ConnectionError:
        _show_error_popup("Connection error. Please check your network connection.")
    except requests.exceptions.Timeout:
        _show_error_popup("The request timed out. Please try again later.")
    except Exception as e:
        _show_error_popup(f"An unexpected error occurred: {str(e)}")


def handle_dialog_dismiss():
    trace_id = st.session_state.get("show_dialog")
    if trace_id and trace_id not in st.session_state.feedback_submitted:
        score = st.session_state.get(f"score_{trace_id}")
        comments = st.session_state.get(f"comments_input_{trace_id}", "")
        # Submit the comprehensive feedback to the API
        success, response_data = api_call(
            "post",
            f"{config.API_URL}/feedback",
            json={
                "trace_id": trace_id,
                "feedback_score": score,
                "feedback_text": comments or "",
                "feedback_source_type": "api"
            }
        )
        if success:
            st.session_state.feedback_submitted[trace_id] = response_data.get("message", "Thanks for your feedback!")
        else:
            st.session_state.feedback_submitted[trace_id] = "Feedback submitted!"
    st.session_state.show_dialog = None


@st.dialog("Provide additional feedback", on_dismiss=handle_dialog_dismiss)
def show_comments_dialog(trace_id):
    st.write("Thank you for rating! Do you have any additional comments?")
    comments = st.text_input("Optional comments:", placeholder="Tell us more...", key=f"comments_input_{trace_id}")
    
    score = st.session_state.get(f"score_{trace_id}")
    
    col1, col2 = st.columns(2)
    with col1:
        if st.button("Submit", key=f"comments_submit_{trace_id}"):
            success, response_data = api_call(
                "post",
                f"{config.API_URL}/feedback",
                json={
                    "trace_id": trace_id,
                    "feedback_score": score,
                    "feedback_text": comments or "",
                    "feedback_source_type": "api"
                }
            )
            if success:
                st.session_state.feedback_submitted[trace_id] = response_data.get("message", "Thanks for your feedback!")
            else:
                st.error(response_data.get("message", "Failed to submit comments."))
            st.session_state.show_dialog = None
            st.rerun()
    with col2:
        if st.button("No thanks", key=f"comments_cancel_{trace_id}"):
            success, response_data = api_call(
                "post",
                f"{config.API_URL}/feedback",
                json={
                    "trace_id": trace_id,
                    "feedback_score": score,
                    "feedback_text": "",
                    "feedback_source_type": "api"
                }
            )
            if success:
                st.session_state.feedback_submitted[trace_id] = response_data.get("message", "Thanks for your feedback!")
            else:
                st.error(response_data.get("message", "Failed to submit feedback."))
            st.session_state.show_dialog = None
            st.rerun()


if "messages" not in st.session_state:
    st.session_state.messages = [{"role": "assistant", "content": "Hello! How can I assist you today?"}]
if "citations" not in st.session_state:
    st.session_state.citations = []
if "feedback_submitted" not in st.session_state:
    st.session_state.feedback_submitted = {}
if "show_dialog" not in st.session_state:
    st.session_state.show_dialog = None


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


for idx, message in enumerate(st.session_state.messages):
    with st.chat_message(message["role"]):
        st.markdown(message["content"])
        
        # Check if this is the last message, it's from the assistant, and it has a trace_id
        if (
            idx == len(st.session_state.messages) - 1
            and message["role"] == "assistant"
            and message.get("trace_id")
        ):
            trace_id = message["trace_id"]
            if trace_id in st.session_state.feedback_submitted:
                st.success(st.session_state.feedback_submitted[trace_id])
            else:
                st.write("Was this response helpful?")
                score = st.feedback("thumbs", key=f"score_{trace_id}")
                if score is not None:
                    # Defer API submission until dialog is handled
                    st.session_state.show_dialog = trace_id
                    st.rerun()


if prompt := st.chat_input("Hello! How can I assist you today?"):
    st.session_state.show_dialog = None
    st.session_state.citations = []
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"):
        
        status_placeholder = st.empty()
        message_placeholder = st.empty()

        for line in api_call_stream(
            "post", 
            f"{config.API_URL}/agent", 
            json={"query": prompt, "thread_id": thread_id},
            stream=True,
            headers={"Accept": "text/event-stream"}
        ):
            line_text = line.decode("utf-8")
            if line_text.startswith("data: "):
                data = line_text[6:]

                try:
                    output = json.loads(data)

                    if output["type"] == "final_answer":
                        answer = output["data"]["answer"]
                        used_context = output["data"]["used_context"]
                        trace_id = output["data"]["trace_id"]
                        
                        st.session_state.used_context = used_context
                        st.session_state.citations = used_context
                        st.session_state.messages.append({"role": "assistant", "content": answer})
                        st.session_state.trace_id = trace_id
                        
                        status_placeholder.empty()
                        message_placeholder.markdown(answer)
                        break
                
                except json.JSONDecodeError:
                    status_placeholder.markdown(f"*{data}*")
        
    st.rerun()

if st.session_state.get("show_dialog"):
    show_comments_dialog(st.session_state.show_dialog)