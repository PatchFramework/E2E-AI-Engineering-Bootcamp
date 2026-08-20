import { useState, useEffect, useCallback } from 'react';
import { MetricItem, KPICategory, MetricLineage } from '../models/metric';
import { apiClient } from './apiClient';

export function useMetricsController(companyId: number | null) {
  const [metrics, setMetrics] = useState<MetricItem[]>([]);
  const [activeTab, setActiveTab] = useState<KPICategory>('Overview');
  const [selectedMetric, setSelectedMetric] = useState<MetricItem | null>(null);
  const [lineage, setLineage] = useState<MetricLineage | null>(null);
  const [loading, setLoading] = useState<boolean>(false);
  const [lineageLoading, setLineageLoading] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);

  // Fetch metric lineage when a metric is selected
  const fetchLineage = useCallback(async (metricId: number) => {
    try {
      setLineageLoading(true);
      const data = await apiClient.get<MetricLineage>(`/api/metrics/${metricId}/lineage`);
      setLineage(data);
    } catch {
      setLineage(null);
    } finally {
      setLineageLoading(false);
    }
  }, []);

  // Fetch metrics for active company
  const fetchMetrics = useCallback(async () => {
    if (!companyId) {
      setMetrics([]);
      return;
    }

    try {
      setLoading(true);
      const data = await apiClient.get<MetricItem[]>(`/api/companies/${companyId}/metrics`);
      setMetrics(data);
      setError(null);

      // If a metric is currently selected, refresh its object and its lineage
      setSelectedMetric(currentSelected => {
        if (!currentSelected) return null;
        const updated = data.find(m => m.metric_name === currentSelected.metric_name) || currentSelected;
        if (updated && updated.id) {
          fetchLineage(updated.id);
        }
        return updated;
      });
    } catch (err: any) {
      setError(err.message || 'Failed to load company metrics');
    } finally {
      setLoading(false);
    }
  }, [companyId, fetchLineage]);

  useEffect(() => {
    fetchMetrics();
  }, [fetchMetrics]);

  const handleSelectMetric = useCallback(

    (metric: MetricItem | null) => {
      setSelectedMetric(metric);
      if (metric && metric.id) {
        fetchLineage(metric.id);
      } else {
        setLineage(null);
      }
    },
    [fetchLineage]
  );

  // Filtered metrics by category tab
  const filteredMetrics = metrics.filter(m => activeTab === 'Overview' || m.category === activeTab);

  return {
    metrics,
    filteredMetrics,
    activeTab,
    setActiveTab,
    selectedMetric,
    setSelectedMetric: handleSelectMetric,
    lineage,
    loading,
    lineageLoading,
    error,
    refreshMetrics: fetchMetrics,
  };
}
