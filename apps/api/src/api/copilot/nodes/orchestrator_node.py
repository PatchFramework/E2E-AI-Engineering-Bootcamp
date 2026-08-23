import os
import time
import logging
from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field
from langchain_core.messages import SystemMessage, HumanMessage

from api.copilot.state import CopilotGraphState, CleanEvent, SubagentSubstate
from api.copilot.prompts import get_prompt_template, FALLBACK_ORCHESTRATOR_PROMPT
from api.copilot.token_tracker import extract_token_usage, merge_token_usages

logger = logging.getLogger(__name__)

class TaskDelegation(BaseModel):
    agent: str = Field(..., description="Target subagent: 'METRICS', 'FILING_SEARCH', 'QUALITY_AUDIT', or 'GEN_UI'")
    task_description: str = Field(..., description="Specific and focused instruction for this subagent")

class OrchestrationPlan(BaseModel):
    execution_plan: List[str] = Field(..., description="List of subagent names in order of execution or ['DIRECT_ANSWER']")
    parallel_batches: Optional[List[List[str]]] = Field(
        default=None,
        description="Batches of subagents that can execute simultaneously without dependency (e.g. [['METRICS', 'FILING_SEARCH'], ['GEN_UI']])"
    )
    task_delegations: List[TaskDelegation] = Field(
        default_factory=list,
        description="Specific task delegations for each planned subagent"
    )
    reasoning: str = Field(..., description="Step-by-step reasoning for the plan and task distribution")

def run_orchestrator_node(state: CopilotGraphState) -> Dict[str, Any]:
    """
    Orchestrator node:
    1. Initial Mode: Analyzes query and context, produces structured execution plan and specific task delegations.
    2. Dynamic Re-evaluation Mode: Inspects returning subagent summaries, updates clean event narrative, adapts/refines remaining tasks.
    """
    messages = state.get("messages", [])
    last_user_msg = messages[-1].content if messages else ""
    q = last_user_msg.lower().strip()
    company_id = state.get("company_id", 1)
    context_snapshot = state.get("context_snapshot") or {}
    company_name = context_snapshot.get("companyName") or f"Company #{company_id}"
    active_metric = state.get("active_metric") or context_snapshot.get("activeMetric") or "None"
    
    model_name = os.getenv("COPILOT_LLM_MODEL") or os.getenv("OPENAI_MODEL") or "gpt-4o-mini"
    current_token_usage = state.get("token_usage") or {
        "prompt_tokens": 0, "completion_tokens": 0, "cached_tokens": 0, "reasoning_tokens": 0, "total_tokens": 0
    }
    
    clean_history = list(state.get("clean_event_history") or [])
    completed_steps = list(state.get("completed_steps") or [])
    execution_plan = list(state.get("execution_plan") or [])
    new_events: List[CleanEvent] = []

    # -------------------------------------------------------------
    # 1. INITIAL PLANNING PHASE (First entry)
    # -------------------------------------------------------------
    if not execution_plan:
        logger.info(f"Orchestrator initial planning for: '{last_user_msg}'")

        # Direct Answer heuristic shortcut (fast response for trivial greetings)
        greetings = ["hi", "hello", "hey", "who are you", "what can you do", "help"]
        if q in greetings or (len(q.split()) <= 2 and any(g in q for g in ["hi", "hello", "hey"])):
            new_events.append({
                "event_type": "USER_QUERY",
                "agent": "user",
                "content": last_user_msg,
                "metadata": {"company_id": company_id},
                "timestamp": time.time()
            })
            new_events.append({
                "event_type": "ORCHESTRATOR_PLAN",
                "agent": "orchestrator",
                "content": "Routing to direct conversational response.",
                "metadata": {"plan": ["DIRECT_ANSWER"]},
                "timestamp": time.time()
            })
            return {
                "execution_plan": ["DIRECT_ANSWER"],
                "completed_steps": ["DIRECT_ANSWER"],
                "clean_event_history": new_events,
                "model_used": model_name,
                "reasoning_status": "Formulating direct answer..."
            }

        # Record Initial User Query Event
        new_events.append({
            "event_type": "USER_QUERY",
            "agent": "user",
            "content": last_user_msg,
            "metadata": {"company_id": company_id, "active_metric": active_metric},
            "timestamp": time.time()
        })

        # LLM-Based Planning & Task Delegation
        openai_key = os.getenv("OPENAI_API_KEY")
        plan_obj: Optional[OrchestrationPlan] = None

        if openai_key:
            try:
                from langchain_openai import ChatOpenAI
                llm = ChatOpenAI(
                    model=model_name,
                    temperature=0.1,
                    api_key=openai_key,
                    tags=["orchestrator-planner", model_name],
                    model_kwargs={
                        "metadata": {
                            "ls_model_name": model_name,
                            "ls_provider": "openai",
                            "company_id": company_id
                        }
                    }
                )
                structured_llm = llm.with_structured_output(OrchestrationPlan)
                prompt_tpl = get_prompt_template("copilot-orchestrator", FALLBACK_ORCHESTRATOR_PROMPT)
                sys_prompt = prompt_tpl.format(
                    company_id=company_id,
                    company_name=company_name,
                    active_metric=active_metric
                )
                
                resp = structured_llm.invoke([
                    SystemMessage(content=sys_prompt),
                    HumanMessage(content=f"Underwriting Query: {last_user_msg}\nActive Snapshot: {context_snapshot}")
                ])
                if isinstance(resp, OrchestrationPlan):
                    plan_obj = resp
                    # Estimate / track token usage if available
                    logger.info(f"Orchestrator generated structured plan: {plan_obj.execution_plan}")
            except Exception as e:
                logger.warning(f"Orchestrator structured planning LLM call failed ({e}); using heuristic fallback plan.")


        # Record Plan Event in Clean History
        new_events.append({
            "event_type": "ORCHESTRATOR_PLAN",
            "agent": "orchestrator",
            "content": f"Formulated execution plan: {' -> '.join(plan_obj.execution_plan)}. Reasoning: {plan_obj.reasoning}",
            "metadata": {
                "execution_plan": plan_obj.execution_plan,
                "reasoning": plan_obj.reasoning
            },
            "timestamp": time.time()
        })

        # Initialize subagent substates with specific task descriptions
        metric_substate: Optional[SubagentSubstate] = None
        rag_substate: Optional[SubagentSubstate] = None
        audit_substate: Optional[SubagentSubstate] = None
        gen_ui_substate: Optional[SubagentSubstate] = None

        delegation_map = {d.agent: d.task_description for d in plan_obj.task_delegations}

        for agent_name in plan_obj.execution_plan:
            desc = delegation_map.get(agent_name, f"Execute task for {agent_name}")
            new_events.append({
                "event_type": "DELEGATED_TASK",
                "agent": "orchestrator",
                "content": f"Delegated to {agent_name}: {desc}",
                "metadata": {"target_agent": agent_name, "task_description": desc},
                "timestamp": time.time()
            })

            substate_payload: SubagentSubstate = {
                "task_description": desc,
                "iteration_count": 0,
                "max_iterations": 3,
                "is_complete": False,
                "tool_call_history": [],
                "internal_messages": [],
                "final_summary": None
            }

            if agent_name == "METRICS":
                metric_substate = substate_payload
            elif agent_name == "FILING_SEARCH":
                rag_substate = substate_payload
            elif agent_name == "QUALITY_AUDIT":
                audit_substate = substate_payload
            elif agent_name == "GEN_UI":
                gen_ui_substate = substate_payload

        # Determine next step
        first_step = plan_obj.execution_plan[0] if plan_obj.execution_plan else "SYNTHESIZE"

        updates: Dict[str, Any] = {
            "execution_plan": plan_obj.execution_plan,
            "completed_steps": [],
            "current_step_index": 0,
            "clean_event_history": new_events,
            "model_used": model_name,
            "reasoning_status": f"Planning complete: {' -> '.join(plan_obj.execution_plan)}"
        }

        if metric_substate:
            updates["metric_substate"] = metric_substate
        if rag_substate:
            updates["rag_substate"] = rag_substate
        if audit_substate:
            updates["audit_substate"] = audit_substate
        if gen_ui_substate:
            updates["gen_ui_substate"] = gen_ui_substate

        return updates

    # -------------------------------------------------------------
    # 2. DYNAMIC RE-EVALUATION & NEXT-STEP DELEGATION PHASE
    # -------------------------------------------------------------
    logger.info("Orchestrator re-evaluating workflow progress and subagent outputs.")

    # Check for newly completed subagents and record their final summaries
    for agent_key, substate_name in [
        ("METRICS", "metric_substate"),
        ("FILING_SEARCH", "rag_substate"),
        ("QUALITY_AUDIT", "audit_substate"),
        ("GEN_UI", "gen_ui_substate")
    ]:
        sub = state.get(substate_name)
        if sub and sub.get("is_complete") and agent_key not in completed_steps:
            completed_steps.append(agent_key)
            summary = sub.get("final_summary") or f"{agent_key} task completed."
            new_events.append({
                "event_type": "SUBAGENT_ANSWER",
                "agent": agent_key.lower(),
                "content": summary,
                "metadata": {
                    "iterations": sub.get("iteration_count", 1),
                    "tool_calls_count": len(sub.get("tool_call_history", []))
                },
                "timestamp": time.time()
            })

    # Identify remaining steps in execution plan
    remaining_steps = [s for s in execution_plan if s not in completed_steps]

    if not remaining_steps:
        # All planned steps finished -> route to synthesizer
        logger.info("All planned subtasks completed. Proceeding to final synthesis.")
        new_events.append({
            "event_type": "PLAN_REFINED",
            "agent": "orchestrator",
            "content": "All subagent tasks verified and complete. Ready for credit synthesis.",
            "metadata": {"completed_steps": completed_steps},
            "timestamp": time.time()
        })
        return {
            "completed_steps": completed_steps,
            "clean_event_history": new_events,
            "reasoning_status": "All underwriting evidence gathered. Synthesizing final analysis..."
        }

    # Next step is available
    next_step = remaining_steps[0]
    logger.info(f"Orchestrator delegating next step: {next_step}")

    # If next step is GEN_UI, dynamically pass recent metric or topic results into its task description
    if next_step == "GEN_UI":
        gen_ui_sub = state.get("gen_ui_substate") or {}
        task_desc = gen_ui_sub.get("task_description") or f"Generate visualization for query: '{last_user_msg}'"
        # If we just gathered metric history, enrich GenUI task description
        metric_res = state.get("metric_results")
        if metric_res and "history" in metric_res:
            task_desc += f" using historical points: {metric_res['history'].get('history')}"
        
        gen_ui_sub["task_description"] = task_desc
        gen_ui_sub["is_complete"] = False

        return {
            "completed_steps": completed_steps,
            "gen_ui_substate": gen_ui_sub,
            "clean_event_history": new_events,
            "reasoning_status": f"Delegating to GenUI: {task_desc[:60]}..."
        }

    return {
        "completed_steps": completed_steps,
        "clean_event_history": new_events,
        "reasoning_status": f"Proceeding to {next_step}..."
    }

