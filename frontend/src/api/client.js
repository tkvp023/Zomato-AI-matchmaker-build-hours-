const API_BASE_URL = 'http://localhost:8000/api/v1';

export const apiClient = {
  async getMetadata() {
    try {
      const response = await fetch(`${API_BASE_URL}/metadata`);
      if (!response.ok) throw new Error('Failed to fetch metadata');
      return await response.json();
    } catch (error) {
      console.error('API Error:', error);
      throw error;
    }
  },

  async getRecommendations(preferences) {
    try {
      const response = await fetch(`${API_BASE_URL}/recommendations`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(preferences),
      });
      
      const data = await response.json();
      
      if (!response.ok) {
        // Validation errors return 400 with detail.message
        const message = data?.detail?.message || data?.detail || 'Failed to fetch recommendations';
        throw new Error(message);
      }
      
      return data;
    } catch (error) {
      console.error('API Error:', error);
      throw error;
    }
  }
};
