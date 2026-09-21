export default function ProductCard({ product }) {
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
