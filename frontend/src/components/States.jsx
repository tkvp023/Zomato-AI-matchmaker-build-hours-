import { Search, Wrench, RefreshCw } from 'lucide-react';

export function LoadingState() {
  const messages = ["Analysing your preferences...", "Consulting the AI chef...", "Ranking the best picks..."];
  const randomMessage = messages[Math.floor(Math.random() * messages.length)];

  return (
    <div className="loading-wrapper">
      <div className="loading-dots">
        <div className="pulse-dot"></div>
        <div className="pulse-dot"></div>
        <div className="pulse-dot"></div>
      </div>
      <h3 className="loading-title">Curating Your Evening</h3>
      <p className="loading-subtitle">{randomMessage}</p>
    </div>
  );
}

export function EmptyState({ onRetry }) {
  return (
    <div className="glass-panel empty-state">
      <div className="empty-icon">🔍</div>
      <h2>No restaurants found</h2>
      <p>No restaurants match your exact preferences. Try adjusting your filters.</p>
      
      <div className="suggestion-pills">
        <button className="suggestion-pill">↓ Try lowering rating</button>
        <button className="suggestion-pill">📍 Try a different area</button>
        <button className="suggestion-pill">✕ Remove cuisine filter</button>
      </div>

      <button onClick={onRetry} className="new-search-link">
        <Search size={14} /> Start a new search
      </button>
    </div>
  );
}

export function ErrorState({ message, onRetry }) {
  return (
    <div className="glass-panel error-state">
      <div className="error-icon-circle">
        <Wrench size={32} color="#FFC107" />
      </div>
      <h2>Something went wrong</h2>
      <p>{message || "We couldn't reach our recommendation engine. This might be a temporary issue."}</p>
      
      <button onClick={onRetry} className="btn-primary">
        <RefreshCw size={16} /> Try Again
      </button>
      
      <span className="text-muted-sm">If this persists, check your internet connection</span>
    </div>
  );
}
