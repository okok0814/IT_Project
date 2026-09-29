import { useState } from 'react'

export default function ProductCard({ product }) {
  const [imageFailed, setImageFailed] = useState(false)
  if (product.imageUrl) {
    return (
      <article className="product-card">
        <div className="product-art catalog-art">
          {imageFailed ? <span>Image unavailable</span> :
            <img src={product.imageUrl} alt={product.name} loading="lazy" onError={() => setImageFailed(true)} />}
        </div>
        <div className="product-copy">
          <h3>{product.name}</h3>
          <div className="match-row"><span>COSINE SIMILARITY</span><strong>{product.similarity.toFixed(3)}</strong></div>
        </div>
      </article>
    )
  }
  return (
    <article className="product-card">
      <div className={`product-art art-${product.art}`}>
        <div className="scanline" />
        <span className="product-symbol">{product.symbol}</span>
      </div>
      <div className="product-copy">
        <h3>{product.name}</h3>
        <p>{product.price}</p>
        <div className="match-row"><span>NEURAL MATCH</span><strong>{product.score}%</strong></div>
        <div className="meter"><span style={{ width: `${product.score}%` }} /></div>
      </div>
    </article>
  )
}
