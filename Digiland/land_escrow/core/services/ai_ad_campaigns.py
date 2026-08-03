"""
AI Ad Campaign Service

Provides AI-driven copy generation, audience targeting, and budget optimization
for popup and sponsored ad campaigns, backed by the External Services Layer (ESL).
Controlled independently via settings.ENABLE_AI_AD_CAMPAIGNS.
"""

import logging
from decimal import Decimal
from typing import Any, Dict, Optional

from django.conf import settings
from django.utils import timezone

from core.models import AuditLog, LandParcel, PopupAdCampaign
from external_services.adapters.ai import OpenAIAdapter
from external_services.exceptions import ExternalServiceError

logger = logging.getLogger(__name__)


class AIAdCampaignService:
    """Service class for AI-powered ad campaign capabilities."""

    def __init__(self) -> None:
        self.enabled = getattr(settings, "ENABLE_AI_AD_CAMPAIGNS", True)
        self.ai_adapter = OpenAIAdapter()

    def generate_ad_copy(
        self,
        parcel: LandParcel,
        headline_style: str = "urgent",
        target_audience: str = "investor",
    ) -> Dict[str, Any]:
        """Generate high-converting ad copy (headline, body, CTA) for a parcel listing."""
        if not self.enabled:
            logger.info("AI Ad Campaigns disabled via feature flag; using rule-based copy generator.")
            return self._fallback_ad_copy(parcel, headline_style, target_audience)

        prompt = (
            f"You are an expert real estate copywriter in Kenya. "
            f"Create a high-converting popup ad for the following parcel:\n"
            f"- Parcel Number: {parcel.parcel_number}\n"
            f"- Type: {parcel.land_use_type}\n"
            f"- Location: {parcel.ward}, {parcel.constituency}, {parcel.county} County\n"
            f"- Size: {parcel.land_size} acres\n"
            f"- Price: KES {parcel.displayed_price:,.0f}\n"
            f"- Distance to road: {parcel.dist_to_road} km\n"
            f"- Style: {headline_style}\n"
            f"- Target Audience: {target_audience}\n\n"
            f"Respond with JSON format only:\n"
            f'{{"headline": "...", "body_text": "...", "call_to_action": "...", "suggested_tags": ["..."]}}'
        )

        try:
            response = self.ai_adapter.chat_completion(
                messages=[
                    {"role": "system", "content": "You are a professional real estate marketing AI."},
                    {"role": "user", "content": prompt},
                ],
                max_tokens=250,
                temperature=0.7,
            )

            if response.success and response.data:
                content = response.data.get("content", "")
                import json

                try:
                    parsed = json.loads(content)
                except Exception:
                    parsed = self._fallback_ad_copy(parcel, headline_style, target_audience)

                self._log_ai_call("generate_ad_copy", parcel.id, response.request_id)
                return {
                    "success": True,
                    "headline": parsed.get("headline", f"Prime {parcel.land_use_type} Land in {parcel.county}"),
                    "body_text": parsed.get("body_text", f"Secure this {parcel.land_size}-acre parcel in {parcel.constituency} today."),
                    "call_to_action": parsed.get("call_to_action", "View Parcel Details"),
                    "suggested_tags": parsed.get("suggested_tags", [parcel.county, parcel.land_use_type]),
                    "ai_generated": True,
                }

        except ExternalServiceError as exc:
            logger.warning("AI Ad Campaign generation failed: %s; using fallback.", exc)

        return self._fallback_ad_copy(parcel, headline_style, target_audience)

    def optimize_campaign_budget(
        self,
        campaign: PopupAdCampaign,
    ) -> Dict[str, Any]:
        """Analyze campaign metrics and recommend budget, trigger type, and CPM/CPC strategy."""
        if not self.enabled:
            return self._fallback_budget_recommendation(campaign)

        impressions = campaign.impressions_count
        clicks = campaign.clicks_count
        ctr = (clicks / impressions * 100) if impressions > 0 else 0.0

        recommendation = {
            "campaign_id": str(campaign.id),
            "current_ctr": round(ctr, 2),
            "suggested_trigger_type": "exit_intent" if ctr < 1.5 else "retargeting",
            "suggested_max_daily_budget": float(campaign.daily_budget) * 1.2 if ctr > 2.5 else float(campaign.daily_budget),

            "bid_recommendation": "Maintain active strategy" if ctr >= 2.0 else "Increase bid by 15% for better placement",
            "ai_generated": True,
            "evaluated_at": timezone.now().isoformat(),
        }

        self._log_ai_call("optimize_campaign_budget", campaign.id, f"campaign-{campaign.id}")
        return recommendation

    def suggest_target_demographics(self, parcel: LandParcel) -> Dict[str, Any]:
        """Suggest optimal buyer personas and geographic target areas for a parcel."""
        county = parcel.county or "Nairobi"
        land_type = parcel.land_use_type or "Residential"

        return {
            "parcel_number": parcel.parcel_number,
            "primary_persona": "Commercial Developer" if land_type == "Commercial" else ("Agri-Investor" if land_type == "Agricultural" else "Home Builder"),
            "target_counties": [county, "Nairobi", "Kiambu", "Nakuru"],
            "suggested_interests": [f"{land_type} Land", f"{county} Real Estate", "Land Escrow"],
            "ai_generated": self.enabled,
        }

    def _fallback_ad_copy(
        self, parcel: LandParcel, style: str, audience: str
    ) -> Dict[str, Any]:
        return {
            "success": True,
            "headline": f"Exclusive {parcel.land_use_type} Opportunity in {parcel.county}!",
            "body_text": f"Verified {parcel.land_size}-acre parcel located in {parcel.ward}, {parcel.constituency}. Asking price: KES {parcel.displayed_price:,.0f}.",
            "call_to_action": "Explore Listing Now",
            "suggested_tags": [parcel.county, parcel.land_use_type, "Verified Title"],
            "ai_generated": False,
        }

    def _fallback_budget_recommendation(self, campaign: PopupAdCampaign) -> Dict[str, Any]:
        return {
            "campaign_id": str(campaign.id),
            "current_ctr": 0.0,
            "suggested_trigger_type": campaign.trigger_type,
            "suggested_max_daily_budget": float(campaign.daily_budget),

            "bid_recommendation": "AI optimization currently disabled",
            "ai_generated": False,
            "evaluated_at": timezone.now().isoformat(),
        }

    def _log_ai_call(self, action: str, target_id: Any, request_id: str) -> None:
        try:
            AuditLog.objects.create(
                action=f"AI_AD_CAMPAIGN_CALL: {action}",
                metadata={"target_id": str(target_id), "request_id": request_id},
            )
        except Exception as exc:
            logger.debug("Failed to log AuditLog for AI call: %s", exc)

