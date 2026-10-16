import os
import sys
import json
from dotenv import load_dotenv

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
load_dotenv("backend/.env")

from backend.services.ai_service import build_system_prompt, _get_mistral, MISTRAL_MODEL, _load_json_docs, _format_context

agents_config = [
    {
        "name": "Competition Analysis",
        "file_prefix": "01_competition_analysis",
        "inputs": """Generate a complete competitive analysis strategy report for Coca-Cola vs Pepsi and Dr Pepper based on scanned knowledge base data.

── Additional Context ──
Q: Which specific competitors concern you most and why?
A: PepsiCo and Dr Pepper Snapple Group due to aggressive non-sugar and energy drink expansion.

Q: What market or geography should we focus on?
A: North America and Western Europe.

Q: What differentiators do you believe you have over competitors?
A: Global distribution infrastructure, unmatched brand loyalty, and iconic heritage marketing."""
    },
    {
        "name": "GTM Strategy",
        "file_prefix": "02_gtm_strategy",
        "inputs": """Generate a complete Go-To-Market (GTM) Strategy for Coca-Cola.

── Additional Context ──
Q: Who is your primary target customer segment?
A: Gen Z and Young Professionals (Ages 18-35).

Q: What channels are you prioritising?
A: Digital Social (Instagram, TikTok), Retail Partnerships, Event Sponsorships.

Q: What is your launch timeline and budget range?
A: 90-Day Rapid Scale, $5M Launch Budget."""
    },
    {
        "name": "Product Launch Strategy",
        "file_prefix": "03_product_launch_strategy",
        "inputs": """Generate a complete Product Launch Strategy for Coca-Cola.

── Additional Context ──
Q: What are you launching?
A: New Product (Coca-Cola Zero Sugar Energy Infusion)

Q: What is the primary objective of this launch?
A: Generate Sales & Rapid Market Penetration

Q: What is your planned launch timeline?
A: 1–3 Months"""
    }
]

def run_all():
    os.makedirs("scratch/prompts", exist_ok=True)
    os.makedirs("scratch/outputs", exist_ok=True)
    
    brand_name = "Coca-Cola"
    brand_slug = "coca_cola"
    docs = _load_json_docs(brand_slug)
    formatted_context = ""
    if docs:
        parts = []
        for i, doc in enumerate(docs[:3], 1):
            parts.append(f"[Source {i} — {doc.get('title', 'Doc')}]\n{doc.get('content', '')[:1000]}")
        formatted_context = "\n\n".join(parts)
        
    client = _get_mistral()
    
    results = []
    
    for agent in agents_config:
        agent_name = agent["name"]
        prefix = agent["file_prefix"]
        print(f"\n==========================================")
        print(f" PROCESSING AGENT: {agent_name}")
        print(f"==========================================")
        
        # Build prompt
        prompt = build_system_prompt(brand_name, agent_name, "Coca-Cola Global Beverage Division", formatted_context)
        prompt_path = f"scratch/prompts/{prefix}_prompt.txt"
        with open(prompt_path, "w", encoding="utf-8") as f:
            f.write(prompt)
        print(f"Prompt saved to {prompt_path} ({len(prompt)} chars)")
        
        # Generate output
        messages = [
            {"role": "system", "content": prompt},
            {"role": "user", "content": agent["inputs"]}
        ]
        
        print(f"Calling Mistral API for {agent_name}...")
        res = client.chat.completions.create(
            model=MISTRAL_MODEL,
            messages=messages,
            temperature=0.3
        )
        
        output_text = res.choices[0].message.content
        output_path = f"scratch/outputs/{prefix}_output.md"
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(output_text)
        print(f"Output saved to {output_path} ({len(output_text)} chars)")
        
        results.append({
            "agent_name": agent_name,
            "prefix": prefix,
            "prompt_path": prompt_path,
            "output_path": output_path,
            "prompt": prompt,
            "output": output_text
        })
        
    print("\nAll 3 agent outputs successfully generated!")
    return results

if __name__ == "__main__":
    run_all()
