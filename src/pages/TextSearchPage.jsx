import { useState } from 'react'
import { useNavigate } from 'react-router-dom'

export default function TextSearchPage() {
  const navigate = useNavigate()
  const [query, setQuery] = useState('black shirt')

  return (
    <div className="search-page">
      <section className="search-intro">
        <p className="eyebrow">FASHION TEXT SEARCH</p>
        <h1>DESCRIBE YOUR STYLE</h1>
      </section>

      <section className="text-search-card">
        <label htmlFor="query">FASHION QUERY</label>
        <div className="query-input-wrap">
          <span>⌕</span>
          <input id="query" value={query} onChange={(e) => setQuery(e.target.value)} placeholder="e.g. black shirt, white dress, leather bag..." />
        </div>

        <div className="static-filter-grid">
          <label>Gender<select defaultValue="Men"><option>Men</option><option>Women</option><option>Unisex</option></select></label>
          <label>Category<select defaultValue="Shirts"><option>Shirts</option><option>Jeans</option><option>Sneakers</option></select></label>
          <label>Color<select defaultValue="Black"><option>Black</option><option>White</option><option>Blue</option></select></label>
        </div>

        <div className="form-actions">
          <button className="secondary-btn" onClick={() => setQuery('')}>CLEAR</button>
          <button className="primary-btn" onClick={() => navigate('/results', { state: { query } })}>DISCOVER</button>
        </div>
      </section>
    </div>
  )
}
