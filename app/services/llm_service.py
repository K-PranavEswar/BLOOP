"""
LLM Service for HemoPulse AI Pro
Integrates Google's latest GenAI SDK via centralized GeminiManager for actionable AI Insights.
"""
import json
import logging
import threading
from app.extensions import db
from app.services.gemini_manager import generate_with_failover
from app.services.ai_risk_engine import calculate_global_risk
from app.models.ai_analysis_log import AIAnalysisLog

logger = logging.getLogger(__name__)

def run_and_log_analysis_async(app_context):
    """
    Spawns a background thread to run the mathematical analysis, call Gemini, and log the result.
    Requires passing the Flask app context.
    """
    def task():
        with app_context():
            try:
                # 1. Run Mathematical Risk Engine
                engine_data = calculate_global_risk()
                
                # Standardize risk output for Gemini prompt
                # engine_data contains 'blood_groups', 'global_stats', 'critical_group'
                
                # We will just analyze the top critical alert, or global if none
                alerts = engine_data.get('alerts', [])
                if not alerts:
                    return
                
                target_alert = alerts[0] # The highest severity alert
                blood_group = target_alert['blood_group']
                risk_level = target_alert['risk_level']
                confidence = target_alert['confidence']
                
                # 2. Call Gemini strictly for analysis, not prediction
                prompt = f"""
                You are an expert AI Health Assistant for a Blood Bank Management System (HemoPulse AI Pro).
                The Mathematical Risk Analysis Engine has calculated the following strict data for blood group {blood_group}:
                
                {json.dumps(target_alert, indent=2)}
                
                Global Hospital Readiness Score: {engine_data['hospital_readiness_score']}%
                Global Inventory Health Score: {engine_data['inventory_health_score']}%
                
                Your task is to EXPLAIN this data and provide recommendations. 
                DO NOT change the calculations. DO NOT perform predictions.
                
                Respond STRICTLY in the following JSON format:
                {{
                    "situation_summary": "Concise 1-2 sentence summary of the situation.",
                    "medical_risk_explanation": "Explanation of clinical risk.",
                    "inventory_analysis": "Analysis of the stock and demand.",
                    "emergency_recommendations": "Actionable emergency steps.",
                    "donation_campaign_suggestions": "Steps to acquire more blood.",
                    "hospital_coordination_suggestions": "Steps for hospital transfers/prep.",
                    "priority_level": "{risk_level}",
                    "confidence_explanation": "Why the system confidence is {confidence}%."
                }}
                """
                
                # Add formatting instructions to ensure clean JSON
                prompt += "\n\nOutput only raw JSON, no markdown formatting."
                
                model_used = 'gemini-manager'
                recommendation_json = ""
                
                try:
                    response_text = generate_with_failover(prompt)
                    if response_text:
                        # Clean markdown if present
                        cleaned = response_text.replace("```json", "").replace("```", "").strip()
                        # Verify it's valid JSON
                        json.loads(cleaned)
                        recommendation_json = cleaned
                except Exception as e:
                    logger.error(f"Unexpected error in LLM service: {e}")
                    
                if not recommendation_json:
                    logger.error("Cloud AI is temporarily unavailable. Local AI prediction engine is active.")
                    recommendation_json = _rule_based_fallback(target_alert)
                    model_used = 'rule-based'
                    
                # 3. Log to Database
                log_entry = AIAnalysisLog(
                    blood_group=blood_group,
                    risk_level=risk_level,
                    prediction_data=json.dumps(target_alert),
                    recommendation_data=recommendation_json,
                    model_used=model_used,
                    confidence=confidence
                )
                db.session.add(log_entry)
                db.session.commit()
                logger.info(f"[AI Engine] Successfully logged analysis for {blood_group}")
                
            except Exception as e:
                logger.error(f"[AI Engine] Background task failed: {e}")
                db.session.rollback()

    thread = threading.Thread(target=task)
    thread.start()


def _rule_based_fallback(alert):
    """
    Rule-based text generation if Gemini is unavailable or fails.
    Outputs the exact JSON format expected by the dashboard.
    """
    risk = alert['risk_level']
    blood = alert['blood_group']
    days = alert['remaining_days']
    
    situation = f"Current inventory of {blood} blood is at {risk} levels."
    action = "Continue standard operations."
    campaign = "Standard donation drives."
    
    if risk == 'CRITICAL':
        situation = f"Current inventory of {blood} blood is critically below the predicted demand."
        action = "Immediate emergency blood donation campaigns are recommended."
        campaign = f"Target {blood} donors urgently via SMS."
    elif risk == 'HIGH':
        situation = f"{blood} inventory is significantly below safety thresholds."
        action = "Prepare for potential shortages."
        campaign = "Schedule priority donation camps this week."
        
    fallback_data = {
        "situation_summary": situation,
        "medical_risk_explanation": f"Based on historical and predicted consumption, {blood} availability is at risk.",
        "inventory_analysis": f"Stock is {alert['current_stock']}, predicted demand is {alert['predicted_demand']}.",
        "emergency_recommendations": action,
        "donation_campaign_suggestions": campaign,
        "hospital_coordination_suggestions": "Review pending emergency requests.",
        "priority_level": risk,
        "confidence_explanation": f"Based on strict mathematical calculation scoring {alert['confidence']}%."
    }
    return json.dumps(fallback_data)


def generate_insights(*args, **kwargs):
    """
    Backward compatibility wrapper to prevent ImportError.
    Since insights are now generated asynchronously via run_and_log_analysis_async,
    this function fetches the latest generated insight from the database,
    or returns a fallback string if none exists, ensuring older templates don't break.
    """
    try:
        from app.models.ai_analysis_log import AIAnalysisLog
        latest = AIAnalysisLog.query.order_by(AIAnalysisLog.created_at.desc()).first()
        if latest:
            data = latest.get_recommendation_dict()
            if data and "situation_summary" in data:
                return data["situation_summary"]
    except Exception as e:
        logger.error(f"Error in generate_insights wrapper: {e}")
        
    return "System is operating normally. AI monitoring is active."
