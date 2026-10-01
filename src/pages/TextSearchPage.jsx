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

function matchesQuery(product, tokens) {
  if (tokens.length === 0) {
    return true
  }

  const searchable = normalize([
    product.gender,
    product.category,
    product.color,
    product.usage,
    product.master_category,
    product.sub_category,
  ].join(' '))

  // All query words must appear somewhere in the real product metadata.
  return tokens.every((token) => searchable.includes(token))
}

function getTextMatchScore(product, tokens) {
  if (tokens.length === 0) {
    return 1
  }

  const searchable = normalize([
    product.gender,
    product.category,
    product.color,
    product.usage,
    product.master_category,
    product.sub_category,
  ].join(' '))

  const matched = tokens.filter((token) => searchable.includes(token)).length
  return matched / tokens.length
}

function searchTextDemo({ query, gender, category, color }) {
  const tokens = tokenize(query)

  return textSearchDemoCatalog
    .filter((product) => !gender || product.gender === gender)
    .filter((product) => !category || product.category === category)
    .filter((product) => !color || product.color === color)
    .filter((product) => matchesQuery(product, tokens))
    .map((product) => ({
      ...product,
      text_match_score: getTextMatchScore(product, tokens),
    }))
    .sort((a, b) => {
      if (b.text_match_score !== a.text_match_score) {
        return b.text_match_score - a.text_match_score
      }

      return String(a.product_id).localeCompare(String(b.product_id), undefined, {
        numeric: true,
      })
    })
}

export default function TextSearchPage() {
  const navigate = useNavigate()

  const [query, setQuery] = useState('black shirt')
  const [gender, setGender] = useState('Men')
  const [category, setCategory] = useState('Shirts')
  const [color, setColor] = useState('Black')
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
      await new Promise((resolve) => setTimeout(resolve, 350))

      const results = searchTextDemo({
        query,
        gender,
        category,
        color,
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
          Search with words and filters.
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
