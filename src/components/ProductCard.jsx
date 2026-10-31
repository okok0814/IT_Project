import { buildBackendImageUrl } from '../api/fashionApi'
import { useState } from 'react'

export default function ProductCard({ product }) {
  const [failedImage, setFailedImage] = useState('')

  const isImageApiResult = Number.isFinite(product.similarity_score)
  const isTextPreview = Number.isFinite(product.text_match_score)
  const isFilterOnly = product.match_type === 'metadata'

  const rawScore = isImageApiResult
    ? product.similarity_score
    : isTextPreview
      ? product.text_match_score
      : Number.isFinite(product.score)
        ? product.score / 100
        : null

  const hasScore = rawScore !== null

  const scorePercent = hasScore ? Math.max(
    0,
    Math.min(
      100,
      rawScore <= 1
        ? Math.round(rawScore * 100)
        : Math.round(rawScore),
    ),
  ) : 0

  const imageSrc = buildBackendImageUrl(product.image_url)

  const scoreLabel = isFilterOnly ? 'FILTER MATCH' : isImageApiResult
    ? 'COSINE SIMILARITY'
    : isTextPreview
      ? 'TEXT MATCH'
      : 'VISUAL MATCH'

  const scoreValue = isFilterOnly ? '—' : isImageApiResult
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

        {(isFilterOnly || hasScore) && <div className="match-row">
          <span>{scoreLabel}</span>
          <strong>{scoreValue}</strong>
        </div>}

        {!isFilterOnly && hasScore && <div className="meter">
          <span style={{ width: `${scorePercent}%` }} />
        </div>}
      </div>
    </article>
  )
}
