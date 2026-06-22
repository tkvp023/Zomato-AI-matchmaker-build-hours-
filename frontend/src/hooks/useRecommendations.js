import { useState, useEffect } from 'react';
import { apiClient } from '../api/client';

export function useRecommendations() {
  const [metadata, setMetadata] = useState(null);
  const [recommendations, setRecommendations] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [metadataLoading, setMetadataLoading] = useState(true);

  // Load metadata on mount
  useEffect(() => {
    async function fetchMetadata() {
      try {
        const data = await apiClient.getMetadata();
        setMetadata(data);
      } catch (err) {
        console.error("Failed to load metadata", err);
      } finally {
        setMetadataLoading(false);
      }
    }
    fetchMetadata();
  }, []);

  const fetchRecommendations = async (preferences) => {
    setLoading(true);
    setError(null);
    setRecommendations(null);
    
    try {
      const data = await apiClient.getRecommendations(preferences);
      setRecommendations(data);
    } catch (err) {
      setError(err.message || 'Failed to fetch recommendations');
    } finally {
      setLoading(false);
    }
  };

  const clearRecommendations = () => {
    setRecommendations(null);
    setError(null);
  };

  return {
    metadata,
    metadataLoading,
    recommendations,
    loading,
    error,
    fetchRecommendations,
    clearRecommendations
  };
}
