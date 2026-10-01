import { useLocation, useNavigate } from 'react-router-dom'
import FilterSidebar from '../components/FilterSidebar'
import ProductCard from '../components/ProductCard'
import { mockProducts, relatedProducts } from '../data/mockProducts'

export default function ResultsPage() {
  const location = useLocation()
  const navigate = useNavigate()

  const query = location.state?.query
  const apiResults = location.state?.results
  const searchType = location.state?.searchType
  const uploadedImageName = location.state?.uploadedImageName
  const filters = location.state?.filters ?? {}

  const hasSearchResults = Array.isArray(apiResults)
  const products = hasSearchResults ? apiResults : mockProducts
  const count = products.length

  const isImageSearch = searchType === 'image'
  const isTextPreview = searchType === 'text-demo'

  const heading = isImageSearch
    ? 'IMAGE SEARCH RESULTS'
    : query
      ? `Results for “${query}”`
      : isTextPreview
        ? 'TEXT SEARCH RESULTS'
        : 'CURATED RESULTS'

  const appliedFilters = [
    filters.gender && { label: 'Gender', value: filters.gender },
    filters.category && { label: 'Category', value: filters.category },
    filters.color && { label: 'Color', value: filters.color },
  ].filter(Boolean)

  const retryPath = isImageSearch ? '/search/image' : '/search/text'

  return (
    <div className="results-page">
      <section className="mini-hero">
        <div className="mini-hero-copy">
          <p className="eyebrow">
            {isImageSearch
              ? 'VISUAL MATCHES'
              : isTextPreview
                ? 'FILTER PREVIEW'
                : 'MATCHED PIECES'}
          </p>

          <h1>{heading}</h1>

          {isImageSearch && uploadedImageName && (
            <p>
              Results returned for <strong>{uploadedImageName}</strong>.
            </p>
          )}

          {isTextPreview && appliedFilters.length > 0 && (
            <div className="applied-filter-row" aria-label="Applied filters">
              <span className="applied-filter-label">APPLIED FILTERS</span>

              {appliedFilters.map((filter) => (
                <span className="applied-filter-chip" key={filter.label}>
                  {filter.label}: {filter.value}
                </span>
              ))}
            </div>
          )}
        </div>

        <span className="result-count">
          {count} {count === 1 ? 'ITEM' : 'ITEMS'} FOUND
        </span>
      </section>

      {hasSearchResults && count === 0 ? (
        <section className="results-empty" role="status">
          <p className="eyebrow">NO MATCHES FOUND</p>

          <h2>No products matched the current search.</h2>

          <p>Try changing the query or selecting fewer filters.</p>

          <button
            type="button"
            className="primary-btn"
            onClick={() => navigate(retryPath)}
          >
            TRY ANOTHER SEARCH
          </button>
        </section>
      ) : (
        <div className={`results-layout ${hasSearchResults ? 'image-results-layout' : ''}`}>
          {!hasSearchResults && <FilterSidebar />}

          <section className="results-content">
            <div className="results-heading">
              <h2>
                MATCHED PIECES <span>{count} ITEMS FOUND</span>
              </h2>

              <p>
                Sorted by:{' '}
                <strong>
                  {isImageSearch
                    ? 'Cosine similarity'
                    : isTextPreview
                      ? 'Frontend text match'
                      : 'Visual Similarity %'}
                </strong>
              </p>
            </div>

            <div className="product-grid">
              {products.map((product, index) => (
                <ProductCard
                  key={product.product_id ?? product.id ?? index}
                  product={product}
                />
              ))}
            </div>
          </section>
        </div>
      )}

      {!hasSearchResults && (
        <section className="related-section">
          <div className="related-heading">
            <h2>✣ YOU MAY ALSO LIKE</h2>
            <span>← &nbsp; →</span>
          </div>

          <div className="related-grid">
            {relatedProducts.map((name, index) => (
              <article className="related-card" key={name}>
                <div className={`related-art related-${index + 1}`}>
                  <span>{['◫', '●', '✦', '⌘', '◒', '∞'][index]}</span>
                </div>

                <h3>{name}</h3>
                <p>${[120, 45, 55, 35, 149, 75][index]}</p>
              </article>
            ))}
          </div>
        </section>
      )}
    </div>
  )
}
