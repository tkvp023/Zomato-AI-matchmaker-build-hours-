import { useRecommendations } from './hooks/useRecommendations';
import { PreferenceForm } from './components/PreferenceForm';
import { Hero, ResultsBanner, RecommendationCard } from './components/ResultComponents';
import { LoadingState, EmptyState, ErrorState } from './components/States';

function Navbar() {
  return (
    <nav className="navbar">
      <div className="navbar-logo">
        <span className="text-gradient">Zomato AI</span>
        <span className="navbar-tagline">Matchmaker</span>
      </div>
    </nav>
  );
}

function App() {
  const { 
    metadata, 
    metadataLoading, 
    metadataError,
    recommendations, 
    loading, 
    error, 
    fetchRecommendations, 
    clearRecommendations 
  } = useRecommendations();

  const handleSearch = (preferences) => {
    fetchRecommendations(preferences);
  };

  const handleRetry = () => {
    clearRecommendations();
  };

  return (
    <div>
      <Navbar />

      <main className="main-container">
        
        {/* Initial State: Hero + Form */}
        {!loading && !recommendations && !error && (
          <>
            <Hero />
            {metadataLoading ? (
              <div className="loading-wrapper" style={{ padding: '48px 0' }}>
                <div className="loading-dots">
                  <div className="pulse-dot"></div>
                </div>
              </div>
            ) : metadataError ? (
              <div className="glass-panel" style={{ textAlign: 'center', padding: '40px 24px', maxWidth: 560, margin: '0 auto' }}>
                <div style={{ fontSize: '2.5rem', marginBottom: 16 }}>⚠️</div>
                <h3 style={{ color: 'var(--text-primary)', marginBottom: 8 }}>Backend Unavailable</h3>
                <p style={{ color: 'var(--text-secondary)', fontSize: '0.95rem', lineHeight: 1.6 }}>
                  {metadataError}
                </p>
                <button 
                  className="btn-glass" 
                  style={{ marginTop: 20 }} 
                  onClick={() => window.location.reload()}
                >
                  ↻ Retry Connection
                </button>
              </div>
            ) : (
              <PreferenceForm 
                metadata={metadata} 
                onSubmit={handleSearch} 
                disabled={loading} 
              />
            )}
          </>
        )}

        {/* Loading State */}
        {loading && (
          <>
            <div className="form-disabled">
              <PreferenceForm metadata={metadata} onSubmit={() => {}} disabled={true} />
            </div>
            <LoadingState />
          </>
        )}

        {/* Error State */}
        {error && !loading && (
          <ErrorState message={error} onRetry={handleRetry} />
        )}

        {/* Results */}
        {recommendations && !loading && !error && (
          <div>
            {recommendations.recommendations.length > 0 ? (
              <>
                <ResultsBanner 
                  summary={recommendations.summary}
                  usedFallback={recommendations.used_fallback}
                  totalCandidates={recommendations.total_candidates_considered}
                />
                
                <div className="card-list">
                  {recommendations.recommendations.map(rec => (
                    <RecommendationCard 
                      key={rec.restaurant_name} 
                      recommendation={rec} 
                      usedFallback={recommendations.used_fallback}
                    />
                  ))}
                </div>

                <div className="new-search-footer">
                  <button onClick={handleRetry} className="btn-glass" style={{ margin: '0 auto' }}>
                    ↻ Start a New Search
                  </button>
                </div>
              </>
            ) : (
              <EmptyState onRetry={handleRetry} />
            )}
          </div>
        )}

      </main>
    </div>
  );
}

export default App;
