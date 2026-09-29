import { useEffect, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { searchByImage } from '../api/fashionApi'

export default function ImageSearchPage() {
  const navigate = useNavigate()
  const inputRef = useRef(null)
  const requestRef = useRef(null)

  const [selectedFile, setSelectedFile] = useState(null)
  const [previewUrl, setPreviewUrl] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  useEffect(() => () => requestRef.current?.abort(), [])

  function handleFile(file) {
    if (loading) return
    setError('')

    if (!file) {
      return
    }

    if (!/\.(jpe?g|png|webp)$/i.test(file.name) ||
        (file.type && !['image/jpeg', 'image/png', 'image/webp'].includes(file.type))) {
      setError('Unsupported format. Choose a JPG, PNG or WEBP image.')
      return
    }
    if (file.size === 0 || file.size > 10 * 1024 * 1024) {
      setError(file.size === 0 ? 'This file is empty.' : 'Image is too large. Maximum size is 10 MiB.')
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
    event.target.value = ''
  }

  function handleDragOver(event) {
    event.preventDefault()
  }

  function handleDrop(event) {
    event.preventDefault()
    if (loading) return
    if (event.dataTransfer.files.length !== 1) {
      setError('Please upload one image at a time.')
      return
    }

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
    if (!selectedFile || requestRef.current) {
      return
    }

    setLoading(true)
    setError('')
    const controller = new AbortController()
    requestRef.current = controller
    const timeout = setTimeout(() => controller.abort(), 120000)

    try {
      const results = await searchByImage(selectedFile, 8, { signal: controller.signal })

      navigate('/results', {
        state: {
          searchType: 'image',
          uploadedImageName: selectedFile.name,
          results,
        },
      })
    } catch (searchError) {
      setError(
        searchError.name === 'AbortError'
          ? 'Search timed out. Please try again.'
          : searchError instanceof TypeError
          ? 'Cannot reach the search server. Please try again.'
          : searchError instanceof Error
          ? searchError.message
          : 'Unable to connect to the backend.'
      )
    } finally {
      clearTimeout(timeout)
      requestRef.current = null
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
                  ? 'Finding similar products...'
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
              JPG · PNG · WEBP · UP TO 10 MiB · 25 MEGAPIXELS
            </span>
          </>
        )}

        <input
          ref={inputRef}
          type="file"
          accept=".jpg,.jpeg,.png,.webp,image/jpeg,image/png,image/webp"
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
        <div className="search-status search-status-loading" role="status" aria-live="polite">
          <span className="loading-spinner" aria-hidden="true" />

          <div>
            <strong>SEARCHING...</strong>
            <span>Finding similar products. The first search may take longer.</span>
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
