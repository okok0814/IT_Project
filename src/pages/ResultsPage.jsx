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

  const hasApiResults = Array.isArray(apiResults)
  const products = hasApiResults ? apiResults : mockProducts
  const count = products.length

  const heading =
    searchType === 'image'
      ? 'IMAGE SEARCH RESULTS'
      : query
        ? `Results for “${query}”`
        : 'CURATED RESULTS'

  return (
    <div className="results-page">
      <section className="mini-hero">
        <div className="mini-hero-copy">
          <p className="eyebrow">
            {searchType === 'image' ? 'VISUAL MATCHES' : 'MATCHED PIECES'}
          </p>

          <h1>{heading}</h1>

          {searchType === 'image' && uploadedImageName && (
            <p>
              Results returned for <strong>{uploadedImageName}</strong>.
            </p>
          )}
        </div>

        <span className="result-count">
          {count} {count === 1 ? 'ITEM' : 'ITEMS'} FOUND
        </span>
      </section>

      {hasApiResults && count === 0 ? (
        <section className="results-empty">
          <p className="eyebrow">NO MATCHES FOUND</p>

          <h2>No products were returned by the image search.</h2>

          <p>Try another image or use a clearer product photo.</p>

          <button
            type="button"
            className="primary-btn"
            onClick={() => navigate('/search/image')}
          >
            SEARCH ANOTHER IMAGE
          </button>
        </section>
      ) : (
        <div className="results-layout">
          <FilterSidebar />

          <section className="results-content">
            <div className="results-heading">
              <h2>
                MATCHED PIECES <span>{count} ITEMS FOUND</span>
              </h2>

              <p>
                Sorted by: <strong>Visual Similarity %</strong>
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
    </div>
  )
}
