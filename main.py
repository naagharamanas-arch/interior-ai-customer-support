import asyncio
import json
import logging
import os
import time
import uuid
from pathlib import Path
from dotenv import load_dotenv
from memory import save_message, get_chat_history

from autogen_agentchat.agents import AssistantAgent
from autogen_agentchat.ui import Console
from autogen_ext.models.openai import OpenAIChatCompletionClient

load_dotenv()

BASE_DIR = Path(__file__).parent
PROFILE_PATH = BASE_DIR / "company_profile.json"


def load_company_profile():
    try:
        with open(PROFILE_PATH, "r", encoding="utf-8") as file:
            return json.load(file)
    except (FileNotFoundError, json.JSONDecodeError) as error:
        logging.error("Company profile could not be loaded: %s", error)
        return None
    
BASE_DIR = Path(__file__).parent
LOG_DIR = BASE_DIR / "logs"
LOG_DIR.mkdir(exist_ok=True)

logging.basicConfig(
    filename=LOG_DIR / "app.log",
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    encoding="utf-8",
)

MAX_QUESTION_LENGTH = 1000
MAX_MODEL_CALLS = 2

AGENT_INSTRUCTIONS = {
    "HOME_INTERIOR": (
        "You help with residential interior design, living rooms, "
        "bedrooms, wardrobes, and home kitchens. Never invent company prices."
    ),
    "COMMERCIAL_INTERIOR": (
        "You help with commercial interiors, office ceilings, "
        "and partitions. Never invent company prices."
    ),
    "UPVC_PVC_INTERIOR": (
        "You help with economical UPVC/PVC interiors, ceilings, "
        "wall panels, and maintenance. Never invent company prices."
    ),
    "B2B_PRODUCTS": (
        "You help with Aluminium Solar Sections, Baffle Ceiling Sections, "
        "Aluminium Patta, and Modular Kitchen Products. Ask for specifications "
        "and quantity for bulk orders. Never invent prices, stock, or MOQ."
    ),
}


def build_agent_instructions(category, company_profile):
    category_info = company_profile.get("business_categories", {}).get(category, {})
    
    details_verified = category_info.get("details_verified", True)


    company_context = json.dumps(
        {
            "company_name": company_profile.get("company_name", "Unknown"),
            "website_status": company_profile.get(
                "website_status", "Needs Company Verification"
            ),
            "company_profile_status": company_profile.get(
                "company_profile_status", "Partially Verified"
            ),
            "verification_note": company_profile.get(
                "verification_note",
                "Confirm company-specific details before making commitments."
            ),
            "category_details": category_info,
            "sales_rules": company_profile.get("sales_rules", {}),
            "human_handover": company_profile.get("human_handover", {}),
        },
        ensure_ascii=False,
        indent=2,
    )

    return (
        AGENT_INSTRUCTIONS[category]
        + "\n\nUse this company profile as your reference:\n"
        + company_context
        + "\n\nImportant rules:"

        + "\n\nImportant rules:"
        + "\n- Treat unverified details as unconfirmed."
        + "\n- Never claim that the company offers a product or service unless the company profile confirms it."
        + f"\n- Product/service details_verified status for this category: {details_verified}."
        + "\n- If details_verified is false, do not say 'we offer', 'we provide', or otherwise confirm availability. Say the company team must verify the product or service."
        + "\n- If product or service availability is unverified, say that the company team must confirm it."
        + "\n- Never invent prices, stock, MOQ, specifications, warranties, or delivery times."
        + "\n- Ask for missing product specifications and quantity for bulk orders."
        + "\n- For prices, complaints, or unverified details, recommend confirmation by the company team."
        + "\n- Do not claim that a human handover has occurred unless it actually has."

    )


async def main():
    from memory import initialize_database
    initialize_database()

    company_profile = load_company_profile()

    if not company_profile:
        print("Error: Company profile is missing or invalid.")
        return

    print("Company profile loaded:", company_profile.get("company_name", "Unknown"))

    request_id = str(uuid.uuid4())[:8]
    started = time.perf_counter()
    calls_used = 0
    model_client = None

    try:
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("OPENAI_API_KEY is missing from .env")

        model_client = OpenAIChatCompletionClient(
            model="gpt-4o-mini",
            api_key=api_key,
        )
        customer_id = input("Enter customer ID: ").strip()

        if not customer_id:
            print("Customer ID cannot be empty.")
            return

        chat_history = get_chat_history(customer_id)

        print(f"Previous messages found: {len(chat_history)}")

        question = input("Customer question: ").strip()

        if not question:
            print("Please enter a question.")
            return

        if len(question) > MAX_QUESTION_LENGTH:
            print(f"Question is too long. Maximum {MAX_QUESTION_LENGTH} characters.")
            return

        print(f"\n[CHECKPOINT] Request ID: {request_id}")
        print("[CHECKPOINT] Input validation passed.")

        

        manager = AssistantAgent(
            name="interior_manager",
            model_client=model_client,
            system_message=f"""
You are the manager for {company_profile.get("company_name", "the company")}.

Use the company profile below to understand the business categories:
{json.dumps(company_profile.get("business_categories", {}), ensure_ascii=False)}

Classify the customer's interior design or interior products question
into exactly one category:
HOME_INTERIOR, COMMERCIAL_INTERIOR, UPVC_PVC_INTERIOR,
B2B_PRODUCTS, or OUT_OF_SCOPE.

Choose HOME_INTERIOR for residential interior design.
Choose COMMERCIAL_INTERIOR for commercial interiors, ceilings, and partitions.
Choose UPVC_PVC_INTERIOR for economical UPVC/PVC interiors.
Choose B2B_PRODUCTS for product specifications, bulk quantity, or purchasing:
Aluminium Solar Sections, Baffle Ceiling Sections, Aluminium Patta,
and Modular Kitchen Products.

If the question is unrelated to these business areas, choose OUT_OF_SCOPE.

Return only the category name, with no explanation.
""",
        )

        calls_used += 1
        routing_result = await manager.run(
            task=f"Classify this customer question: {question}"
        )

        category = routing_result.messages[-1].content.strip().upper()
        print(f"[CHECKPOINT] Selected category: {category}")
        print(f"[CHECKPOINT] Model calls used: {calls_used}/{MAX_MODEL_CALLS}")

        if category == "OUT_OF_SCOPE":
            print("Sorry, I can only help with interior design and interior products.")
            logging.info(
                "request_id=%s category=OUT_OF_SCOPE calls=%s",
                request_id, calls_used
            )
            return

        if category not in AGENT_INSTRUCTIONS:
            raise ValueError(f"Unexpected category: {category}")

        if calls_used >= MAX_MODEL_CALLS:
            raise RuntimeError("Model call budget reached before specialist call")

        specialist = AssistantAgent(
            name=category.lower() + "_specialist",
            model_client=model_client,
            system_message=build_agent_instructions(category, company_profile),
        )

        calls_used += 1
        print(f"[CHECKPOINT] Calling specialist: {category}")


        history_text = "\n".join(
            f'{item["role"]}: {item["content"]}'
            for item in chat_history
        )

        task = (
            f"Previous conversation:\n{history_text or 'No previous conversation.'}\n\n"
            f"Current customer question: {question}\n"
            "Use the previous conversation for context. Answer the current "
            "question concisely. If company-specific information is unknown, "
            "say it needs confirmation."
        )


        print("\nAI Response:")

        response_parts = []

        async for event in specialist.run_stream(task=task):
            if hasattr(event, "content") and isinstance(event.content, str):
                print(event.content)
                response_parts.append(event.content)

        assistant_reply = "\n".join(response_parts)

        save_message(customer_id, "user", question)
        save_message(customer_id, "assistant", assistant_reply)

        duration = round(time.perf_counter() - started, 2)
        logging.info(
            "request_id=%s category=%s calls=%s duration_seconds=%s status=success",
            request_id, category, calls_used, duration
        )
        print(f"\n[CHECKPOINT] Model calls used: {calls_used}/{MAX_MODEL_CALLS}")
        print(f"[CHECKPOINT] Duration: {duration} seconds")
        print("[CHECKPOINT] Status: success")
        print(f"[CHECKPOINT] Detailed log: {LOG_DIR / 'app.log'}")

    except Exception as error:
        duration = round(time.perf_counter() - started, 2)
        logging.exception(
            "request_id=%s calls=%s duration_seconds=%s status=error",
            request_id, calls_used, duration
        )
        print(f"\n[ERROR] {type(error).__name__}: {error}")
        print(f"[CHECKPOINT] Request ID: {request_id}")
        print(f"[CHECKPOINT] Model calls started: {calls_used}")
        print(f"[CHECKPOINT] Detailed error saved in: {LOG_DIR / 'app.log'}")

    finally:
        if model_client is not None:
            await model_client.close()


if __name__ == "__main__":
    asyncio.run(main())