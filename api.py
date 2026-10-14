import asyncio
import os

from fastapi.responses import PlainTextResponse
from fastapi import FastAPI, HTTPException, Request
from pydantic import BaseModel
from dotenv import load_dotenv
from autogen_agentchat.agents import AssistantAgent
from autogen_ext.models.openai import OpenAIChatCompletionClient

from memory import initialize_database, save_message, get_chat_history
from main import load_company_profile, build_agent_instructions, AGENT_INSTRUCTIONS

load_dotenv()

app = FastAPI(title="Interior AI Customer Support API")


VERIFY_TOKEN = os.getenv("WHATSAPP_VERIFY_TOKEN", "bluewhale_verify_2026")



@app.get("/webhook")
async def verify_whatsapp_webhook(request: Request):
    mode = request.query_params.get("hub.mode")
    token = request.query_params.get("hub.verify_token")
    challenge = request.query_params.get("hub.challenge")

    if mode == "subscribe" and token == VERIFY_TOKEN and challenge:
        return PlainTextResponse(content=challenge, status_code=200)

    return PlainTextResponse(content="Forbidden", status_code=403)


class ChatRequest(BaseModel):
    customer_id: str
    message: str


@app.get("/")
def health_check():
    return {"status": "ok", "message": "Interior AI API is running"}


@app.post("/webhook")
async def receive_whatsapp_webhook(request: Request):
    data = await request.json()
    print("WhatsApp webhook received:", data)
    return {"status": "received"}


@app.post("/chat")
async def receive_chat(request: ChatRequest):
    customer_id = request.customer_id.strip()
    question = request.message.strip()

    if not customer_id or not question:
        raise HTTPException(
            status_code=400,
            detail="Customer ID and message are required.",
        )

    company_profile = load_company_profile()
    if not company_profile:
        raise HTTPException(
            status_code=500,
            detail="Company profile could not be loaded.",
        )

    initialize_database()

    # Retrieve previous conversation
    chat_history = get_chat_history(customer_id)
    history_text = "\n".join(
        f'{item["role"]}: {item["content"]}'
        for item in chat_history
    )

    model_client = None

    try:
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise HTTPException(
                status_code=500,
                detail="OpenAI API key is not configured.",
            )

        model_client = OpenAIChatCompletionClient(
            model="gpt-4o-mini",
            api_key=api_key,
        )

        manager = AssistantAgent(
            name="interior_manager",
            model_client=model_client,
            system_message=f"""
You classify customer questions for
{company_profile.get("company_name", "the company")}.

Business categories:
{__import__("json").dumps(company_profile.get("business_categories", {}), ensure_ascii=False)}

Return exactly one category:
HOME_INTERIOR, COMMERCIAL_INTERIOR, UPVC_PVC_INTERIOR,
B2B_PRODUCTS, or OUT_OF_SCOPE.

Choose the category that best matches the question.
For unrelated questions, return OUT_OF_SCOPE.
Return only the category name.
""",
        )

        routing_result = await manager.run(
            task=f"Classify this customer question: {question}"
        )
        category = routing_result.messages[-1].content.strip().upper()

        if category == "OUT_OF_SCOPE":
            reply = (
                "Sorry, I can only help with interior design "
                "and interior products."
            )
        elif category not in AGENT_INSTRUCTIONS:
            raise HTTPException(
                status_code=500,
                detail="Unexpected category returned by AI.",
            )
        else:
            specialist = AssistantAgent(
                name=category.lower() + "_specialist",
                model_client=model_client,
                system_message=build_agent_instructions(
                    category, company_profile
                ),
            )

            task = (
                f"Previous conversation:\n"
                f"{history_text or 'No previous conversation.'}\n\n"
                f"Current customer question: {question}\n"
                "Use the previous conversation for context. "
                "Give a concise, helpful answer. Never invent "
                "unverified company information."
            )

            result = await specialist.run(task=task)
            reply = result.messages[-1].content

        # Save both messages after generating the reply
        save_message(customer_id, "user", question)
        save_message(customer_id, "assistant", reply)

        return {
            "customer_id": customer_id,
            "category": category,
            "reply": reply,
            "status": "success",
        }

    except HTTPException:
        raise
    except Exception as error:
        logging_error = f"{type(error).__name__}: {error}"
        print(f"Chat API error: {logging_error}")
        raise HTTPException(
            status_code=500,
            detail="Unable to process the customer message.",
        )
    finally:
        if model_client is not None:
            await model_client.close()

