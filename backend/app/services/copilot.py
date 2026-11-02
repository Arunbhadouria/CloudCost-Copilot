"""Copilot manual tool-calling execution loop and streaming orchestrator."""
import json
from typing import Dict, Any, List, Generator
from sqlalchemy.orm import Session
from google.genai import types

from app.models import ChatLog
from app.services.llm_client import get_llm_client, get_tool_declarations
from app.services.sql_templates import (
    execute_cost_query,
    execute_get_recommendation,
    execute_compare_periods
)
from app.services.faithfulness import check_faithfulness


def run_copilot_chat(
    db: Session,
    dataset_id: str,
    user_message: str,
    max_turns: int = 4
) -> Generator[Dict[str, Any], None, None]:
    """Execute manual tool-calling loop and stream tokens, tool results, and faithfulness check."""
    client = get_llm_client()
    tools = get_tool_declarations()

    contents: List[Any] = [user_message]
    all_tool_rows: List[Dict[str, Any]] = []
    executed_sqls: List[str] = []
    tool_calls_log: List[Dict[str, Any]] = []

    for _ in range(max_turns):
        try:
            resp = client.run_turn(contents=contents, tools=tools, temperature=0.0)
        except Exception as e:
            err_msg = str(e).lower()
            if "429" in err_msg or "resource_exhausted" in err_msg or "quota" in err_msg:
                from app.services.llm_client import MockClient
                client = MockClient()
                yield {
                    "type": "token",
                    "text": "[Note: Gemini API Free Tier daily quota limit reached (429). Using deterministic local engine.]\n\n"
                }
                resp = client.run_turn(contents=contents, tools=tools, temperature=0.0)
            else:
                raise

        # Check for function calls
        func_calls = getattr(resp, "function_calls", []) or []
        if not func_calls:
            # No tool call needed, model ready to provide final text
            break

        # Handle tool call
        fc = func_calls[0]
        fn_name = fc.name
        fn_args = fc.args or {}

        yield {
            "type": "tool_call",
            "name": fn_name,
            "args": fn_args
        }
        tool_calls_log.append({"name": fn_name, "args": fn_args})

        # Execute whitelisted SQL template with server-injected dataset_id
        if fn_name == "cost_query":
            res = execute_cost_query(
                db=db,
                dataset_id=dataset_id,
                group_by=fn_args.get("group_by", "service"),
                date_from=fn_args.get("date_from"),
                date_to=fn_args.get("date_to"),
                service=fn_args.get("service"),
                region=fn_args.get("region"),
                limit=fn_args.get("limit", 20)
            )
        elif fn_name == "get_recommendation":
            res = execute_get_recommendation(
                db=db,
                dataset_id=dataset_id,
                id=fn_args.get("id"),
                top_n=fn_args.get("top_n", 5)
            )
        elif fn_name == "compare_periods":
            res = execute_compare_periods(
                db=db,
                dataset_id=dataset_id,
                period_a_start=fn_args.get("period_a_start", "2025-01-01"),
                period_a_end=fn_args.get("period_a_end", "2025-01-31"),
                period_b_start=fn_args.get("period_b_start", "2025-02-01"),
                period_b_end=fn_args.get("period_b_end", "2025-02-28"),
                group_by=fn_args.get("group_by", "service")
            )
        else:
            res = {"rows": [], "sql": "-- Unrecognized tool requested"}

        rows = res.get("rows", [])
        sql = res.get("sql", "")

        all_tool_rows.extend(rows)
        executed_sqls.append(sql)

        yield {
            "type": "tool_result",
            "name": fn_name,
            "rows": rows[:5],  # preview top rows in event
            "sql": sql
        }

        # Send tool output back as structured response
        part_resp = types.Part.from_function_response(
            name=fn_name,
            response={"rows": rows, "sql": sql}
        )
        contents.append(types.Content(role="user", parts=[part_resp]))

    # Stream the final answer
    full_answer_parts = []
    try:
        for token in client.stream_content(contents=contents, temperature=0.0):
            full_answer_parts.append(token)
            yield {
                "type": "token",
                "text": token
            }
    except Exception as e:
        err_msg = str(e).lower()
        if "429" in err_msg or "resource_exhausted" in err_msg or "quota" in err_msg:
            from app.services.llm_client import MockClient
            fallback_client = MockClient()
            fallback_resp = fallback_client.run_turn(contents=contents, tools=tools, temperature=0.0)
            fallback_text = getattr(fallback_resp, "text", "") or "Here are your verified cost records from the database."
            full_answer_parts.append(fallback_text)
            yield {
                "type": "token",
                "text": fallback_text
            }
        else:
            raise

    final_answer = "".join(full_answer_parts)

    # Perform number faithfulness check
    faith_result = check_faithfulness(
        answer=final_answer,
        tool_data=all_tool_rows,
        question=user_message
    )

    # Log chat interaction
    chat_log = ChatLog(
        dataset_id=dataset_id,
        question=user_message,
        tool_calls=tool_calls_log,
        answer=final_answer,
        faithfulness=faith_result
    )
    db.add(chat_log)
    db.commit()

    # Emit final completion event
    yield {
        "type": "final",
        "answer": final_answer,
        "sql": executed_sqls,
        "faithfulness": faith_result
    }

