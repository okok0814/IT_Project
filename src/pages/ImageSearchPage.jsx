import { useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'

export default function ImageSearchPage() {
  const navigate = useNavigate()
  const inputRef = useRef(null)
  const [fileName, setFileName] = useState('')

  function chooseFile(event) {
    const file = event.target.files?.[0]
    if (file) setFileName(file.name)
  }

  return (
    <div className="search-page">
      <section className="search-intro">
        <p className="eyebrow">IMAGE-TO-IMAGE SEARCH</p>
        <h1>Upload an image</h1>
      </section>

      <section className="upload-panel" onClick={() => inputRef.current?.click()}>
        <div className="upload-orb">⇧</div>
        <h2>{fileName || 'DRAG & DROP IMAGE TO SEARCH'}</h2>
        <p>Our neural network will dissect visual curves, textures and color tones instantly.</p>
        <span className="upload-format">SUPPORTED: JPG, PNG, WEBP</span>
        <input ref={inputRef} type="file" accept="image/*" onChange={chooseFile} hidden />
      </section>

      <div className="form-actions">
        <button className="secondary-btn" onClick={() => inputRef.current?.click()}>CHOOSE IMAGE</button>
        <button className="primary-btn" onClick={() => navigate('/results')}>VIEW RESULTS</button>
      </div>
    </div>
  )
}
