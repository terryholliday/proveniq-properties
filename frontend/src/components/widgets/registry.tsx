
import React from 'react';
import { Widget } from '@/lib/core-contracts';
import {
    DollarSign,
    ShieldCheck,
    History,
    AlertTriangle,
    MapPin,
    Clock
} from 'lucide-react';
import { Button } from '@/components/ui/button';

// --- HELPER: MICROS TO CURRENCY ---
const formatMicros = (micros: string, currency: string) => {
    try {
        const val = BigInt(micros);
        const floatVal = Number(val) / 1_000_000;
        return new Intl.NumberFormat('en-US', { style: 'currency', currency: currency }).format(floatVal);
    } catch {
        return `${micros} (raw)`;
    }
};

// --- WIDGET IMPLEMENTATIONS ---

const ValuationSummaryWidget: React.FC<{ widget: Extract<Widget, { type: 'VALUATION_SUMMARY' }> }> = ({ widget }) => {
    const { data } = widget;
    return (
        <div className="bg-white rounded-xl border p-6 flex flex-col justify-between h-full">
            <div>
                <div className="flex items-center gap-2 mb-2">
                    <div className="p-2 bg-green-100 rounded-lg text-green-600">
                        <DollarSign className="h-5 w-5" />
                    </div>
                    <h3 className="text-sm font-medium text-slate-500 uppercase tracking-wide">{widget.title}</h3>
                </div>
                <div className="text-3xl font-bold text-slate-900 mt-2">
                    {formatMicros(data.amount_micros, data.currency)}
                </div>
                <div className="text-xs text-slate-400 mt-1">
                    Confidence: {(data.confidence_score * 100).toFixed(0)}% • {new Date(data.valuation_date).toLocaleDateString()}
                </div>
            </div>
            <div className="mt-6">
                <Button variant="outline" className="w-full text-sm">Refinance Options</Button>
            </div>
        </div>
    );
};

const CustodyStatusWidget: React.FC<{ widget: Extract<Widget, { type: 'CUSTODY_STATUS' }> }> = ({ widget }) => {
    const { data } = widget;
    const isProblem = data.status === 'DISPUTED' || data.status === 'LOST';

    return (
        <div className={`rounded-xl border p-6 h-full ${isProblem ? 'bg-red-50 border-red-200' : 'bg-white'}`}>
            <div className="flex items-center gap-2 mb-4">
                <div className={`p-2 rounded-lg ${isProblem ? 'bg-red-100 text-red-600' : 'bg-blue-100 text-blue-600'}`}>
                    {isProblem ? <AlertTriangle className="h-5 w-5" /> : <ShieldCheck className="h-5 w-5" />}
                </div>
                <h3 className="text-sm font-medium text-slate-500 uppercase tracking-wide">{widget.title}</h3>
            </div>

            <div className="space-y-4">
                <div>
                    <p className="text-xs text-slate-400 uppercase">Status</p>
                    <p className={`text-lg font-bold ${isProblem ? 'text-red-700' : 'text-slate-900'}`}>{data.status}</p>
                </div>
                <div>
                    <p className="text-xs text-slate-400 uppercase">Custodian</p>
                    <p className="text-md font-medium text-slate-900">{data.current_custodian}</p>
                </div>
                {data.last_update && (
                    <div className="flex items-center gap-1 text-xs text-slate-400">
                        <Clock className="h-3 w-3" />
                        <span>Updated {new Date(data.last_update).toLocaleTimeString()}</span>
                    </div>
                )}
            </div>
        </div>
    );
};

const ProvenanceTimelineWidget: React.FC<{ widget: Extract<Widget, { type: 'PROVENANCE_TIMELINE' }> }> = ({ widget }) => {
    const { data } = widget;
    // Show only top 3 recent events
    const recentEvents = data.events.slice(-3);

    return (
        <div className="bg-white rounded-xl border p-6 h-full md:col-span-2 lg:col-span-1">
            <div className="flex items-center gap-2 mb-4">
                <div className="p-2 bg-purple-100 rounded-lg text-purple-600">
                    <History className="h-5 w-5" />
                </div>
                <h3 className="text-sm font-medium text-slate-500 uppercase tracking-wide">{widget.title}</h3>
            </div>
            <div className="space-y-4">
                {recentEvents.length === 0 && <p className="text-slate-400 text-sm italic">No history available.</p>}

                {recentEvents.map((evt, i) => (
                    <div key={i} className="flex gap-3 items-start">
                        <div className="w-1.5 h-1.5 rounded-full bg-slate-300 mt-2 shrink-0" />
                        <div>
                            <p className="text-sm font-medium text-slate-900">{evt.title}</p>
                            <p className="text-xs text-slate-500">{new Date(evt.occurred_at).toLocaleDateString()} • {evt.actor}</p>
                        </div>
                    </div>
                ))}
            </div>
        </div>
    );
};

const UnknownWidget: React.FC<{ widget: any }> = ({ widget }) => {
    console.error(`[UniversalDashboard] Unknown widget type: ${widget.type}`, widget);
    return (
        <div className="bg-gray-50 border border-dashed border-gray-300 rounded-xl p-4 text-xs font-mono text-gray-500 h-full overflow-hidden">
            <p className="font-bold text-red-500 mb-1">UNKNOWN WIDGET: {widget.type}</p>
            <pre>{JSON.stringify(widget.data, null, 2)}</pre>
        </div>
    );
};

// --- REGISTRY ---
const registry: Record<string, React.FC<any>> = {
    'VALUATION_SUMMARY': ValuationSummaryWidget,
    'CUSTODY_STATUS': CustodyStatusWidget,
    'PROVENANCE_TIMELINE': ProvenanceTimelineWidget
};

// --- DASHBOARD RENDERER ---
export const UniversalDashboard: React.FC<{ widgets: Widget[] }> = ({ widgets }) => {
    if (!widgets || widgets.length === 0) return null;

    // Stable sort by priority desc
    const sorted = [...widgets].sort((a, b) => b.priority_int - a.priority_int);

    return (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4 mb-6">
            {sorted.map((w, idx) => {
                const Component = registry[w.type] || UnknownWidget;
                return (
                    <div key={`${w.type}-${idx}`} className="min-h-[200px]">
                        <Component widget={w} />
                    </div>
                );
            })}
        </div>
    );
};
