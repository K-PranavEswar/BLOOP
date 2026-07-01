import os
import sys
from dotenv import load_dotenv

try:
    from app.services.gemini_manager import gemini_manager_instance
except ImportError as e:
    print(f"[-] ERROR importing GeminiManager: {e}")
    sys.exit(1)

def test_gemini_failover():
    print("=== Testing Gemini API Failover Manager ===")
    
    load_dotenv()
    
    # 1. Verify API Keys loaded
    if not gemini_manager_instance.keys:
        print("[-] ERROR: No GEMINI_API_KEY_* found in environment.")
        print("[-] Please ensure your .env file contains: GEMINI_API_KEY_1=..., GEMINI_API_KEY_2=..., etc.")
        return
        
    print(f"[+] Loaded {len(gemini_manager_instance.keys)} API Keys from environment.")
    
    # 2. Send a simple prompt
    print("\n=== Testing AI Generation & Failover ===")
    prompt = "Reply with 'Hello, HemoPulse AI failover is working!' if you can read this."
    print(f"Prompt: {prompt}")
    print("Check server logs (or standard output) for the failover switching process.")
    
    response = gemini_manager_instance.generate_content(prompt)
    
    if response:
        print("\n[+] AI Response received:")
        print("-" * 40)
        print(response)
        print("-" * 40)
        print(f"\n[+] SUCCESS: Currently using API Key Index {gemini_manager_instance.current_key_index + 1}.")
    else:
        print("\n[-] ERROR: All configured keys and models failed to generate content.")

if __name__ == "__main__":
    test_gemini_failover()