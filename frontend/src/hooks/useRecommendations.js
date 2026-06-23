import { useState, useEffect } from 'react';
import { apiClient } from '../api/client';

export function useRecommendations() {
  const [metadata, setMetadata] = useState(null);
  const [recommendations, setRecommendations] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [metadataLoading, setMetadataLoading] = useState(true);
  const [metadataError, setMetadataError] = useState(null);

  // Load metadata on mount
  useEffect(() => {
    async function fetchMetadata() {
      try {
        const data = await apiClient.getMetadata();
        setMetadata(data);
      } catch (err) {
        console.error("Failed to load metadata", err);
        setMetadataError('Could not connect to the backend API. Please check that the server is running.');
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
    metadataError,
    recommendations,
    loading,
    error,
    fetchRecommendations,
    clearRecommendations
  };
}
