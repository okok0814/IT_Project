import { useLocation } from 'react-router-dom'
import FilterSidebar from '../components/FilterSidebar'
import ProductCard from '../components/ProductCard'
import { mockProducts, relatedProducts } from '../data/mockProducts'

export default function ResultsPage() {
  const location = useLocation()
  const query = location.state?.query

  return (
    <div className="results-page">
      <section className="mini-hero">
        <div className="mini-hero-copy">
          <p className="eyebrow">MATCHED PIECES</p>
          <h1>{query ? `Results for “${query}”` : 'CURATED RESULTS'}</h1>
        </div>
        <span className="result-count">8 ITEMS FOUND</span>
      </section>

      <div className="results-layout">
        <FilterSidebar />
        <section className="results-content">
          <div className="results-heading">
            <h2>MATCHED PIECES <span>8 ITEMS FOUND</span></h2>
            <p>Sorted by: <strong>Visual Similarity %</strong></p>
          </div>
          <div className="product-grid">
            {mockProducts.map((product) => <ProductCard key={product.id} product={product} />)}
          </div>
        </section>
      </div>

      <section className="related-section">
        <div className="related-heading">
          <h2>✣ YOU MAY ALSO LIKE</h2>
          <span>← &nbsp; →</span>
        </div>
        <div className="related-grid">
          {relatedProducts.map((name, index) => (
            <article className="related-card" key={name}>
              <div className={`related-art related-${index + 1}`}><span>{['◫','●','✦','⌘','◒','∞'][index]}</span></div>
              <h3>{name}</h3>
              <p>${[120,45,55,35,149,75][index]}</p>
            </article>
          ))}
        </div>
      </section>
    </div>
  )
}
