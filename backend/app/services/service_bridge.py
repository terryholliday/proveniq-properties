"""
PROVENIQ Properties - Service Bridge

Integration with PROVENIQ Service for maintenance work orders.
Properties dispatches maintenance to Service, which manages vendor assignment.
"""

import logging
from datetime import datetime
from typing import Optional, List
from uuid import UUID
import httpx

logger = logging.getLogger(__name__)

SERVICE_API_URL = "http://localhost:3008/api"


class ServiceBridge:
    """
    Bridge to PROVENIQ Service for maintenance dispatch.
    
    Properties → Service flow:
    1. Tenant reports issue (Properties)
    2. Landlord approves dispatch (Properties)
    3. Work order created (Service)
    4. Provider assigned and scheduled (Service)
    5. Work completed (Service)
    6. Completion synced back (Properties)
    """
    
    def __init__(self, base_url: str = SERVICE_API_URL):
        self.base_url = base_url
    
    async def create_work_order(
        self,
        property_id: UUID,
        unit_id: Optional[UUID],
        ticket_id: UUID,
        title: str,
        description: str,
        service_domain: str,
        service_type: str,
        urgency: str,
        contact_name: str,
        contact_phone: str,
        address: str,
        requested_by: UUID,
    ) -> Optional[dict]:
        """Create a work order in Service."""
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.base_url}/work-orders",
                    json={
                        "title": title,
                        "description": description,
                        "serviceDomain": service_domain,
                        "serviceType": service_type,
                        "priority": self._map_urgency_to_priority(urgency),
                        "contactName": contact_name,
                        "contactPhone": contact_phone,
                        "address": address,
                        "sourceApp": "properties",
                        "sourceId": str(ticket_id),
                        "metadata": {
                            "property_id": str(property_id),
                            "unit_id": str(unit_id) if unit_id else None,
                            "requested_by": str(requested_by),
                        },
                    },
                    timeout=10.0,
                )
                
                if response.status_code not in (200, 201):
                    logger.warning(f"[SERVICE] Work order creation failed: {response.status_code}")
                    return None
                
                data = response.json()
                logger.info(f"[SERVICE] Work order created: {data.get('id')}")
                return data
        except Exception as e:
            logger.error(f"[SERVICE] Work order creation error: {e}")
            return None
    
    async def get_work_order_status(self, work_order_id: str) -> Optional[dict]:
        """Get work order status from Service."""
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.base_url}/work-orders/{work_order_id}",
                    timeout=10.0,
                )
                
                if response.status_code != 200:
                    return None
                
                return response.json()
        except Exception as e:
            logger.error(f"[SERVICE] Work order status error: {e}")
            return None
    
    async def get_providers_for_service(
        self,
        service_domain: str,
        service_type: str,
        zip_code: Optional[str] = None,
    ) -> List[dict]:
        """Get available providers for a service type."""
        try:
            params = {
                "serviceDomain": service_domain,
                "serviceType": service_type,
            }
            if zip_code:
                params["serviceArea"] = zip_code
            
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.base_url}/providers",
                    params=params,
                    timeout=10.0,
                )
                
                if response.status_code != 200:
                    return []
                
                data = response.json()
                return data.get("providers", data) if isinstance(data, dict) else data
        except Exception as e:
            logger.error(f"[SERVICE] Provider search error: {e}")
            return []
    
    def _map_urgency_to_priority(self, urgency: str) -> str:
        """Map Properties urgency to Service priority."""
        mapping = {
            "emergency": "URGENT",
            "urgent": "HIGH",
            "normal": "MEDIUM",
            "low": "LOW",
        }
        return mapping.get(urgency.lower(), "MEDIUM")


# Singleton
_service_instance: Optional[ServiceBridge] = None


def get_service_bridge() -> ServiceBridge:
    """Get the Service bridge instance."""
    global _service_instance
    if _service_instance is None:
        _service_instance = ServiceBridge()
    return _service_instance
