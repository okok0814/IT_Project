import { useEffect, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'

export default function ImageSearchPage() {
  const navigate = useNavigate()
  const inputRef = useRef(null)

  const [selectedFile, setSelectedFile] = useState(null)
  const [previewUrl, setPreviewUrl] = useState('')

  function handleFile(file) {
    if (!file || !file.type.startsWith('image/')) return

    setSelectedFile(file)

    const newPreviewUrl = URL.createObjectURL(file)
    setPreviewUrl((oldPreviewUrl) => {
      if (oldPreviewUrl) {
        URL.revokeObjectURL(oldPreviewUrl)
      }

      return newPreviewUrl
    })
  }

  function chooseFile(event) {
    const file = event.target.files?.[0]
    handleFile(file)
  }

  function handleDragOver(event) {
    event.preventDefault()
  }

  function handleDrop(event) {
    event.preventDefault()

    const file = event.dataTransfer.files?.[0]
    handleFile(file)
  }

  function removeImage(event) {
    event.stopPropagation()

    setSelectedFile(null)

    setPreviewUrl((oldPreviewUrl) => {
      if (oldPreviewUrl) {
        URL.revokeObjectURL(oldPreviewUrl)
      }

      return ''
    })

    if (inputRef.current) {
      inputRef.current.value = ''
    }
  }

  useEffect(() => {
    return () => {
      if (previewUrl) {
        URL.revokeObjectURL(previewUrl)
      }
    }
  }, [previewUrl])

  return (
    <div className="search-page">
      <section className="search-intro">
        <p className="eyebrow">VISUAL FASHION SEARCH</p>
        <h1>FIND YOUR PERFECT MATCH</h1>
      </section>

      <section
        className={`upload-panel ${previewUrl ? 'has-preview' : ''}`}
        onClick={() => inputRef.current?.click()}
        onDragOver={handleDragOver}
        onDrop={handleDrop}
      >
        {previewUrl ? (
          <div className="image-preview-container">
            <img
              className="image-preview"
              src={previewUrl}
              alt="Selected fashion preview"
            />

            <button
              type="button"
              className="remove-preview"
              onClick={removeImage}
              aria-label="Remove selected image"
            >
              ×
            </button>

            <div className="preview-info">
              <span>IMAGE READY</span>

              <p title={selectedFile?.name}>
                {selectedFile?.name}
              </p>

              <small>Click the image to choose another one</small>
            </div>
          </div>
        ) : (
          <>
            <div className="upload-orb">＋</div>

            <h2>DROP YOUR IMAGE HERE</h2>

            <p>
              Upload a fashion image and discover pieces with similar
              shapes, textures and colors.
            </p>

            <span className="upload-format">
              JPG · PNG · WEBP
            </span>
          </>
        )}

        <input
          ref={inputRef}
          type="file"
          accept="image/*"
          onChange={chooseFile}
          hidden
        />
      </section>

      <div className="form-actions">
        <button
          className="secondary-btn"
          onClick={() => inputRef.current?.click()}
        >
          {previewUrl ? 'CHANGE IMAGE' : 'SELECT IMAGE'}
        </button>

        <button
          className="primary-btn"
          disabled={!selectedFile}
          onClick={() => navigate('/results')}
        >
          DISCOVER MATCHES
        </button>
      </div>
    </div>
  )
}