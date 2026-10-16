import os
import json
import asyncio
from dotenv import load_dotenv

# Load env variables
load_dotenv("backend/.env")

from backend.services.ai_service import build_system_prompt, _get_mistral, MISTRAL_MODEL, _load_json_docs, _format_context

def run_test():
    brand_name = "Coca-Cola"
    brand_slug = "coca_cola"
    agent_type = "Product Launch Strategy"
    
    # Load knowledge base context
    docs = _load_json_docs(brand_slug)
    formatted_context = ""
    if docs:
        formatted_context = _format_context(docs[:3])
    
    # User inputs for Product Launch Strategy
    user_input_prompt = """Generate a complete Product Launch Strategy for Coca-Cola.

── Additional Context ──
Q: What are you launching?
A: New Product

Q: What is the primary objective of this launch?
A: Generate Sales

Q: What is your planned launch timeline?
A: 1–3 Months"""

    # Build system prompt
    system_prompt = build_system_prompt(brand_name, agent_type, "Coca-Cola Global Beverage Division", formatted_context)
    
    print("=== SYSTEM PROMPT BUILT (Length: {} chars) ===".format(len(system_prompt)))
    
    # Save system prompt to scratch file
    os.makedirs("scratch", exist_ok=True)
    with open("scratch/product_launch_backend_prompt.txt", "w", encoding="utf-8") as f:
        f.write(system_prompt)
        
    # Call Mistral LLM to generate response
    client = _get_mistral()
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_input_prompt}
    ]
    
    print("Sending request to Mistral API...")
    res = client.chat.completions.create(
        model=MISTRAL_MODEL,
        messages=messages,
        temperature=0.3
    )
    
    generated_output = res.choices[0].message.content
    print("=== GENERATED OUTPUT RECEIVED (Length: {} chars) ===".format(len(generated_output)))
    
    with open("scratch/product_launch_generated_output.md", "w", encoding="utf-8") as f:
        f.write(generated_output)
        
    print("Successfully saved prompt and generated output!")

if __name__ == "__main__":
    run_test()
