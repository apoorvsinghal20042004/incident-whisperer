from langgraph.graph import StateGraph, END
from app.agents.state import IncidentState
from app.agents.triage import triage_agent
from app.agents.log_analysis import log_analysis_agent
from app.agents.metrics import metrics_agent
from app.agents.hypothesis import hypothesis_agent

def build_incident_graph():
    # graph structure: START -> triage_agent -> log_analysis & metrics_agent run parallely -> hypothesis_agent -> END
    # create graph with our state schema
    # every node receives and returns IncidentState
    workflow = StateGraph(IncidentState)

    # Adding nodes
    # each node is a func that takes state and returns state updates
    workflow.add_node("triage", triage_agent)
    workflow.add_node("log_analysis", log_analysis_agent)
    workflow.add_node("metrics", metrics_agent)
    workflow.add_node("hypothesis", hypothesis_agent)

    # define edges
    workflow.set_entry_point("triage")
    workflow.add_edge("triage", "log_analysis")
    workflow.add_edge("triage", "metrics")
    workflow.add_edge("log_analysis", "hypothesis")
    workflow.add_edge("metrics", "hypothesis")
    workflow.add_edge("hypothesis", END)

    # compile graph - validate str and prep for exec
    return workflow.compile()

# create graph instance once- reused for every incident
incident_graph = build_incident_graph()