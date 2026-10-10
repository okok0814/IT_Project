import { useEffect, useMemo, useState } from 'react'
import { useLocation, useNavigate } from 'react-router-dom'
import ProductCard from '../components/ProductCard'
import { getRelatedProducts } from '../api/fashionApi'
import { textSearchDemoCatalog } from '../data/textSearchDemoCatalog'

const ITEMS_PER_PAGE = 8
const RECOMMENDATION_LIMIT = 8

function buildPageItems(currentPage, totalPages) {
  if (totalPages <= 10) {
    return Array.from({ length: totalPages }, (_, index) => index + 1)
  }

  const maxVisibleNumbers = 9
  let start = Math.max(1, currentPage - 4)
  let end = Math.min(totalPages, start + maxVisibleNumbers - 1)

  if (end - start + 1 < maxVisibleNumbers) {
    start = Math.max(1, end - maxVisibleNumbers + 1)
  }

  const pages = []

  if (start > 1) {
    pages.push(1)

    if (start > 2) {
      pages.push('left-ellipsis')
    }
  }

  for (let page = start; page <= end; page += 1) {
    if (!pages.includes(page)) {
      pages.push(page)
    }
  }

  if (end < totalPages) {
    if (end < totalPages - 1) {
      pages.push('right-ellipsis')
    }

    pages.push(totalPages)
  }

  return pages
}

export default function ResultsPage() {
  const location = useLocation()
  const navigate = useNavigate()

  const query = location.state?.query ?? ''
  const apiResults = location.state?.results
  const searchType = location.state?.searchType
  const uploadedImageName = location.state?.uploadedImageName
  const filters = location.state?.filters ?? {}

  const hasSearchResults = Array.isArray(apiResults)

  // Direct /results view also uses the full real Dataset 2 catalog.
  // No mock products are used.
  const products = hasSearchResults ? apiResults : textSearchDemoCatalog
  const count = products.length

  const isImageSearch = searchType === 'image'
  const isTextSearch = searchType === 'text'
  const isCatalogView = !hasSearchResults

  const [currentPage, setCurrentPage] = useState(1)

  const totalPages = Math.max(1, Math.ceil(count / ITEMS_PER_PAGE))

  useEffect(() => {
    setCurrentPage(1)
  }, [query, searchType, filters.gender, filters.category, filters.color, count])

  useEffect(() => {
    if (currentPage > totalPages) {
      setCurrentPage(totalPages)
    }
  }, [currentPage, totalPages])

  const paginatedProducts = useMemo(() => {
    const start = (currentPage - 1) * ITEMS_PER_PAGE
    const end = start + ITEMS_PER_PAGE

    return products.slice(start, end)
  }, [products, currentPage])

  const pageItems = useMemo(
    () => buildPageItems(currentPage, totalPages),
    [currentPage, totalPages],
  )

  const [selectedProductId, setSelectedProductId] = useState('')
  const [retryRelated, setRetryRelated] = useState(0)
  const [related, setRelated] = useState({ sourceId: '', status: 'idle', products: [], error: '' })
  const sourceProductId = hasSearchResults && products.length
    ? (products.some(product => product.product_id === selectedProductId)
      ? selectedProductId : products[0].product_id)
    : ''

  useEffect(() => {
    if (!sourceProductId) return
    const controller = new AbortController()
    let active = true
    const timeout = setTimeout(() => controller.abort(), 120000)
    setRelated({ sourceId: sourceProductId, status: 'loading', products: [], error: '' })
    getRelatedProducts(sourceProductId, RECOMMENDATION_LIMIT, { signal: controller.signal })
      .then(products => {
        if (active) setRelated({ sourceId: sourceProductId, status: 'ready', products, error: '' })
      })
      .catch(error => {
        if (active) setRelated({ sourceId: sourceProductId, status: 'error', products: [],
          error: error.name === 'AbortError' ? 'Recommendations timed out. Please try again.'
            : error instanceof TypeError ? 'Cannot reach the recommendation server.' : error.message })
      })
      .finally(() => clearTimeout(timeout))
    return () => {
      active = false
      clearTimeout(timeout)
      controller.abort()
    }
  }, [sourceProductId, retryRelated])

  const relatedStatus = related.sourceId === sourceProductId ? related.status : 'loading'
  const recommendationProducts = relatedStatus === 'ready' ? related.products : []

  const heading = isImageSearch
    ? 'IMAGE SEARCH RESULTS'
    : isTextSearch && query
      ? `Results for “${query}”`
      : isTextSearch
        ? 'TEXT SEARCH RESULTS'
        : 'DATASET 2 CATALOG'

  const appliedFilters = [
    filters.gender && { label: 'Gender', value: filters.gender },
    filters.category && { label: 'Category', value: filters.category },
    filters.color && { label: 'Color', value: filters.color },
  ].filter(Boolean)

  const retryPath = isImageSearch ? '/search/image' : '/search/text'

  function goToPage(page) {
    const safePage = Math.min(Math.max(page, 1), totalPages)

    setCurrentPage(safePage)

    window.scrollTo({
      top: 0,
      behavior: 'smooth',
    })
  }

  return (
    <div className="results-page">
      <section className="mini-hero">
        <div className="mini-hero-copy">
          <p className="eyebrow">
            {isImageSearch
              ? 'VISUAL MATCHES'
              : isTextSearch
                ? 'TEXT MATCHES'
                : 'REAL DATASET 2 PRODUCTS'}
          </p>

          <h1>{heading}</h1>

          {isImageSearch && uploadedImageName && (
            <p>
              Results returned for <strong>{uploadedImageName}</strong>.
            </p>
          )}

          {isCatalogView && (
            <p>
              Browsing the full real Dataset 2 metadata catalog.
            </p>
          )}

          {isTextSearch && appliedFilters.length > 0 && (
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
        <>
          <section className="results-content">
            <div className="results-heading">
              <h2>
                {isCatalogView ? 'DATASET 2 PRODUCTS' : 'MATCHED PIECES'}{' '}
                <span>{count} ITEMS FOUND</span>
              </h2>

              <p>
                {isCatalogView ? (
                  <>
                    Source: <strong>real Dataset 2 metadata</strong>
                  </>
                ) : (
                  <>
                    Sorted by:{' '}
                    <strong>
                      {isImageSearch
                        ? 'Cosine similarity'
                        : isTextSearch
                          ? (query ? 'Cosine similarity' : 'Product ID')
                          : 'Product ID'}
                    </strong>
                  </>
                )}
              </p>
            </div>

            <div className="product-grid">
              {paginatedProducts.map((product, index) => (
                <ProductCard
                  key={product.product_id ?? product.id ?? `${currentPage}-${index}`}
                  product={product}
                />
              ))}
            </div>
          </section>

          {count > ITEMS_PER_PAGE && (
            <nav className="pagination-wrap" aria-label="Results pagination">
              <div className="pagination-summary">
                Page {currentPage} of {totalPages}
              </div>

              <div className="pagination">
                <button
                  type="button"
                  className="pagination-btn pagination-arrow"
                  onClick={() => goToPage(currentPage - 1)}
                  disabled={currentPage === 1}
                  aria-label="Previous page"
                >
                  &lt;
                </button>

                {pageItems.map((item, index) => {
                  if (typeof item === 'string') {
                    return (
                      <span
                        className="pagination-ellipsis"
                        key={`${item}-${index}`}
                        aria-hidden="true"
                      >
                        …
                      </span>
                    )
                  }

                  return (
                    <button
                      type="button"
                      className={`pagination-btn ${currentPage === item ? 'pagination-active' : ''}`}
                      onClick={() => goToPage(item)}
                      aria-current={currentPage === item ? 'page' : undefined}
                      key={item}
                    >
                      {item}
                    </button>
                  )
                })}

                <button
                  type="button"
                  className="pagination-btn pagination-arrow"
                  onClick={() => goToPage(currentPage + 1)}
                  disabled={currentPage === totalPages}
                  aria-label="Next page"
                >
                  &gt;
                </button>
              </div>
            </nav>
          )}
        </>
      )}

      {sourceProductId && (
        <section className="related-section" aria-labelledby="related-title">
          <div className="related-heading">
            <div>
              <h2 id="related-title">YOU MAY ALSO LIKE</h2>
              <p className="related-description">Explore pieces from complementary categories to pair with your chosen item.</p>
            </div>

            <span className="related-count">
              {relatedStatus === 'loading' ? 'LOADING...' : `${recommendationProducts.length} SUGGESTIONS`}
            </span>
          </div>

          <div className="related-source-control">
            <label htmlFor="related-source">Pair with</label>
            <select id="related-source" value={sourceProductId}
              onChange={event => setSelectedProductId(event.target.value)}>
              {products.map(product => (
                <option key={product.product_id} value={product.product_id}>
                  {product.name || `Product ${product.product_id}`} ({product.product_id})
                </option>
              ))}
            </select>
          </div>
          {relatedStatus === 'loading' && <p role="status">Finding complementary products...</p>}
          {relatedStatus === 'error' && (
            <div role="alert" className="search-status search-status-error">
              <span>{related.error}</span>
              <button type="button" className="secondary-btn" onClick={() => setRetryRelated(value => value + 1)}>RETRY RECOMMENDATIONS</button>
            </div>
          )}
          {relatedStatus === 'ready' && !recommendationProducts.length && (
            <p role="status">No complementary products are available for this item yet. Try another item.</p>
          )}
          <div className="related-products-grid">
            {recommendationProducts.map((product) => (
              <ProductCard
                key={`related-${product.product_id}`}
                product={product}
              />
            ))}
          </div>
        </section>
      )}
    </div>
  )
}
