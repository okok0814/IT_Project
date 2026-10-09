import { useEffect, useMemo, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  categoryOptions,
  colorOptions,
  genderOptions,
} from '../data/filterOptions'
import { searchByText } from '../api/fashionApi'

export default function TextSearchPage() {
  const navigate = useNavigate()
  const requestRef = useRef(null)
  useEffect(() => () => requestRef.current?.abort(), [])

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
    if (requestRef.current) return
    if (!hasSearchInput) {
      setError('Enter a fashion query or choose at least one filter.')
      return
    }

    setLoading(true)
    setError('')
    const controller = new AbortController()
    requestRef.current = controller
    const timeout = setTimeout(() => controller.abort(), 120000)

    try {
      const filters = { gender, category, color }
      const results = await searchByText(query, filters, 50, { signal: controller.signal })

      navigate('/results', {
        state: {
          searchType: 'text',
          query: query.trim(),
          filters: {
            gender,
            category,
            color,
          },
          results,
        },
      })
    } catch (error) {
      setError(error.name === 'AbortError'
        ? 'Search timed out. Please try again.'
        : error instanceof TypeError ? 'Cannot reach the search server. Please try again.' : error.message)
    } finally {
      clearTimeout(timeout)
      requestRef.current = null
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
            maxLength={1000}
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
          <label htmlFor="gender-filter">
            Gender
            <select
              id="gender-filter"
              aria-label="Gender"
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

          <label htmlFor="category-filter">
            Category
            <select
              id="category-filter"
              aria-label="Category"
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

          <label htmlFor="color-filter">
            Color
            <select
              id="color-filter"
              aria-label="Color"
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
