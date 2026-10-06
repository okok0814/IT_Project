import { useEffect, useMemo, useState } from 'react'
import { useLocation, useNavigate } from 'react-router-dom'
import FilterSidebar from '../components/FilterSidebar'
import ProductCard from '../components/ProductCard'
import { mockProducts, relatedProducts } from '../data/mockProducts'

const ITEMS_PER_PAGE = 8

function buildPageItems(currentPage, totalPages) {
  if (totalPages <= 10) {
    return Array.from({ length: totalPages }, (_, index) => index + 1)
  }

  // Keep a compact pagination like:
  // < 1 2 3 4 5 6 7 8 9 ... >
  // and shift the visible window when the user moves further.
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

  const query = location.state?.query
  const apiResults = location.state?.results
  const searchType = location.state?.searchType
  const uploadedImageName = location.state?.uploadedImageName
  const filters = location.state?.filters ?? {}

  const hasSearchResults = Array.isArray(apiResults)
  const products = hasSearchResults ? apiResults : mockProducts
  const count = products.length

  const isImageSearch = searchType === 'image'
  const isTextSearch = searchType === 'text'

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

  const heading = isImageSearch
    ? 'IMAGE SEARCH RESULTS'
    : query
      ? `Results for “${query}”`
      : isTextSearch
        ? 'TEXT SEARCH RESULTS'
        : 'CURATED RESULTS'

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
                : 'MATCHED PIECES'}
          </p>

          <h1>{heading}</h1>

          {isImageSearch && uploadedImageName && (
            <p>
              Results returned for <strong>{uploadedImageName}</strong>.
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
                      : isTextSearch
                        ? (query ? 'Cosine similarity' : 'Product ID')
                        : 'Visual Similarity %'}
                  </strong>
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
          </div>

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
