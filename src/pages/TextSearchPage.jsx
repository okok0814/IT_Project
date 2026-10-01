import { useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  categoryOptions,
  colorOptions,
  genderOptions,
} from '../data/filterOptions'
import { textSearchDemoCatalog } from '../data/textSearchDemoCatalog'

function normalize(value) {
  return String(value ?? '').trim().toLowerCase()
}

function tokenize(query) {
  return normalize(query)
    .split(/\s+/)
    .map((token) => token.trim())
    .filter(Boolean)
}

function scoreProduct(product, tokens) {
  if (tokens.length === 0) {
    return 1
  }

  const fields = [
    product.gender,
    product.category,
    product.color,
    product.usage,
    product.master_category,
    product.sub_category,
  ]

  const searchable = normalize(fields.join(' '))
  const matched = tokens.filter((token) => searchable.includes(token)).length

  return matched / tokens.length
}

function searchTextDemo({ query, gender, category, color, topK = 12 }) {
  const tokens = tokenize(query)

  return textSearchDemoCatalog
    .filter((product) => !gender || product.gender === gender)
    .filter((product) => !category || product.category === category)
    .filter((product) => !color || product.color === color)
    .map((product) => ({
      ...product,
      text_match_score: scoreProduct(product, tokens),
    }))
    .filter((product) => tokens.length === 0 || product.text_match_score > 0)
    .sort((a, b) => b.text_match_score - a.text_match_score)
    .slice(0, topK)
}

export default function TextSearchPage() {
  const navigate = useNavigate()

  const [query, setQuery] = useState('')
  const [gender, setGender] = useState('')
  const [category, setCategory] = useState('')
  const [color, setColor] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  const hasSearchInput = useMemo(
    () => Boolean(query.trim() || gender || category || color),
    [query, gender, category, color],
  )

  function clearForm() {
    setQuery('')
    setGender('')
    setCategory('')
    setColor('')
    setError('')
  }

  async function handleSearch() {
    if (!hasSearchInput) {
      setError('Enter a fashion query or choose at least one filter.')
      return
    }

    setLoading(true)
    setError('')

    try {
      // Small delay so the loading state is visible in the UI/report screenshots.
      await new Promise((resolve) => setTimeout(resolve, 450))

      const results = searchTextDemo({
        query,
        gender,
        category,
        color,
        topK: 12,
      })

      navigate('/results', {
        state: {
          searchType: 'text-demo',
          query: query.trim(),
          filters: {
            gender,
            category,
            color,
          },
          results,
        },
      })
    } catch {
      setError('Text-search preview failed. Please try again.')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="search-page">
      <section className="search-intro">
        <p className="eyebrow">FASHION TEXT SEARCH</p>
        <h1>DESCRIBE YOUR STYLE</h1>
        <p>
          Search with fashion words, then narrow the preview with Dataset 2 metadata filters.
        </p>
      </section>

      <section className="text-search-card">
        <label htmlFor="query">FASHION QUERY</label>

        <div className="query-input-wrap">
          <span aria-hidden="true">⌕</span>

          <input
            id="query"
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            onKeyDown={(event) => {
              if (event.key === 'Enter' && !loading) {
                handleSearch()
              }
            }}
            placeholder="e.g. black shirt, white dress, red shoes..."
            disabled={loading}
          />
        </div>

        <div className="static-filter-grid">
          <label>
            Gender
            <select
              value={gender}
              onChange={(event) => setGender(event.target.value)}
              disabled={loading}
            >
              <option value="">All genders</option>
              {genderOptions.map((item) => (
                <option value={item} key={item}>
                  {item}
                </option>
              ))}
            </select>
          </label>

          <label>
            Category
            <select
              value={category}
              onChange={(event) => setCategory(event.target.value)}
              disabled={loading}
            >
              <option value="">All categories</option>
              {categoryOptions.map((item) => (
                <option value={item} key={item}>
                  {item}
                </option>
              ))}
            </select>
          </label>

          <label>
            Color
            <select
              value={color}
              onChange={(event) => setColor(event.target.value)}
              disabled={loading}
            >
              <option value="">All colors</option>
              {colorOptions.map((item) => (
                <option value={item} key={item}>
                  {item}
                </option>
              ))}
            </select>
          </label>
        </div>

        <div className="text-filter-summary">
          <span>TEXT</span>
          <strong>{query.trim() || 'Any text'}</strong>
          <span>GENDER</span>
          <strong>{gender || 'All'}</strong>
          <span>CATEGORY</span>
          <strong>{category || 'All'}</strong>
          <span>COLOR</span>
          <strong>{color || 'All'}</strong>
        </div>

        {error && (
          <div className="search-status search-status-error" role="alert">
            <div>
              <strong>SEARCH ERROR</strong>
              <span>{error}</span>
            </div>
          </div>
        )}

        {loading && (
          <div className="search-status search-status-loading" role="status">
            <span className="loading-spinner" aria-hidden="true" />

            <div>
              <strong>SEARCHING...</strong>
              <span>Applying the text query and metadata filters.</span>
            </div>
          </div>
        )}

        <div className="form-actions">
          <button
            type="button"
            className="secondary-btn"
            onClick={clearForm}
            disabled={loading}
          >
            CLEAR
          </button>

          <button
            type="button"
            className="primary-btn"
            onClick={handleSearch}
            disabled={loading || !hasSearchInput}
          >
            {loading ? 'SEARCHING...' : 'DISCOVER'}
          </button>
        </div>
      </section>
    </div>
  )
}
