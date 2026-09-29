import { buildBackendImageUrl } from '../api/fashionApi'
import { useState } from 'react'

export default function ProductCard({ product }) {
  const [failedImage, setFailedImage] = useState('')
  const isApiResult = typeof product.similarity_score === 'number'
  const similarityScore =
    typeof product.similarity_score === 'number'
      ? product.similarity_score
      : Number(product.score ?? 0) / 100

  const scorePercent = Math.max(
    0,
    Math.min(
      100,
      similarityScore <= 1
        ? Math.round(similarityScore * 100)
        : Math.round(similarityScore)
    )
  )

  const imageSrc = buildBackendImageUrl(product.image_url)

  return (
    <article className="product-card">
      <div className="product-art product-art-real">
        {imageSrc && failedImage !== imageSrc ? (
          <img
            className="product-image"
            src={imageSrc}
            alt={`Fashion product ${product.product_id ?? product.id ?? ''}`}
            loading="lazy"
            onError={() => setFailedImage(imageSrc)}
          />
        ) : (
          <>
            <div className="scanline" />
            <span className="product-symbol">{imageSrc ? 'Image unavailable' : product.symbol ?? '◫'}</span>
          </>
        )}
      </div>

      <div className="product-copy">
        <h3>
          {product.name ??
            `PRODUCT ${product.product_id ?? product.id ?? 'UNKNOWN'}`}
        </h3>

        <p className="product-id">
          ID: {product.product_id ?? product.id ?? 'N/A'}
        </p>

        {product.category && (
          <p className="product-meta">
            {product.gender ? `${product.gender} · ` : ''}
            {product.category}
            {product.color ? ` · ${product.color}` : ''}
          </p>
        )}

        <div className="match-row">
          <span>{isApiResult ? 'COSINE SIMILARITY' : 'VISUAL MATCH'}</span>

          <strong>{isApiResult ? similarityScore.toFixed(3) : `${scorePercent}%`}</strong>
        </div>

        <div className="meter">
          <span style={{ width: `${scorePercent}%` }} />
        </div>
      </div>
    </article>
  )
}
