"""Explicit bounded LangGraph workflow for the read-only business assistant."""

from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Any, Literal, TypedDict, cast

from langgraph.graph import END, START, StateGraph
from sqlalchemy.ext.asyncio import AsyncSession

from nexus.modules.business_agent.models import AgentRun
from nexus.modules.business_agent.schemas import BusinessAgentRequest
from nexus.modules.business_agent.tools import BusinessTools, ToolAuthorizationError
from nexus.modules.organizations.domain import Permission, TenantContext, has_permission

AgentStatus = Literal["running", "completed", "unsupported", "denied", "failed"]


class AgentState(TypedDict):
    question: str
    status: AgentStatus
    selected_tool: str | None
    tool_input: dict[str, object]
    tool_result: dict[str, object]
    answer: str
    citations: list[dict[str, object]]
    transitions: list[str]
    error_code: str | None


class BusinessAgent:
    """One-tool, read-only graph with bounded and inspectable transitions."""

    def __init__(
        self,
        session: AsyncSession,
        context: TenantContext,
        tools: BusinessTools,
        run: AgentRun,
        request: BusinessAgentRequest,
    ) -> None:
        self._session = session
        self._context = context
        self._tools = tools
        self._run = run
        self._request = request

    def compile(self) -> Any:
        graph = StateGraph(AgentState)
        graph.add_node("authorize", self._authorize)
        graph.add_node("plan", self._plan)
        graph.add_node("execute_tool", self._execute_tool)
        graph.add_node("compose_answer", self._compose_answer)
        graph.add_edge(START, "authorize")
        graph.add_conditional_edges(
            "authorize",
            lambda state: "plan" if state["status"] == "running" else "compose_answer",
            {"plan": "plan", "compose_answer": "compose_answer"},
        )
        graph.add_conditional_edges(
            "plan",
            lambda state: "execute_tool" if state["status"] == "running" else "compose_answer",
            {"execute_tool": "execute_tool", "compose_answer": "compose_answer"},
        )
        graph.add_edge("execute_tool", "compose_answer")
        graph.add_edge("compose_answer", END)
        return graph.compile()

    async def run(self) -> AgentState:
        initial: AgentState = {
            "question": self._request.question,
            "status": "running",
            "selected_tool": None,
            "tool_input": {},
            "tool_result": {},
            "answer": "",
            "citations": [],
            "transitions": [],
            "error_code": None,
        }
        result = cast(AgentState, await self.compile().ainvoke(initial))
        self._run.status = result["status"]
        self._run.selected_tool = result["selected_tool"]
        self._run.transition_count = len(result["transitions"])
        self._run.error_code = result["error_code"]
        self._run.completed_at = datetime.now(UTC)
        await self._session.flush()
        return result

    async def _authorize(self, state: AgentState) -> dict[str, object]:
        transitions = [*state["transitions"], "authorize"]
        if not has_permission(self._context.role, Permission.AI_ASSISTANT_USE):
            return {
                "status": "denied",
                "error_code": "agent_access_denied",
                "transitions": transitions,
            }
        return {"transitions": transitions}

    async def _plan(self, state: AgentState) -> dict[str, object]:
        question = state["question"].lower().strip()
        transitions = [*state["transitions"], "plan"]
        today = datetime.now(UTC).date()
        month_start = date(today.year, today.month, 1)
        default_range: dict[str, object] = {
            "date_from": month_start.isoformat(),
            "date_to": today.isoformat(),
            "currency": self._request.currency,
        }
        selected: str
        tool_input: dict[str, object]
        write_words = {"delete", "create", "update", "change", "refund", "adjust"}
        if any(word in question.split() for word in write_words):
            return {
                "status": "unsupported",
                "error_code": "write_requires_explicit_workflow",
                "answer": (
                    "Write operations are not available in this assistant. Use a separately "
                    "authorized workflow with explicit user confirmation."
                ),
                "transitions": transitions,
            }
        if "compare" in question and "sales" in question:
            if self._request.period_a is None or self._request.period_b is None:
                return {
                    "status": "unsupported",
                    "error_code": "comparison_periods_required",
                    "answer": "Select both comparison periods before asking to compare sales.",
                    "transitions": transitions,
                }
            tool_input = {
                "period_a_from": self._request.period_a.date_from.isoformat(),
                "period_a_to": self._request.period_a.date_to.isoformat(),
                "period_b_from": self._request.period_b.date_from.isoformat(),
                "period_b_to": self._request.period_b.date_to.isoformat(),
                "currency": self._request.currency,
            }
            selected = "compare_sales_periods"
        elif any(term in question for term in ("sold the most", "top products", "best-selling")):
            selected, tool_input = "get_top_products", {**default_range, "limit": 5}
        elif any(term in question for term in ("running low", "low stock", "inventory alert")):
            selected, tool_input = "get_inventory_alerts", {"limit": 20}
        elif any(term in question for term in ("revenue", "sales this month")):
            selected, tool_input = "get_revenue_summary", default_range
        elif any(term in question for term in ("document", "handbook", "policy", "knowledge")):
            selected, tool_input = "search_knowledge_base", {"query": state["question"]}
        else:
            return {
                "status": "unsupported",
                "error_code": "unsupported_question",
                "answer": "This assistant cannot answer that question with its approved tools.",
                "transitions": transitions,
            }
        return {
            "selected_tool": selected,
            "tool_input": tool_input,
            "transitions": transitions,
        }

    async def _execute_tool(self, state: AgentState) -> dict[str, object]:
        transitions = [*state["transitions"], "execute_tool"]
        try:
            result = await self._tools.invoke(
                cast(str, state["selected_tool"]), state["tool_input"]
            )
            return {"tool_result": result, "transitions": transitions}
        except ToolAuthorizationError:
            return {
                "status": "denied",
                "error_code": "tool_access_denied",
                "transitions": transitions,
            }
        except TimeoutError:
            return {
                "status": "failed",
                "error_code": "tool_timeout",
                "transitions": transitions,
            }
        except Exception:
            return {
                "status": "failed",
                "error_code": "tool_execution_failed",
                "transitions": transitions,
            }

    async def _compose_answer(self, state: AgentState) -> dict[str, object]:
        transitions = [*state["transitions"], "compose_answer"]
        if state["status"] != "running":
            answer = state["answer"] or "The assistant could not complete this request."
            return {"answer": answer, "transitions": transitions}
        tool = state["selected_tool"]
        result = state["tool_result"]
        citations: list[dict[str, object]] = []
        if tool == "get_revenue_summary":
            answer = (
                f"Net revenue was {result['total_revenue']} {result['currency']} across "
                f"{result['order_count']} completed paid orders."
            )
        elif tool == "get_top_products":
            products = cast(list[dict[str, object]], result["products"])
            answer = "No paid product sales were found."
            if products:
                answer = "Top products: " + "; ".join(
                    f"{item['name']} ({item['quantity_sold']} units)" for item in products
                )
        elif tool == "get_inventory_alerts":
            alerts = cast(list[dict[str, object]], result["alerts"])
            answer = "No products are at or below their low-stock threshold."
            if alerts:
                answer = "Low-stock products: " + "; ".join(
                    f"{item['product_name']} at {item['branch_name']} "
                    f"({item['quantity']} <= {item['threshold']})"
                    for item in alerts
                )
        elif tool == "compare_sales_periods":
            first = cast(dict[str, object], result["period_a"])
            second = cast(dict[str, object], result["period_b"])
            difference = Decimal(str(second["total_revenue"])) - Decimal(
                str(first["total_revenue"])
            )
            answer = (
                f"Period A revenue was {first['total_revenue']} {result['currency']}; "
                f"Period B was {second['total_revenue']} {result['currency']}; "
                f"difference B-A was {difference}."
            )
        elif tool == "search_knowledge_base":
            answer = str(result["answer"])
            citations = cast(list[dict[str, object]], result["citations"])
            if not result["supported"]:
                return {
                    "status": "unsupported",
                    "answer": answer,
                    "citations": [],
                    "transitions": transitions,
                }
        else:
            return {
                "status": "failed",
                "answer": "The selected tool produced no supported response.",
                "error_code": "invalid_tool_result",
                "transitions": transitions,
            }
        return {
            "status": "completed",
            "answer": answer,
            "citations": citations,
            "transitions": transitions,
        }
