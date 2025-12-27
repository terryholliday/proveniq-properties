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

    async def sync_completion(
        self,
        work_order_id: str,
        ticket_id: UUID,
    ) -> Optional[dict]:
        """Sync work order completion back to Properties maintenance ticket."""
        status = await self.get_work_order_status(work_order_id)
        if not status:
            return None
        
        return {
            "work_order_id": work_order_id,
            "ticket_id": str(ticket_id),
            "status": status.get("status"),
            "completed_at": status.get("completedAt"),
            "provider": status.get("provider"),
            "total_cost_cents": status.get("totalCostCents"),
            "invoice_url": status.get("invoiceUrl"),
            "synced_at": datetime.utcnow().isoformat(),
        }

    async def dispatch_from_inspection(
        self,
        inspection_id: UUID,
        property_id: UUID,
        unit_id: Optional[UUID],
        damaged_items: List[dict],
        contact_name: str,
        contact_phone: str,
        address: str,
        requested_by: UUID,
    ) -> List[dict]:
        """Dispatch work orders for damaged items from inspection.
        
        Groups items by service type and creates one work order per type.
        """
        # Group by service domain
        grouped = {}
        for item in damaged_items:
            domain = self._infer_service_domain(item.get("room_name", ""), item.get("item_name", ""))
            if domain not in grouped:
                grouped[domain] = []
            grouped[domain].append(item)
        
        results = []
        for domain, items in grouped.items():
            item_list = ", ".join([f"{i['room_name']}: {i['item_name']}" for i in items])
            work_order = await self.create_work_order(
                property_id=property_id,
                unit_id=unit_id,
                ticket_id=inspection_id,  # Use inspection ID as source
                title=f"Inspection Repair: {domain}",
                description=f"Items requiring repair from inspection:\n{item_list}",
                service_domain=domain,
                service_type="repair",
                urgency="normal",
                contact_name=contact_name,
                contact_phone=contact_phone,
                address=address,
                requested_by=requested_by,
            )
            if work_order:
                results.append(work_order)
        
        return results

    def _infer_service_domain(self, room_name: str, item_name: str) -> str:
        """Infer service domain from room/item."""
        text = f"{room_name} {item_name}".lower()
        
        if any(kw in text for kw in ["sink", "faucet", "toilet", "shower", "drain", "pipe"]):
            return "plumbing"
        elif any(kw in text for kw in ["outlet", "switch", "light", "electrical", "wire"]):
            return "electrical"
        elif any(kw in text for kw in ["hvac", "heat", "cool", "ac", "furnace"]):
            return "hvac"
        elif any(kw in text for kw in ["door", "window", "lock", "cabinet"]):
            return "carpentry"
        elif any(kw in text for kw in ["paint", "wall", "ceiling"]):
            return "painting"
        elif any(kw in text for kw in ["floor", "carpet", "tile"]):
            return "flooring"
        else:
            return "general"


# Singleton
_service_instance: Optional[ServiceBridge] = None


def get_service_bridge() -> ServiceBridge:
    """Get the Service bridge instance."""
    global _service_instance
    if _service_instance is None:
        _service_instance = ServiceBridge()
    return _service_instance
