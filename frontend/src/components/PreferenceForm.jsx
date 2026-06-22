import { useState, useEffect } from 'react';
import { MapPin, Utensils, Sparkles } from 'lucide-react';

const BUDGET_TIERS = [
  { key: 'low',    label: 'Low',    range: '< ₹500' },
  { key: 'medium', label: 'Medium', range: '₹500 – ₹1500' },
  { key: 'high',   label: 'High',   range: '> ₹1500' },
];

export function PreferenceForm({ metadata, onSubmit, disabled }) {
  const [formData, setFormData] = useState({
    location: '',
    cuisine: '',
    budget: 'medium',
    min_rating: 3.5,
    additional_preferences: ''
  });

  useEffect(() => {
    if (metadata && !formData.location) {
      setFormData(prev => ({
        ...prev,
        location: metadata.locations[0] || 'Indiranagar'
      }));
    }
  }, [metadata]);

  const handleChange = (e) => {
    const { name, value } = e.target;
    setFormData(prev => ({
      ...prev,
      [name]: name === 'min_rating' ? parseFloat(value) : value
    }));
  };

  const handleBudgetSlider = (e) => {
    const val = parseInt(e.target.value, 10);
    setFormData(prev => ({ ...prev, budget: BUDGET_TIERS[val].key }));
  };

  const handleSubmit = (e) => {
    e.preventDefault();
    onSubmit({
      ...formData,
      cuisine: formData.cuisine === '' ? '' : formData.cuisine
    });
  };

  if (!metadata) return null;

  const budgetIndex = BUDGET_TIERS.findIndex(t => t.key === formData.budget);

  return (
    <form onSubmit={handleSubmit} className="glass-panel pref-form">
      
      {/* Location + Cuisine Row */}
      <div className="form-row">
        <div className="form-group">
          <label className="form-label">LOCATION</label>
          <div className="input-wrapper">
            <span className="input-icon"><MapPin size={16} /></span>
            <select 
              name="location" 
              value={formData.location} 
              onChange={handleChange}
              className="form-select"
              required
            >
              {metadata.locations.map(loc => (
                <option key={loc} value={loc}>{loc}</option>
              ))}
            </select>
          </div>
        </div>

        <div className="form-group">
          <label className="form-label">CUISINE</label>
          <div className="input-wrapper">
            <span className="input-icon"><Utensils size={16} /></span>
            <select 
              name="cuisine" 
              value={formData.cuisine} 
              onChange={handleChange}
              className="form-select"
            >
              <option value="">Any Cuisine</option>
              {metadata.cuisines.map(c => (
                <option key={c} value={c}>{c}</option>
              ))}
            </select>
          </div>
        </div>
      </div>

      {/* Budget — real range slider that snaps to 3 positions */}
      <div className="budget-section">
        <label className="form-label">BUDGET</label>
        <div className="budget-slider-wrapper">
          <input
            type="range"
            className="budget-range-input"
            min="0"
            max="2"
            step="1"
            value={budgetIndex}
            onChange={handleBudgetSlider}
          />
          <div className="budget-labels">
            {BUDGET_TIERS.map((tier, i) => (
              <div
                key={tier.key}
                className={`budget-label-item ${budgetIndex === i ? 'active' : ''}`}
                onClick={() => setFormData(prev => ({ ...prev, budget: tier.key }))}
              >
                <span className="budget-label-name">{tier.label}</span>
                <span className="budget-label-range">{tier.range}</span>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* Min Rating */}
      <div className="rating-section">
        <div className="rating-header">
          <label className="form-label">
            <span style={{ color: 'var(--star-color)', marginRight: 6 }}>★</span>
            MINIMUM RATING
          </label>
          <span className="rating-value">{formData.min_rating.toFixed(1)}</span>
        </div>
        <input 
          type="range" 
          name="min_rating" 
          min="1.0" 
          max="5.0" 
          step="0.1" 
          value={formData.min_rating} 
          onChange={handleChange}
        />
        <div className="rating-labels">
          <span>1.0</span>
          <span>5.0</span>
        </div>
      </div>

      {/* Additional Preferences */}
      <div className="form-textarea-section">
        <label className="form-label">ADDITIONAL PREFERENCES</label>
        <textarea 
          name="additional_preferences" 
          value={formData.additional_preferences} 
          onChange={handleChange}
          placeholder="e.g., 'Quiet place for a date', 'Good vegan options', 'Rooftop seating'"
          className="form-textarea"
          style={{ marginTop: 8 }}
        ></textarea>
      </div>

      {/* Submit */}
      <button type="submit" disabled={disabled} className="submit-btn">
        <Sparkles size={20} /> Get Recommendations
      </button>
    </form>
  );
}
