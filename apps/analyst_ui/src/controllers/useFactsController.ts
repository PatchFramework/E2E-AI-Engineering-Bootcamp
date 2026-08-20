import { useState, useEffect, useCallback } from 'react';
import { FinancialFact, FactCorrectionPayload, FactCorrectionResult } from '../models/fact';
import { apiClient } from './apiClient';

export interface CorrectionFeedbackState {
  factConcept: string;
  originalValue?: number;
  newValue: number;
  unit: string;
  affectedMetrics: string[];
}

export function useFactsController(companyId: number | null, onFactsUpdated?: () => void) {
  const [facts, setFacts] = useState<FinancialFact[]>([]);
  const [loading, setLoading] = useState<boolean>(false);
  const [selectedFactForCorrection, setSelectedFactForCorrection] = useState<FinancialFact | null>(null);
  const [correctionFeedback, setCorrectionFeedback] = useState<CorrectionFeedbackState | null>(null);
  const [isSubmitting, setIsSubmitting] = useState<boolean>(false);

  // Fetch facts for active company
  const fetchFacts = useCallback(async () => {
    if (!companyId) {
      setFacts([]);
      return;
    }

    try {
      setLoading(true);
      const data = await apiClient.get<FinancialFact[]>(`/api/facts/${companyId}`);
      setFacts(data);
    } catch {
      setFacts([]);
    } finally {
      setLoading(false);
    }
  }, [companyId]);

  useEffect(() => {
    fetchFacts();
  }, [fetchFacts]);

  // Verify Fact
  const verifyFact = useCallback(
    async (factId: number) => {
      try {
        setIsSubmitting(true);
        const updated = await apiClient.post<FinancialFact>(`/api/facts/${factId}/verify`);
        setFacts(prev => prev.map(f => (f.id === factId ? updated : f)));
        if (onFactsUpdated) onFactsUpdated();
        return updated;
      } catch (err: any) {
        throw new Error(err.message || 'Failed to verify fact');
      } finally {
        setIsSubmitting(false);
      }
    },
    [onFactsUpdated]
  );

  // Correct Fact with analyst override & change reason
  const correctFact = useCallback(
    async (factId: number, value: number, reason: string) => {
      try {
        setIsSubmitting(true);
        const oldFact = facts.find(f => f.id === factId);
        const payload: FactCorrectionPayload = {
          value,
          change_reason: reason,
        };
        const res = await apiClient.post<FactCorrectionResult>(`/api/facts/${factId}/correct`, payload);

        setFacts(prev => prev.map(f => (f.id === factId ? res.fact : f)));

        setCorrectionFeedback({
          factConcept: res.fact.concept,
          originalValue: oldFact?.value,
          newValue: res.fact.value,
          unit: res.fact.unit,
          affectedMetrics: res.affected_metrics || [],
        });

        if (onFactsUpdated) onFactsUpdated();
        return res;
      } catch (err: any) {
        throw new Error(err.message || 'Failed to correct fact');
      } finally {
        setIsSubmitting(false);
      }
    },
    [facts, onFactsUpdated]
  );


  const clearFeedback = useCallback(() => {
    setCorrectionFeedback(null);
  }, []);

  return {
    facts,
    loading,
    selectedFactForCorrection,
    setSelectedFactForCorrection,
    correctionFeedback,
    clearFeedback,
    verifyFact,
    correctFact,
    isSubmitting,
    refreshFacts: fetchFacts,
  };
}
