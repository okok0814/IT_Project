import { useEffect, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'

export default function ImageSearchPage() {
  const navigate = useNavigate()
  const inputRef = useRef(null)
  const requestRef = useRef(null)

  const [selectedFile, setSelectedFile] = useState(null)
  const [previewUrl, setPreviewUrl] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

  useEffect(() => () => requestRef.current?.abort(), [])

  async function searchImage() {
    if (!selectedFile || requestRef.current) return
    const controller = new AbortController()
    requestRef.current = controller
    setLoading(true)
    setError('')
    const timeout = setTimeout(() => controller.abort(), 120000)
    try {
      const form = new FormData()
      form.append('image', selectedFile)
      form.append('top_k', '10')
      const response = await fetch('/api/v1/search/image', {
        method: 'POST', body: form, signal: controller.signal,
      })
      const body = await response.json().catch(() => null)
      if (!response.ok || !body?.success) {
        throw new Error(body?.error || 'Image search is unavailable. Please try again.')
      }
      if (!Array.isArray(body.data)) throw new Error('Invalid search response. Please try again.')
      navigate('/results', { state: { imageResults: body.data, filename: selectedFile.name } })
    } catch (err) {
      setError(err.name === 'AbortError'
        ? 'Search timed out. Please try again.'
        : err instanceof TypeError ? 'Cannot reach the search server. Please try again.' : err.message)
    } finally {
      clearTimeout(timeout)
      requestRef.current = null
      setLoading(false)
    }
  }

  function handleFile(file) {
    if (!file || loading) return
    setError('')
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

    const file = event.dataTransfer.files?.[0]
    handleFile(file)
  }

  function removeImage(event) {
    event.stopPropagation()
    if (loading) return
    setError('')

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
        onClick={() => !loading && inputRef.current?.click()}
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
              disabled={loading}
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
              JPG · PNG · WEBP · UP TO 10 MiB · 25 MEGAPIXELS
            </span>
          </>
        )}

        <input
          ref={inputRef}
          type="file"
          accept=".jpg,.jpeg,.png,.webp,image/jpeg,image/png,image/webp"
          disabled={loading}
          onChange={chooseFile}
          hidden
        />
      </section>

      {error && <p className="search-error" role="alert">{error}</p>}
      {loading && <p role="status">Finding similar products… The first search may take longer while the model loads.</p>}

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
          onClick={searchImage}
        >
          {loading ? 'SEARCHING…' : 'DISCOVER MATCHES'}
        </button>
      </div>
    </div>
  )
}
