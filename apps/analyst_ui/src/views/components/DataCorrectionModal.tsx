import React, { useState } from 'react';
import {
  X,
  AlertTriangle,
  CheckCircle,
  Save,
  Loader2,
  CheckCheck,
} from 'lucide-react';

import { FinancialFact } from '../../models/fact';
import { formatMetricValue, parseAnalystInput } from '../../models/metric';
import { CorrectionFeedbackState } from '../../controllers/useFactsController';

interface DataCorrectionModalProps {
  fact: FinancialFact | null;
  feedback: CorrectionFeedbackState | null;
  isSubmitting: boolean;
  onClose: () => void;
  onClearFeedback: () => void;
  onVerify: (factId: number) => Promise<any>;
  onCorrect: (factId: number, value: number, reason: string) => Promise<any>;
}

export const DataCorrectionModal: React.FC<DataCorrectionModalProps> = ({
  fact,
  feedback,
  isSubmitting,
  onClose,
  onClearFeedback,
  onVerify,
  onCorrect,
}) => {
  const [overrideValue, setOverrideValue] = useState<string>('');
  const [reason, setReason] = useState<string>('');
  const [error, setError] = useState<string | null>(null);

  // Sync state whenever the selected fact changes
  React.useEffect(() => {
    if (fact) {
      setOverrideValue(fact.value !== undefined && fact.value !== null ? fact.value.toString() : '');
      setReason('');
      setError(null);
    }
  }, [fact]);

  if (!fact && !feedback) return null;

  const handleSubmitCorrection = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!fact) return;

    const numValue = parseAnalystInput(overrideValue);
    if (numValue === null || isNaN(numValue)) {
      setError('Please enter a valid numerical value (e.g. 1.5M, 1,500,000 or 1.5).');
      return;
    }
    if (!reason.trim()) {
      setError('A justification reason is required for compliance audit trails.');
      return;
    }

    try {
      setError(null);
      await onCorrect(fact.id, numValue, reason.trim());
    } catch (err: any) {
      setError(err.message || 'Correction failed.');
    }
  };

  const handleVerifyDirectly = async () => {
    if (!fact) return;
    try {
      setError(null);
      await onVerify(fact.id);
      onClose();
    } catch (err: any) {
      setError(err.message || 'Verification failed.');
    }
  };


  return (
    <div className="fixed inset-0 z-50 overflow-y-auto bg-slate-950/80 backdrop-blur-sm flex items-center justify-center p-4">
      <div className="bg-slate-900 border border-slate-800 rounded-2xl w-full max-w-xl shadow-2xl overflow-hidden animate-in fade-in zoom-in-95 duration-200">
        {/* Modal Header */}
        <div className="p-6 border-b border-slate-800 flex justify-between items-start">
          <div className="flex items-center gap-3">
            <div className="p-2.5 rounded-xl bg-indigo-950/60 text-indigo-400 border border-indigo-900/50">
              <AlertTriangle className="w-5 h-5" />
            </div>
            <div>
              <h3 className="text-lg font-bold text-white tracking-tight">
                {feedback ? 'Fact Correction Completed' : `Data Correction UX · ${fact?.concept}`}
              </h3>
              <p className="text-xs text-slate-400 mt-0.5">
                Real-time financial fact modification and synchronous KPI recalculation
              </p>
            </div>
          </div>
          <button
            onClick={() => {
              onClearFeedback();
              onClose();
            }}
            className="text-slate-400 hover:text-white p-1.5 rounded-lg bg-slate-800/40 hover:bg-slate-800 transition"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        {/* Modal Content */}
        <div className="p-6">
          {/* Post-Save Feedback State (PRD lines 118-129) */}
          {feedback ? (
            <div className="space-y-6">
              <div className="bg-emerald-950/30 border border-emerald-900/60 rounded-xl p-5">
                <div className="flex items-center gap-2 text-emerald-400 font-bold text-sm">
                  <CheckCheck className="w-5 h-5" />
                  {feedback.factConcept} updated successfully
                </div>
                <p className="text-xs text-slate-300 mt-2">
                  New verified value:{' '}
                  <span className="font-extrabold text-white">
                    {formatMetricValue(feedback.newValue, feedback.unit)}
                  </span>
                </p>
              </div>

              {/* Affected Metrics Recalculated List */}
              <div>
                <h4 className="text-xs font-bold text-slate-300 uppercase tracking-wider mb-3">
                  Affected Synchronously Recalculated Metrics:
                </h4>
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
                  {feedback.affectedMetrics.map((metricName, idx) => (
                    <div
                      key={idx}
                      className="flex items-center gap-2 text-xs font-medium text-slate-200 bg-slate-950/60 border border-slate-800/80 p-2.5 rounded-lg"
                    >
                      <CheckCircle className="w-4 h-4 text-emerald-400 flex-shrink-0" />
                      <span>{metricName}</span>
                    </div>
                  ))}
                </div>
              </div>

              <div className="pt-4 border-t border-slate-800 flex justify-end">
                <button
                  onClick={() => {
                    onClearFeedback();
                    onClose();
                  }}
                  className="bg-brand-600 hover:bg-brand-500 text-white font-semibold text-xs px-5 py-2.5 rounded-xl transition"
                >
                  Done
                </button>
              </div>
            </div>
          ) : fact ? (
            <form onSubmit={handleSubmitCorrection} className="space-y-6">
              {/* Fact Context */}
              <div className="bg-slate-950/60 border border-slate-800 rounded-xl p-4 flex justify-between items-center">
                <div>
                  <div className="text-[11px] text-slate-400 uppercase tracking-wider font-semibold">
                    Current Extracted Fact
                  </div>
                  <div className="text-2xl font-black text-white mt-1">
                    {formatMetricValue(fact.value, fact.unit)}
                  </div>
                  <div className="text-[11px] text-slate-400 mt-1">
                    Fiscal Year {fact.fiscal_year} ({fact.fiscal_period})
                  </div>
                </div>

                <div className="text-right">
                  <span
                    className={`text-[10px] px-2.5 py-1 rounded-full font-bold uppercase tracking-wider ${
                      fact.verification_status === 'VERIFIED'
                        ? 'bg-emerald-950/60 text-emerald-400 border border-emerald-900/50'
                        : 'bg-amber-950/60 text-amber-400 border border-amber-900/50'
                    }`}
                  >
                    {fact.verification_status === 'VERIFIED'
                      ? '✓ Verified'
                      : 'Unverified AI-Generated'}
                  </span>
                </div>
              </div>

              {/* Form Inputs for Analyst Override */}
              <div className="space-y-4">
                <div>
                  <label className="block text-xs font-semibold text-slate-300 mb-1.5">
                    New Override Value ({fact.unit})
                  </label>
                  <input
                    type="number"
                    step="any"
                    value={overrideValue}
                    onChange={e => setOverrideValue(e.target.value)}
                    placeholder={`e.g. 184000000`}
                    className="w-full bg-slate-950 border border-slate-800 focus:border-brand-500 rounded-xl px-4 py-2.5 text-sm text-white focus:outline-none transition"
                    required
                  />
                </div>

                <div>
                  <label className="block text-xs font-semibold text-slate-300 mb-1.5">
                    Reason for Override (Compliance Audit Trail)
                  </label>
                  <textarea
                    rows={2}
                    value={reason}
                    onChange={e => setReason(e.target.value)}
                    placeholder="e.g. Management adjusted EBITDA figure should be used."
                    className="w-full bg-slate-950 border border-slate-800 focus:border-brand-500 rounded-xl px-4 py-2.5 text-xs text-white focus:outline-none transition resize-none"
                    required
                  />
                </div>
              </div>

              {error && <p className="text-xs text-rose-400">{error}</p>}

              {/* Action Buttons */}
              <div className="flex items-center justify-between gap-3 pt-4 border-t border-slate-800">
                {fact.verification_status !== 'VERIFIED' && (
                  <button
                    type="button"
                    onClick={handleVerifyDirectly}
                    disabled={isSubmitting}
                    className="bg-emerald-950/50 hover:bg-emerald-900/60 text-emerald-400 border border-emerald-800/60 font-semibold text-xs px-4 py-2.5 rounded-xl transition flex items-center gap-1.5"
                  >
                    <CheckCircle className="w-4 h-4" /> Verify As Is
                  </button>
                )}

                <div className="flex items-center gap-2 ml-auto">
                  <button
                    type="button"
                    onClick={onClose}
                    className="text-xs font-semibold text-slate-400 hover:text-slate-200 px-4 py-2.5 rounded-xl transition"
                  >
                    Cancel
                  </button>
                  <button
                    type="submit"
                    disabled={isSubmitting}
                    className="bg-brand-600 hover:bg-brand-500 text-white font-semibold text-xs px-5 py-2.5 rounded-xl transition flex items-center gap-1.5 shadow-lg shadow-brand-600/30"
                  >
                    {isSubmitting ? (
                      <Loader2 className="w-4 h-4 animate-spin" />
                    ) : (
                      <Save className="w-4 h-4" />
                    )}
                    Save Correction
                  </button>
                </div>
              </div>
            </form>
          ) : null}
        </div>
      </div>
    </div>
  );
};
