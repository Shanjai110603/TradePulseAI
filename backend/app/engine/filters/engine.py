from datetime import datetime
from typing import Dict, Any, Tuple, Optional
from app.engine.ai.base import AIAnalysisResult


class UserFilterEngine:
    """
    Evaluates candidate signals against global user preferences and pattern-specific overrides.
    Returns clear audit diagnostic reasons if a signal fails any filter.
    """

    @classmethod
    def evaluate_filters(
        cls,
        candidate_data: Dict[str, Any],
        ai_analysis: AIAnalysisResult,
        pattern_config: Dict[str, Any],
        user_preferences: Optional[Dict[str, Any]] = None
    ) -> Tuple[bool, str, Dict[str, Any]]:
        """
        Returns:
            (passed: bool, reason: str, audit_details: dict)
        """
        audit = {}

        # 1. Pattern-Specific AI Settings (Overrides Global)
        ai_cfg = pattern_config.get("ai_config", {})
        if ai_cfg.get("enabled", True):
            min_score = ai_cfg.get("min_score", 70)
            if ai_analysis.score < min_score:
                audit["ai_score"] = {"required": min_score, "actual": ai_analysis.score, "pass": False}
                return False, f"AI Score {ai_analysis.score} is below pattern requirement of {min_score}", audit
            audit["ai_score"] = {"required": min_score, "actual": ai_analysis.score, "pass": True}

            req_bias = ai_cfg.get("required_bias", "ANY").upper()
            if req_bias not in ["ANY", ""]:
                if ai_analysis.bias.upper() != req_bias:
                    audit["ai_bias"] = {"required": req_bias, "actual": ai_analysis.bias, "pass": False}
                    return False, f"AI Bias {ai_analysis.bias} does not match required bias {req_bias}", audit
                audit["ai_bias"] = {"required": req_bias, "actual": ai_analysis.bias, "pass": True}

            min_conf = ai_cfg.get("min_confidence", "MODERATE").upper()
            conf_hierarchy = {"LOW": 1, "MODERATE": 2, "HIGH": 3}
            actual_level = conf_hierarchy.get(ai_analysis.confidence.upper(), 2)
            required_level = conf_hierarchy.get(min_conf, 2)
            if actual_level < required_level:
                audit["ai_confidence"] = {"required": min_conf, "actual": ai_analysis.confidence, "pass": False}
                return False, f"AI Confidence {ai_analysis.confidence} is below required {min_conf}", audit
            audit["ai_confidence"] = {"required": min_conf, "actual": ai_analysis.confidence, "pass": True}

        # 2. Global User Preferences
        if user_preferences:
            global_min_score = user_preferences.get("min_ai_score", 60)
            if ai_analysis.score < global_min_score:
                audit["global_ai_score"] = {"required": global_min_score, "actual": ai_analysis.score, "pass": False}
                return False, f"AI Score {ai_analysis.score} is below global user preference {global_min_score}", audit

            allowed_risks = user_preferences.get("allowed_risk_levels", ["LOW", "MODERATE", "HIGH"])
            risk_text = ai_analysis.risk_assessment.upper()
            is_risk_allowed = any(r in risk_text for r in allowed_risks) if allowed_risks else True
            if not is_risk_allowed:
                audit["global_risk"] = {"allowed": allowed_risks, "actual": ai_analysis.risk_assessment, "pass": False}
                return False, f"AI risk assessment ({ai_analysis.risk_assessment}) not in allowed risk list", audit

        audit["final_decision"] = "PASS"
        return True, "All user and pattern filters successfully passed", audit
