"""
PROVENIQ Core API Client for Properties App

Provides:
- Fixture PAID registration
- Fixture valuation
- Damage assessment integration
- Deposit dispute scoring
"""

import os
import httpx
from typing import Optional, Dict, Any, List
from datetime import datetime

CORE_API_URL = os.getenv("CORE_API_URL", "http://localhost:8000")


class CoreClient:
    """Client for PROVENIQ Core API integration."""

    def __init__(self):
        self.base_url = CORE_API_URL
        self.source_app = "proveniq-properties"

    async def register_fixture(
        self,
        landlord_id: str,
        fixture_name: str,
        category: str,
        unit_id: str,
        property_id: str,
        initial_value: Optional[float] = None,
        condition: str = "good",
    ) -> Optional[Dict[str, Any]]:
        """Register a landlord fixture in Core and get PAID."""
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.base_url}/api/v1/registry",
                    json={
                        "ownerId": landlord_id,
                        "ownerType": "organization",
                        "name": fixture_name,
                        "category": category,
                        "sourceApp": "properties",
                        "externalId": f"{property_id}:{unit_id}:{fixture_name}",
                        "initialValue": initial_value,
                        "condition": condition,
                    },
                    headers={"X-Source-App": self.source_app},
                    timeout=10.0,
                )

                if response.status_code == 201:
                    data = response.json()
                    return {
                        "paid": data.get("paid"),
                        "registered_at": data.get("registeredAt"),
                        "status": data.get("status"),
                    }

                print(f"[Core] Fixture registration failed: {response.status_code}")
                return None

        except Exception as e:
            print(f"[Core] Fixture registration error: {e}")
            return None

    async def get_fixture_valuation(
        self,
        paid: str,
        category: str,
        condition: str = "good",
        age_years: float = 0,
    ) -> Optional[Dict[str, Any]]:
        """Get current valuation for a fixture."""
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.base_url}/api/v1/valuations",
                    json={
                        "assetId": paid,
                        "name": "Fixture",
                        "category": category,
                        "condition": condition,
                    },
                    headers={"X-Source-App": self.source_app},
                    timeout=10.0,
                )

                if response.status_code == 200:
                    data = response.json()
                    return {
                        "paid": paid,
                        "estimated_value": data.get("estimatedValue"),
                        "currency": data.get("currency", "USD"),
                        "confidence": data.get("confidence"),
                        "depreciation_rate": data.get("breakdown", {}).get("depreciationRate"),
                        "valued_at": data.get("valuedAt"),
                    }

                print(f"[Core] Fixture valuation failed: {response.status_code}")
                return None

        except Exception as e:
            print(f"[Core] Fixture valuation error: {e}")
            return None

    async def get_deposit_dispute_score(
        self,
        paid: str,
        damage_claimed: float,
        move_in_photos: int,
        move_out_photos: int,
        days_occupied: int,
    ) -> Dict[str, Any]:
        """Get scoring for deposit dispute resolution."""
        try:
            # Get provenance for evidence quality
            provenance = await self._get_provenance(paid, move_in_photos + move_out_photos)

            # Calculate dispute score
            evidence_score = min((move_in_photos + move_out_photos) * 10, 50)
            provenance_score = provenance.get("score", 30) if provenance else 30

            # Tenure factor (longer tenancy = more expected wear)
            tenure_factor = min(days_occupied / 365, 3) * 10  # Max 30 points

            overall_score = evidence_score + (provenance_score * 0.3) + tenure_factor

            # Recommendation based on score
            if overall_score >= 70:
                recommendation = "LANDLORD_FAVOR"
                confidence = "HIGH"
            elif overall_score >= 50:
                recommendation = "SPLIT"
                confidence = "MEDIUM"
            else:
                recommendation = "TENANT_FAVOR"
                confidence = "LOW"

            return {
                "paid": paid,
                "score": round(overall_score, 2),
                "recommendation": recommendation,
                "confidence": confidence,
                "factors": {
                    "evidence_quality": evidence_score,
                    "provenance_score": provenance_score,
                    "tenure_factor": round(tenure_factor, 2),
                },
                "scored_at": datetime.utcnow().isoformat(),
            }

        except Exception as e:
            print(f"[Core] Deposit dispute scoring error: {e}")
            return {
                "paid": paid,
                "score": 50,
                "recommendation": "MANUAL_REVIEW",
                "confidence": "LOW",
                "error": str(e),
            }

    async def batch_valuate_fixtures(
        self,
        fixtures: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """Get valuations for multiple fixtures."""
        results = []
        for fixture in fixtures:
            valuation = await self.get_fixture_valuation(
                paid=fixture.get("paid", fixture.get("id")),
                category=fixture.get("category", "appliances"),
                condition=fixture.get("condition", "good"),
            )
            results.append(valuation or {"paid": fixture.get("paid"), "error": "Failed"})
        return results

    async def assess_damage(
        self,
        paid: str,
        before_image_urls: List[str],
        after_image_urls: List[str],
        category: str = "appliances",
    ) -> Optional[Dict[str, Any]]:
        """P1: Compare before/after condition for damage assessment."""
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.base_url}/api/v1/condition/compare",
                    json={
                        "assetId": paid,
                        "beforeImageUrls": before_image_urls,
                        "afterImageUrls": after_image_urls,
                        "category": category,
                        "context": "inspection",
                    },
                    headers={"X-Source-App": self.source_app},
                    timeout=15.0,
                )

                if response.status_code == 200:
                    data = response.json()
                    print(f"[Core] Damage assessment: {data.get('before', {}).get('condition')} → {data.get('after', {}).get('condition')}")
                    return data

                print(f"[Core] Damage assessment failed: {response.status_code}")
                return None

        except Exception as e:
            print(f"[Core] Damage assessment error: {e}")
            return None

    async def get_deposit_dispute_score(
        self,
        paid: str,
        damage_assessment: Dict[str, Any],
        deposit_amount_cents: int,
        claimed_damage_cents: int,
    ) -> Dict[str, Any]:
        """P1: Score deposit dispute based on damage evidence."""
        try:
            # Calculate score from damage assessment
            deterioration = damage_assessment.get("comparison", {}).get("deteriorationScore", 0)
            recommendation = damage_assessment.get("recommendation", "no_action")
            
            # Evidence strength
            evidence_score = min(deterioration * 2, 100)
            
            # Claim reasonableness
            if claimed_damage_cents > deposit_amount_cents:
                reasonableness = 50  # Claiming more than deposit
            elif claimed_damage_cents > deterioration * deposit_amount_cents / 100:
                reasonableness = 70
            else:
                reasonableness = 90
            
            overall_score = (evidence_score + reasonableness) / 2
            
            if overall_score >= 70:
                verdict = "LANDLORD_FAVOR"
            elif overall_score >= 40:
                verdict = "SPLIT"
            else:
                verdict = "TENANT_FAVOR"

            return {
                "paid": paid,
                "evidenceScore": evidence_score,
                "reasonablenessScore": reasonableness,
                "overallScore": overall_score,
                "verdict": verdict,
                "recommendation": recommendation,
                "deteriorationPercent": deterioration,
                "suggestedDeduction": min(claimed_damage_cents, int(deposit_amount_cents * deterioration / 100)),
            }

        except Exception as e:
            print(f"[Core] Deposit dispute scoring error: {e}")
            return {
                "paid": paid,
                "overallScore": 50,
                "verdict": "MANUAL_REVIEW",
                "error": str(e),
            }

    async def _get_provenance(
        self,
        paid: str,
        image_count: int,
    ) -> Optional[Dict[str, Any]]:
        """Get provenance score for an asset."""
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.base_url}/api/v1/provenance/score",
                    json={
                        "assetId": paid,
                        "hasReceipt": False,
                        "imageCount": image_count,
                        "sourceApp": "properties",
                    },
                    headers={"X-Source-App": self.source_app},
                    timeout=10.0,
                )

                if response.status_code == 200:
                    return response.json()

        except Exception as e:
            print(f"[Core] Provenance error: {e}")

        return None


# Singleton instance
_core_client: Optional[CoreClient] = None


def get_core_client() -> CoreClient:
    """Get singleton Core client instance."""
    global _core_client
    if _core_client is None:
        _core_client = CoreClient()
    return _core_client
