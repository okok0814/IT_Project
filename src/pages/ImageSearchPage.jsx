import { useEffect, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { searchByImage } from '../api/fashionApi'

export default function ImageSearchPage() {
  const navigate = useNavigate()
  const inputRef = useRef(null)

  const [selectedFile, setSelectedFile] = useState(null)
  const [previewUrl, setPreviewUrl] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  function handleFile(file) {
    setError('')

    if (!file) {
      return
    }

    if (!file.type.startsWith('image/')) {
      setError('Please select a valid image file.')
      return
    }

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

    if (loading) {
      return
    }

    setSelectedFile(null)
    setError('')

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

  async function handleSearch() {
    if (!selectedFile || loading) {
      return
    }

    setLoading(true)
    setError('')

    try {
      const results = await searchByImage(selectedFile, 8)

      navigate('/results', {
        state: {
          searchType: 'image',
          uploadedImageName: selectedFile.name,
          results,
        },
      })
    } catch (searchError) {
      setError(
        searchError instanceof Error
          ? searchError.message
          : 'Unable to connect to the backend.'
      )
    } finally {
      setLoading(false)
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

        <p>
          Upload an image for visually similar products.
        </p>
      </section>

      <section
        className={`upload-panel ${previewUrl ? 'has-preview' : ''}`}
        onClick={() => {
          if (!loading) {
            inputRef.current?.click()
          }
        }}
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
              disabled={loading}
            >
              ×
            </button>

            <div className="preview-info">
              <span>IMAGE READY</span>

              <p title={selectedFile?.name}>
                {selectedFile?.name}
              </p>

              <small>
                {loading
                  ? 'Searching the backend...'
                  : 'Click the image to choose another one'}
              </small>
            </div>
          </div>
        ) : (
          <>
            <div className="upload-orb">＋</div>

            <h2>DROP YOUR IMAGE HERE</h2>

            <p>
              Upload a fashion image and discover pieces with similar shapes,
              textures and colors.
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
          disabled={loading}
          hidden
        />
      </section>

      {error && (
        <div className="search-status search-status-error" role="alert">
          <strong>SEARCH ERROR</strong>

          <span>{error}</span>
        </div>
      )}

      {loading && (
        <div className="search-status search-status-loading" aria-live="polite">
          <span className="loading-spinner" aria-hidden="true" />

          <div>
            <strong>SEARCHING...</strong>
          </div>
        </div>
      )}

      <div className="form-actions">
        <button
          className="secondary-btn"
          disabled={loading}
          onClick={() => inputRef.current?.click()}
        >
          {previewUrl ? 'CHANGE IMAGE' : 'SELECT IMAGE'}
        </button>

        <button
          className="primary-btn"
          disabled={!selectedFile || loading}
          onClick={handleSearch}
        >
          {loading ? 'SEARCHING...' : 'DISCOVER MATCHES'}
        </button>
      </div>
    </div>
  )
}
