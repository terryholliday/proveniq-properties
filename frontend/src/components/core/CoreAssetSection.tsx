"use client";

/**
 * CoreAssetSection
 * 
 * Displays asset information from Proveniq Core.
 * Uses useAsset hook + WidgetRenderer.
 * NO direct DB access - all data flows through Core.
 */

import React, { useState, useEffect, useCallback, useRef } from "react";

// =============================================================================
// TYPES (inline to avoid cross-repo dependencies)
// =============================================================================

type AssetView = "OPS" | "PROPERTIES" | "HOME" | "BIDS";

interface Widget {
    widget_type: string;
    priority: number;
    data: Record<string, unknown>;
}

interface UniversalAssetProfile {
    schema_version: string;
    requested_view: AssetView;
    identity: {
        paid: string;
        name: string;
        description?: string;
        category: string;
        subcategory?: string;
        brand?: string;
        model?: string;
        serial_number?: string;
        anchor_id?: string;
    };
    ownership: {
        current_owner_id: string;
        ownership_type: string;
        acquired_at?: string;
        acquisition_method?: string;
    };
    integrity: {
        provenance_score: number;
        integrity_verified: boolean;
        last_verified_at: string | null;
        event_count: number;
        anchor_sealed?: boolean;
    };
    widgets: Widget[];
    profile_generated_at: string;
    cache_ttl_seconds?: number;
}

// =============================================================================
// CORE CLIENT (inline implementation)
// =============================================================================

const CORE_API_URL = process.env.NEXT_PUBLIC_CORE_API_URL || "http://localhost:8000";

async function fetchAssetProfile(
    assetId: string,
    view: AssetView = "PROPERTIES"
): Promise<UniversalAssetProfile> {
    const response = await fetch(
        `${CORE_API_URL}/core/asset/${encodeURIComponent(assetId)}?view=${view}`,
        {
            method: "GET",
            headers: { "Content-Type": "application/json" },
        }
    );

    if (!response.ok) {
        if (response.status === 404) {
            throw new Error("ASSET_NOT_FOUND");
        }
        throw new Error(`CORE_ERROR: ${response.status}`);
    }

    return response.json();
}

// =============================================================================
// HOOK
// =============================================================================

function useAsset(assetId: string | null, view: AssetView = "PROPERTIES") {
    const [data, setData] = useState<UniversalAssetProfile | null>(null);
    const [isLoading, setIsLoading] = useState(false);
    const [error, setError] = useState<string | null>(null);
    const mountedRef = useRef(true);

    const fetchData = useCallback(async () => {
        if (!assetId) {
            setData(null);
            return;
        }

        setIsLoading(true);
        setError(null);

        try {
            const profile = await fetchAssetProfile(assetId, view);
            if (mountedRef.current) {
                setData(profile);
            }
        } catch (err) {
            if (mountedRef.current) {
                setError(err instanceof Error ? err.message : "Unknown error");
            }
        } finally {
            if (mountedRef.current) {
                setIsLoading(false);
            }
        }
    }, [assetId, view]);

    useEffect(() => {
        mountedRef.current = true;
        fetchData();
        return () => {
            mountedRef.current = false;
        };
    }, [fetchData]);

    return { data, isLoading, error, refetch: fetchData };
}

// =============================================================================
// WIDGET COMPONENTS
// =============================================================================

function ProvenanceScore({ score }: { score: number }) {
    const color = score >= 80 ? "green" : score >= 50 ? "yellow" : "red";
    const colorClasses = {
        green: "bg-green-100 text-green-700 border-green-200",
        yellow: "bg-yellow-100 text-yellow-700 border-yellow-200",
        red: "bg-red-100 text-red-700 border-red-200",
    };

    return (
        <div className={`px-3 py-1.5 rounded-lg border ${colorClasses[color]}`}>
            <span className="font-semibold">{score}%</span>
            <span className="text-sm ml-1">Provenance</span>
        </div>
    );
}

function WidgetCard({ widget }: { widget: Widget }) {
    const { widget_type, data } = widget;

    // Render based on widget type
    switch (widget_type) {
        case "CUSTODY_STATUS":
            return (
                <div className="bg-white border rounded-lg p-4">
                    <h4 className="text-sm font-medium text-slate-500 mb-2">Custody Status</h4>
                    <div className="flex items-center gap-2">
                        <span className="text-lg font-semibold">
                            {(data.current_state as string)?.replace("_", " ")}
                        </span>
                    </div>
                    {data.last_transition_at && (
                        <p className="text-xs text-slate-400 mt-1">
                            Since {new Date(data.last_transition_at as string).toLocaleDateString()}
                        </p>
                    )}
                </div>
            );

        case "VALUATION_SUMMARY":
            return (
                <div className="bg-white border rounded-lg p-4">
                    <h4 className="text-sm font-medium text-slate-500 mb-2">Valuation</h4>
                    <p className="text-2xl font-bold">
                        ${((data.current_value_cents as number) / 100).toLocaleString()}
                    </p>
                    <p className="text-xs text-slate-400">
                        Confidence: {data.confidence_level as string}
                    </p>
                </div>
            );

        case "RISK_BADGE":
            const riskColors: Record<string, string> = {
                LOW: "bg-green-100 text-green-700",
                MEDIUM: "bg-yellow-100 text-yellow-700",
                HIGH: "bg-orange-100 text-orange-700",
                CRITICAL: "bg-red-100 text-red-700",
            };
            return (
                <div className="bg-white border rounded-lg p-4">
                    <h4 className="text-sm font-medium text-slate-500 mb-2">Risk Assessment</h4>
                    <div className="flex items-center gap-3">
                        <span className="text-2xl font-bold">{data.fraud_score as number}</span>
                        <span className={`px-2 py-1 rounded text-xs font-medium ${riskColors[(data.risk_level as string)] || "bg-slate-100"}`}>
                            {data.risk_level as string}
                        </span>
                    </div>
                </div>
            );

        case "SERVICE_TIMELINE":
            const records = (data.records as Array<Record<string, unknown>>) || [];
            return (
                <div className="bg-white border rounded-lg p-4">
                    <h4 className="text-sm font-medium text-slate-500 mb-2">
                        Service History ({records.length})
                    </h4>
                    {records.length > 0 ? (
                        <div className="space-y-2">
                            {records.slice(0, 3).map((r, i) => (
                                <div key={i} className="text-sm flex justify-between">
                                    <span>{r.service_type as string}</span>
                                    <span className="text-slate-400">{r.status as string}</span>
                                </div>
                            ))}
                        </div>
                    ) : (
                        <p className="text-sm text-slate-400">No service records</p>
                    )}
                </div>
            );

        case "PROVENANCE_TIMELINE":
            const events = (data.events as Array<Record<string, unknown>>) || [];
            return (
                <div className="bg-white border rounded-lg p-4">
                    <h4 className="text-sm font-medium text-slate-500 mb-2">
                        Provenance ({data.total_events as number} events)
                    </h4>
                    {events.length > 0 ? (
                        <div className="space-y-2">
                            {events.slice(0, 3).map((e, i) => (
                                <div key={i} className="text-sm">
                                    <span className="font-medium">{(e.event_type as string)?.replace(/_/g, " ")}</span>
                                    <span className="text-slate-400 ml-2">
                                        {new Date(e.occurred_at as string).toLocaleDateString()}
                                    </span>
                                </div>
                            ))}
                        </div>
                    ) : (
                        <p className="text-sm text-slate-400">No events</p>
                    )}
                </div>
            );

        default:
            // Unknown widget - render placeholder in dev only
            if (process.env.NODE_ENV === "development") {
                return (
                    <div className="bg-yellow-50 border border-yellow-200 rounded-lg p-4">
                        <p className="text-sm text-yellow-700">Unknown widget: {widget_type}</p>
                    </div>
                );
            }
            return null;
    }
}

// =============================================================================
// MAIN COMPONENT
// =============================================================================

interface CoreAssetSectionProps {
    assetId: string;
    className?: string;
}

export function CoreAssetSection({ assetId, className = "" }: CoreAssetSectionProps) {
    const { data: profile, isLoading, error, refetch } = useAsset(assetId, "PROPERTIES");

    if (isLoading) {
        return (
            <div className={`bg-slate-50 rounded-xl p-6 ${className}`}>
                <div className="animate-pulse space-y-4">
                    <div className="h-6 bg-slate-200 rounded w-1/3"></div>
                    <div className="grid grid-cols-2 gap-4">
                        <div className="h-24 bg-slate-200 rounded"></div>
                        <div className="h-24 bg-slate-200 rounded"></div>
                    </div>
                </div>
            </div>
        );
    }

    if (error) {
        if (error === "ASSET_NOT_FOUND") {
            return (
                <div className={`bg-slate-50 rounded-xl p-6 text-center ${className}`}>
                    <p className="text-slate-500">Asset not registered with Core</p>
                    <button
                        onClick={() => refetch()}
                        className="mt-2 text-sm text-blue-600 hover:underline"
                    >
                        Retry
                    </button>
                </div>
            );
        }

        return (
            <div className={`bg-red-50 rounded-xl p-6 ${className}`}>
                <p className="text-red-600 font-medium">Failed to load from Core</p>
                <p className="text-sm text-red-500">{error}</p>
                <button
                    onClick={() => refetch()}
                    className="mt-2 text-sm text-red-600 hover:underline"
                >
                    Retry
                </button>
            </div>
        );
    }

    if (!profile) {
        return null;
    }

    // Sort widgets by priority
    const sortedWidgets = [...profile.widgets].sort((a, b) => a.priority - b.priority);

    return (
        <div className={`bg-white rounded-xl border ${className}`}>
            {/* Header */}
            <div className="p-6 border-b">
                <div className="flex items-start justify-between">
                    <div>
                        <h3 className="text-lg font-semibold">Core Asset Profile</h3>
                        <p className="text-sm text-slate-500 mt-1">
                            {profile.identity.category}
                            {profile.identity.subcategory && ` / ${profile.identity.subcategory}`}
                        </p>
                    </div>
                    <ProvenanceScore score={profile.integrity.provenance_score} />
                </div>

                {/* PAID */}
                <div className="mt-3 text-xs text-slate-400 font-mono">
                    PAID: {profile.identity.paid}
                </div>
            </div>

            {/* Widgets */}
            <div className="p-6">
                {sortedWidgets.length > 0 ? (
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                        {sortedWidgets.map((widget, index) => (
                            <WidgetCard key={`${widget.widget_type}-${index}`} widget={widget} />
                        ))}
                    </div>
                ) : (
                    <p className="text-center text-slate-400 py-4">
                        No widgets available for this view
                    </p>
                )}
            </div>

            {/* Footer */}
            <div className="px-6 py-3 bg-slate-50 border-t text-xs text-slate-400">
                Last updated: {new Date(profile.profile_generated_at).toLocaleString()}
            </div>
        </div>
    );
}
