import { buildBackendImageUrl } from '../api/fashionApi'

export default function ProductCard({ product }) {
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
        {imageSrc ? (
          <img
            className="product-image"
            src={imageSrc}
            alt={`Fashion product ${product.product_id ?? product.id ?? ''}`}
            loading="lazy"
          />
        ) : (
          <>
            <div className="scanline" />
            <span className="product-symbol">{product.symbol ?? '◫'}</span>
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
          <span>VISUAL MATCH</span>

          <strong>{scorePercent}%</strong>
        </div>

        <div className="meter">
          <span style={{ width: `${scorePercent}%` }} />
        </div>
      </div>
    </article>
  )
}
