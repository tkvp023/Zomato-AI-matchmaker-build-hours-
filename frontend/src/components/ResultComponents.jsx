import { MapPin, Star, AlertTriangle, Bot } from 'lucide-react';

export function Hero() {
  return (
    <div className="hero">
      <h1>
        <span className="text-gradient">Zomato AI</span> Recommender
      </h1>
      <p className="subtitle">
        Discover your next favourite restaurant, powered by AI.
      </p>
      
      <div className="hero-stats">
        <div className="hero-stat-card">
          <span className="stat-number">8,200+</span>
          <span className="stat-label">Restaurants</span>
        </div>
        <div className="hero-stat-card">
          <span className="stat-number">120+</span>
          <span className="stat-label">Cuisines</span>
        </div>
        <div className="hero-stat-card">
          <span className="stat-number">45</span>
          <span className="stat-label">Locations</span>
        </div>
      </div>
    </div>
  );
}

export function ResultsBanner({ summary, usedFallback, totalCandidates }) {
  return (
    <div className={`glass-panel results-banner ${usedFallback ? 'fallback' : ''}`}>
      <div className="results-banner-content">
        <div className="results-banner-icon">
          {usedFallback ? (
            <AlertTriangle size={20} color="var(--budget-medium)" />
          ) : (
            <Bot size={20} color="var(--accent-primary)" />
          )}
        </div>
        <div>
          <div className="results-banner-text">
            {usedFallback && (
              <span style={{ fontWeight: 700, color: 'var(--budget-medium)', marginRight: 8 }}>
                AI ranking unavailable —
              </span>
            )}
            {summary}
          </div>
          <div className="results-banner-meta">
            <span>Considered {totalCandidates} candidates</span>
            <span className="dot">•</span>
            <span>Filtered from 8,200 restaurants</span>
            <span className="dot">•</span>
            <span>Powered by Llama 3.3</span>
          </div>
        </div>
      </div>
    </div>
  );
}

function StarRating({ rating }) {
  const fullStars = Math.floor(rating);
  const hasHalf = rating % 1 >= 0.3;
  const total = fullStars + (hasHalf ? 1 : 0);
  const empty = 5 - total;

  return (
    <div className="star-rating">
      {[...Array(fullStars)].map((_, i) => (
        <Star key={`f${i}`} size={16} fill="currentColor" strokeWidth={0} />
      ))}
      {hasHalf && (
        <div style={{ position: 'relative', width: 16, height: 16 }}>
          <Star size={16} style={{ position: 'absolute', left: 0, top: 0, opacity: 0.3 }} />
          <div style={{ position: 'absolute', left: 0, top: 0, overflow: 'hidden', width: '50%' }}>
            <Star size={16} fill="currentColor" strokeWidth={0} />
          </div>
        </div>
      )}
      {[...Array(Math.max(0, empty))].map((_, i) => (
        <Star key={`e${i}`} size={16} style={{ opacity: 0.25 }} />
      ))}
      <span style={{ marginLeft: 6, fontSize: '0.8rem', fontWeight: 600, opacity: 0.7 }}>
        {rating.toFixed(1)}
      </span>
    </div>
  );
}

export function RecommendationCard({ recommendation, usedFallback }) {
  const {
    rank,
    restaurant_name,
    rating,
    estimated_cost,
    cost_display,
    location,
    cuisine,
    explanation
  } = recommendation;

  const cuisinesList = cuisine ? cuisine.split(',').map(c => c.trim()).filter(Boolean) : [];

  let rankClass = 'default';
  if (rank === 1) rankClass = 'gold';
  else if (rank === 2) rankClass = 'silver';
  else if (rank === 3) rankClass = 'bronze';

  return (
    <div className="glass-panel rec-card">
      
      {/* Header: rank + AI badge | stars */}
      <div className="rec-card-header">
        <div className="rec-card-badges">
          <span className={`rank-badge ${rankClass}`}>
            Rank {rank}
          </span>
          <span className="ai-badge">
            {usedFallback ? (
              <><span style={{ color: 'var(--budget-medium)' }}>📊</span> Ranked by data</>
            ) : (
              <><span className="text-gradient">🤖</span> AI Ranked</>
            )}
          </span>
        </div>
        <StarRating rating={rating} />
      </div>

      {/* Name */}
      <h3 className="rec-card-name">{restaurant_name}</h3>

      {/* Cuisine pills */}
      {cuisinesList.length > 0 && (
        <div className="rec-card-cuisines">
          {cuisinesList.map(c => (
            <span key={c} className="cuisine-pill">{c}</span>
          ))}
        </div>
      )}

      {/* Location + Cost */}
      <div className="rec-card-meta">
        <div className="meta-item">
          <MapPin size={15} /> {location}
        </div>
        <div className="cost-badge">
          💳 {cost_display || `₹${estimated_cost} for two`}
        </div>
      </div>

      {/* AI Explanation */}
      {explanation && (
        <div className="explanation-block">
          "{explanation}"
        </div>
      )}
    </div>
  );
}
