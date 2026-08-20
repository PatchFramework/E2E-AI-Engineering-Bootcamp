import { useState, useEffect, useCallback } from 'react';
import { Company, DataQualityIssue, CompanySummary, calculateCompanyRating } from '../models/company';
import { MetricItem } from '../models/metric';
import { FinancialFact } from '../models/fact';
import { apiClient } from './apiClient';

export function useCompanyController(metrics: MetricItem[], facts: FinancialFact[]) {
  const [companies, setCompanies] = useState<Company[]>([]);
  const [selectedCompanyId, setSelectedCompanyId] = useState<number | null>(null);
  const [qualityIssues, setQualityIssues] = useState<DataQualityIssue[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  // Fetch companies list on mount
  const fetchCompanies = useCallback(async () => {
    try {
      setLoading(true);
      const data = await apiClient.get<Company[]>('/api/companies');
      setCompanies(data);
      if (data.length > 0 && selectedCompanyId === null) {
        setSelectedCompanyId(data[0].id);
      }
      setError(null);
    } catch (err: any) {
      setError(err.message || 'Failed to fetch companies');
    } finally {
      setLoading(false);
    }
  }, [selectedCompanyId]);

  useEffect(() => {
    fetchCompanies();
  }, [fetchCompanies]);

  // Fetch company quality issues whenever selected company changes
  const fetchQualityIssues = useCallback(async (companyId: number) => {
    try {
      const data = await apiClient.get<DataQualityIssue[]>(`/api/companies/${companyId}/quality-issues`);
      setQualityIssues(data);
    } catch {
      setQualityIssues([]);
    }
  }, []);

  useEffect(() => {
    if (selectedCompanyId) {
      fetchQualityIssues(selectedCompanyId);
    }
  }, [selectedCompanyId, fetchQualityIssues]);

  const activeCompany = companies.find(c => c.id === selectedCompanyId) || null;

  // Build real-time company summary using facts, metrics, and quality issues
  const companySummary: CompanySummary = (() => {
    const defaultName = activeCompany?.name || 'Acme Corporation';
    const ticker = activeCompany?.ticker || undefined;

    const ratingInfo = calculateCompanyRating(metrics);

    // Compute verified facts count & quality percentage
    const totalFacts = facts.length;
    const verifiedFacts = facts.filter(f => f.verification_status === 'VERIFIED').length;
    const dataQualityPct = totalFacts > 0 ? Math.round((verifiedFacts / totalFacts) * 100) : 87;

    // Detect latest fiscal filing period
    const latestYear = facts.reduce((max, f) => Math.max(max, f.fiscal_year || 0), 2025);

    return {
      name: defaultName,
      ticker,
      rating: ratingInfo.rating,
      risk: ratingInfo.risk,
      riskLevel: ratingInfo.riskLevel,
      latestFiling: `FY${latestYear} Annual Report`,
      dataQualityPct,
      verifiedCount: verifiedFacts,
      totalFactsCount: totalFacts,
      issuesCount: qualityIssues.length,
    };
  })();

  return {
    companies,
    selectedCompanyId,
    setSelectedCompanyId,
    activeCompany,
    companySummary,
    qualityIssues,
    loading,
    error,
    refreshCompanies: fetchCompanies,
  };
}
