"""
FILE: src/llm_manager.py
DESCRIPTION: Hybrid LLM interface managing local low-cost models via Ollama and high-power models via Groq.
"""
import os
from langchain_ollama import OllamaLLM
from groq import Groq

class LLMManager:
    def __init__(self):
        self.groq_client = Groq(api_key=os.environ.get("GROQ_API_KEY", "mock_key"))
        # You'll need ollama running locally with `ollama run llama3.2:1b` or similar
        self.local_llm = OllamaLLM(model="llama3.2:1b")
        self.groq_model = "llama-3.3-70b-versatile"

    def execute_micro_task(self, system_prompt: str, user_prompt: str, expect_json: bool = True) -> str:
        """Runs a localized cheap task (e.g., formatting/data extraction)."""
        prompt = f"{system_prompt}\n\nUser: {user_prompt}"
        if expect_json:
             prompt += "\nOutput MUST be strictly valid JSON. Do not include markdown formatting or introductory text."
             
        try:
            res = self.local_llm.invoke(prompt)
            if expect_json:
                import re
                import json
                import ast
                match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", res, re.DOTALL)
                if match:
                    res = match.group(1)
                else:
                    start = res.find('{')
                    end = res.rfind('}')
                    if start != -1 and end != -1:
                        res = res[start:end+1]
                # Fix single-quotes and invalid JSON from tiny models
                try:
                    json.loads(res)
                except Exception:
                    try:
                        res = json.dumps(ast.literal_eval(res))
                    except Exception:
                        pass
            return res
        except Exception as e:
            # If Ollama is not installed/running, fallback to Groq to prevent crash during testing
            print(f"Local LLM not reached, falling back to Groq: {e}")
            return self.execute_macro_task(system_prompt, user_prompt)

    def execute_macro_task(self, system_prompt: str, user_prompt: str) -> str:
        """Runs a heavy reasoning task via Groq API."""
        try:
            completion = self.groq_client.chat.completions.create(
                model=self.groq_model,
                messages=[
                    {"role": "system", "content": system_prompt + " You MUST output valid JSON."},
                    {"role": "user", "content": user_prompt}
                ],
                response_format={"type": "json_object"},
                temperature=0.1
            )
            return completion.choices[0].message.content
        except Exception as e:
            print(f"Groq API Error: {e}")
            return '{"error": "API failed", "action": "HOLD", "confidence": 0}'
