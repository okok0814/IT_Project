const categories = ['Clothing', 'Sneakers', 'Bags', 'Eyewear', 'Accessory']
const colors = ['#9859ff', '#10b8d8', '#ff4d6d', '#d8e1ff', '#111111']
const sizes = ['XS', 'S', 'M', 'L', 'XL']

export default function FilterSidebar() {
  return (
    <aside className="filter-card">
      <div className="filter-title-row">
        <h3>FILTERS // 01</h3>
        <span>☷</span>
      </div>
      <div className="rule" />

      <section className="filter-section">
        <p className="eyebrow">CATEGORY</p>
        <div className="chip-wrap">
          {categories.map((item, i) => (
            <button key={item} className={`chip ${i === 0 || i === 2 || i === 3 || i === 4 ? 'chip-active' : ''}`}>{item}</button>
          ))}
        </div>
      </section>

      <section className="filter-section">
        <p className="eyebrow">CYBER COLORWAY</p>
        <div className="color-row">
          {colors.map((color) => <button key={color} className="color-dot" style={{ background: color }} aria-label={color} />)}
        </div>
      </section>

      <section className="filter-section">
        <p className="eyebrow">DIMENSION / SIZE</p>
        <div className="size-row">
          {sizes.map((size) => <button key={size} className={`size-btn ${size === 'M' || size === 'L' ? 'size-active' : ''}`}>{size}</button>)}
        </div>
      </section>

      <button className="reset-btn">RESET PARAMETERS</button>
    </aside>
  )
}
