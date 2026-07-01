import os
import logging
import threading
from google import genai
from google.genai.errors import APIError

logger = logging.getLogger(__name__)

class GeminiManager:
    def __init__(self):
        self.keys = []
        self._load_keys()
        self.current_key_index = 0
        self.lock = threading.Lock()
        
        self.preferred_models = ["gemini-3.1-pro", "gemini-3.5-flash", "gemini-2.5-flash", "gemini-2.0-flash"]
        
    def _load_keys(self):
        for idx in range(1, 20):
            key = os.environ.get(f'GEMINI_API_KEY_{idx}') or os.environ.get(f'GEMINI_API_KEY-{idx}')
            if key and key.strip() and key.strip() not in self.keys:
                self.keys.append(key.strip())
            
        single_key = os.environ.get('GEMINI_API_KEY')
        if single_key and single_key.strip() and single_key.strip() not in self.keys:
            self.keys.append(single_key.strip())
            
    def _is_quota_error(self, e):
        err_str = str(e).lower()
        if hasattr(e, 'code') and e.code == 429:
            return True
        for keyword in ["quota exceeded", "resourceexhausted", "rate limit exceeded", "too many requests"]:
            if keyword in err_str.replace(" ", "") or keyword in err_str:
                return True
        return False

    def generate_content(self, prompt):
        last_error_msg = "Unknown error."
        # Reload keys if env changed (useful for testing)
        if not self.keys:
            self._load_keys()
            
        with self.lock:
            keys_count = len(self.keys)
            if keys_count == 0:
                logger.error("[Gemini] No API keys configured.")
                return None
                
            start_key_idx = self.current_key_index
            
            for key_offset in range(keys_count):
                key_idx = (start_key_idx + key_offset) % keys_count
                api_key = self.keys[key_idx]
                
                if key_offset > 0:
                    logger.info(f"[Gemini] Switching to API Key {key_idx + 1}...")
                    
                logger.info(f"[Gemini] Using API Key {key_idx + 1}")
                
                try:
                    client = genai.Client(api_key=api_key)
                except Exception as e:
                    logger.error(f"[Gemini] Failed to initialize Client for Key {key_idx + 1}: {e}")
                    continue
                    
                available_models = []
                try:
                    for m in client.models.list():
                        name = m.name
                        if name.startswith("models/"):
                            name = name.replace("models/", "")
                        available_models.append(name)
                except Exception as e:
                    if self._is_quota_error(e):
                        logger.error(f"[Gemini] API Key {key_idx + 1} quota exceeded during model listing.")
                    else:
                        logger.error(f"[Gemini] API Key {key_idx + 1} failed during model listing: {e}")
                    continue
                    
                supported_models = []
                for pref in self.preferred_models:
                    for am in available_models:
                        if pref in am:
                            supported_models.append(am)
                            break
                            
                if not supported_models:
                    for am in available_models:
                        if 'gemini' in am:
                            supported_models.append(am)
                            
                if not supported_models:
                    logger.error(f"[Gemini] No compatible models found for Key {key_idx + 1}.")
                    continue
                    
                for model_name in supported_models:
                    import time
                    start_time = time.time()
                    try:
                        response = client.models.generate_content(
                            model=model_name,
                            contents=prompt
                        )
                        if response and response.text:
                            self.current_key_index = key_idx
                            response_time = time.time() - start_time
                            logger.info(f"Selected API Key Index: {key_idx + 1}")
                            logger.info(f"Selected Model: {model_name}")
                            logger.info(f"Prompt Length: {len(prompt)} characters")
                            logger.info(f"Response Time: {response_time:.2f} seconds")
                            logger.info(f"Gemini Response: {response.text.strip()[:100]}...")
                            return response.text.strip()
                    except APIError as e:
                        last_error_msg = e.message if hasattr(e, 'message') else str(e)
                        if self._is_quota_error(e):
                            logger.error(f"[Gemini] API Key {key_idx + 1} quota exceeded for model {model_name}.")
                            continue 
                        else:
                            logger.error(f"[Gemini] APIError for Key {key_idx + 1}, model {model_name}: {last_error_msg}")
                            continue 
                    except Exception as e:
                        last_error_msg = str(e)
                        logger.error(f"[Gemini] Error for Key {key_idx + 1}, model {model_name}: {last_error_msg}")
                        continue 
                        
            logger.error("[Gemini] All configured keys and models failed.")
            raise Exception(f"Gemini API completely failed after trying all keys and models. Last Error: {last_error_msg}")

gemini_manager_instance = GeminiManager()

def generate_with_failover(prompt):
    return gemini_manager_instance.generate_content(prompt)
