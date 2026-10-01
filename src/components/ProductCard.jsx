import { buildBackendImageUrl } from '../api/fashionApi'
import { useState } from 'react'

export default function ProductCard({ product }) {
  const [failedImage, setFailedImage] = useState('')

  const isImageApiResult = typeof product.similarity_score === 'number'
  const isTextPreview = typeof product.text_match_score === 'number'

  const rawScore = isImageApiResult
    ? product.similarity_score
    : isTextPreview
      ? product.text_match_score
      : Number(product.score ?? 0) / 100

  const scorePercent = Math.max(
    0,
    Math.min(
      100,
      rawScore <= 1
        ? Math.round(rawScore * 100)
        : Math.round(rawScore),
    ),
  )

  const imageSrc = buildBackendImageUrl(product.image_url)

  const scoreLabel = isImageApiResult
    ? 'COSINE SIMILARITY'
    : isTextPreview
      ? 'TEXT MATCH'
      : 'VISUAL MATCH'

  const scoreValue = isImageApiResult
    ? rawScore.toFixed(3)
    : `${scorePercent}%`

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
            <span className="product-symbol">
              {imageSrc ? 'Image unavailable' : product.symbol ?? '◫'}
            </span>
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

        {(product.gender || product.category || product.color) && (
          <p className="product-meta">
            {[product.gender, product.category, product.color]
              .filter(Boolean)
              .join(' · ')}
          </p>
        )}

        {product.usage && (
          <p className="product-usage">
            {product.usage}
          </p>
        )}

        <div className="match-row">
          <span>{scoreLabel}</span>
          <strong>{scoreValue}</strong>
        </div>

        <div className="meter">
          <span style={{ width: `${scorePercent}%` }} />
        </div>
      </div>
    </article>
  )
}
