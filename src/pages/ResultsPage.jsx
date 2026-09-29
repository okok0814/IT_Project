import { useLocation } from 'react-router-dom'
import FilterSidebar from '../components/FilterSidebar'
import ProductCard from '../components/ProductCard'
import { mockProducts, relatedProducts } from '../data/mockProducts'

export default function ResultsPage() {
  const location = useLocation()
  const query = location.state?.query
  const imageResults = location.state?.imageResults
  const isImageSearch = Array.isArray(imageResults)
  const products = isImageSearch ? imageResults.map(item => ({
    id: item.product_id,
    name: `Product ${item.product_id}`,
    imageUrl: item.image_url,
    similarity: item.similarity_score,
  })) : mockProducts
  const count = products.length

  return (
    <div className="results-page">
      <section className="mini-hero">
        <div className="mini-hero-copy">
          <p className="eyebrow">MATCHED PIECES</p>
          <h1>{isImageSearch ? 'IMAGE MATCHES' : query ? `Results for “${query}”` : 'CURATED RESULTS'}</h1>
          {isImageSearch && <p>Results for {location.state.filename}</p>}
        </div>
        <span className="result-count">{count} ITEMS FOUND</span>
      </section>

      <div className={`results-layout ${isImageSearch ? 'image-results-layout' : ''}`}>
        {!isImageSearch && <FilterSidebar />}
        <section className="results-content">
          <div className="results-heading">
            <h2>MATCHED PIECES <span>{count} ITEMS FOUND</span></h2>
            <p>Sorted by: <strong>{isImageSearch ? 'Cosine similarity' : 'Visual Similarity %'}</strong></p>
          </div>
          <div className="product-grid">
            {products.map((product) => <ProductCard key={product.id} product={product} />)}
          </div>
          {isImageSearch && count === 0 && <p role="status">No matching products found. Try another image.</p>}
        </section>
      </div>

      {!isImageSearch && <section className="related-section">
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
      </section>}
    </div>
  )
}
