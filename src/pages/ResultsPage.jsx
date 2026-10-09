import { useEffect, useMemo, useState } from 'react'
import { useLocation, useNavigate } from 'react-router-dom'
import ProductCard from '../components/ProductCard'
import { textSearchDemoCatalog } from '../data/textSearchDemoCatalog'

const ITEMS_PER_PAGE = 8
const RECOMMENDATION_LIMIT = 8

const catalogById = new Map(
  textSearchDemoCatalog.map((product) => [String(product.product_id), product]),
)

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

function normalize(value) {
  return String(value ?? '').trim().toLowerCase()
}

function tokenize(value) {
  return normalize(value)
    .split(/\s+/)
    .map((token) => token.trim())
    .filter(Boolean)
}

function getRecommendationScore(candidate, context) {
  let score = 0

  if (context.filters.gender && candidate.gender === context.filters.gender) {
    score += 8
  }

  if (context.filters.category && candidate.category === context.filters.category) {
    score += 10
  }

  if (context.filters.color && candidate.color === context.filters.color) {
    score += 7
  }

  for (const seed of context.seedProducts) {
    if (candidate.category && candidate.category === seed.category) score += 8
    if (candidate.sub_category && candidate.sub_category === seed.sub_category) score += 6
    if (candidate.master_category && candidate.master_category === seed.master_category) score += 4
    if (candidate.gender && candidate.gender === seed.gender) score += 3
    if (candidate.color && candidate.color === seed.color) score += 2
    if (candidate.usage && candidate.usage === seed.usage) score += 1
  }

  if (context.queryTokens.length > 0) {
    const searchable = normalize([
      candidate.gender,
      candidate.category,
      candidate.color,
      candidate.usage,
      candidate.master_category,
      candidate.sub_category,
    ].join(' '))

    for (const token of context.queryTokens) {
      if (searchable.includes(token)) {
        score += 2
      }
    }
  }

  return score
}

function buildRecommendations({
  currentProducts,
  query,
  filters,
}) {
  if (!Array.isArray(currentProducts) || currentProducts.length === 0) {
    return []
  }

  const currentIds = new Set(
    currentProducts
      .map((product) => product.product_id ?? product.id)
      .filter((id) => id !== undefined && id !== null)
      .map(String),
  )

  const seedProducts = currentProducts
    .slice(0, 8)
    .map((product) => {
      const id = product.product_id ?? product.id

      if (id === undefined || id === null) {
        return product
      }

      return catalogById.get(String(id)) ?? product
    })
    .filter(Boolean)

  const context = {
    filters,
    seedProducts,
    queryTokens: tokenize(query),
  }

  return textSearchDemoCatalog
    .filter((candidate) => !currentIds.has(String(candidate.product_id)))
    .map((candidate) => ({
      candidate,
      score: getRecommendationScore(candidate, context),
    }))
    .filter((item) => item.score > 0)
    .sort((a, b) => {
      if (b.score !== a.score) {
        return b.score - a.score
      }

      return String(a.candidate.product_id).localeCompare(
        String(b.candidate.product_id),
        undefined,
        { numeric: true },
      )
    })
    .slice(0, RECOMMENDATION_LIMIT)
    .map(({ candidate }) => ({
      ...candidate,
      match_type: 'metadata',
    }))
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

  const recommendationProducts = useMemo(
    () => hasSearchResults
      ? buildRecommendations({
          currentProducts: products,
          query,
          filters,
        })
      : [],
    [
      hasSearchResults,
      products,
      query,
      filters.gender,
      filters.category,
      filters.color,
    ],
  )

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

      {hasSearchResults && recommendationProducts.length > 0 && (
        <section className="related-section" aria-labelledby="related-title">
          <div className="related-heading">
            <div>
              <h2 id="related-title">YOU MAY ALSO LIKE</h2>
            </div>

            <span className="related-count">
              {recommendationProducts.length} SUGGESTIONS
            </span>
          </div>

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
