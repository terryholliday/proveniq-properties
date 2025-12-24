
import { z } from 'zod';

// --- PRIMITIVES ---
export const IntString = z.string().regex(/^-?\d+$/, "Must be an integer string");

// --- WIDGET PROTOCOL ---
export const WidgetBaseSchema = z.object({
    priority_int: z.number().int().min(0).max(100),
    title: z.string(),
    generated_at: z.string().datetime(),
    source_event_refs: z.array(z.string())
});

export const ValuationSummaryWidget = WidgetBaseSchema.extend({
    type: z.literal('VALUATION_SUMMARY'),
    data: z.object({
        amount_micros: IntString,
        currency: z.string(),
        confidence_score: z.number().min(0).max(1),
        valuation_date: z.string().datetime()
    })
});

export const CustodyStatusWidget = WidgetBaseSchema.extend({
    type: z.literal('CUSTODY_STATUS'),
    data: z.object({
        status: z.enum(['CUSTODY', 'TRANSIT', 'DISPUTED', 'LOST']),
        current_custodian: z.string(),
        lat: z.number().optional(),
        lon: z.number().optional(),
        last_update: z.string().datetime().optional()
    })
});

export const ProvenanceTimelineWidget = WidgetBaseSchema.extend({
    type: z.literal('PROVENANCE_TIMELINE'),
    data: z.object({
        events: z.array(z.object({
            occurred_at: z.string().datetime(),
            title: z.string(),
            description: z.string(),
            actor: z.string()
        }))
    })
});

export const WidgetSchema = z.discriminatedUnion('type', [
    ValuationSummaryWidget,
    CustodyStatusWidget,
    ProvenanceTimelineWidget
]);

// --- ASSET PROFILE ---
export const BaseAssetSchema = z.object({
    asset_id: z.string(),
    asset_kind: z.string().optional(),
    owner_subject: z.string().optional(),
    // Add other base fields if needed, keep minimal for now
});

export const AssetProfileSchema = z.object({
    asset: BaseAssetSchema,
    widgets: z.array(WidgetSchema)
});

export type Widget = z.infer<typeof WidgetSchema>;
export type AssetProfile = z.infer<typeof AssetProfileSchema>;
