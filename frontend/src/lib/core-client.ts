
import { AssetProfile, AssetProfileSchema } from './core-contracts';

const CORE_BASE_URL = process.env.NEXT_PUBLIC_CORE_BASE_URL ?? 'http://localhost:3010';
const IS_DEV = process.env.NODE_ENV !== 'production';

export async function getAssetProfile(assetId: string): Promise<AssetProfile> {
    try {
        const res = await fetch(`${CORE_BASE_URL}/api/v1/assets/${assetId}`, {
            headers: {
                'Accept': 'application/json'
            },
            next: { revalidate: 10 } // Cache for 10s if used in server components
        });

        if (!res.ok) {
            // If 404/500, attempt fallback in DEV only
            if (IS_DEV && res.status >= 400) {
                console.warn(`[CoreClient] Fetch failed (${res.status}). Attempting DEV fixture fallback.`);
                return getDevFixture(assetId);
            }
            throw new Error(`Core API Error: ${res.statusText}`);
        }

        const json = await res.json();
        return AssetProfileSchema.parse(json);

    } catch (error) {
        if (IS_DEV) {
            console.warn(`[CoreClient] Network/Parse error. using DEV fixture.`, error);
            return getDevFixture(assetId);
        }
        throw error;
    }
}

// Minimal Fixutre for offline Dev
function getDevFixture(assetId: string): AssetProfile {
    return {
        asset: { asset_id: assetId, owner_subject: "DEV_MOCK", asset_kind: "Property" },
        widgets: [
            {
                type: 'VALUATION_SUMMARY',
                priority_int: 100,
                title: 'Offline Val (Dev)',
                generated_at: new Date().toISOString(),
                source_event_refs: [],
                data: {
                    amount_micros: "1000000000000", // 1M
                    currency: "USD",
                    confidence_score: 0.5,
                    valuation_date: new Date().toISOString()
                }
            },
            {
                type: 'CUSTODY_STATUS',
                priority_int: 90,
                title: 'Offline Custody (Dev)',
                generated_at: new Date().toISOString(),
                source_event_refs: [],
                data: {
                    status: 'CUSTODY',
                    current_custodian: 'DEV_LANDLORD'
                }
            }
        ]
    }
}
