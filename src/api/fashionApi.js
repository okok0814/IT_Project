// Same-origin Vite proxy by default; an explicit backend URL works for deployment.
const API_BASE_URL = (import.meta.env.VITE_API_BASE_URL || '').replace(/\/+$/, '')

export async function searchByImage(file, topK = 8, { signal } = {}) {
  const formData = new FormData()

  formData.append('image', file)
  formData.append('top_k', String(topK))

  const response = await fetch(`${API_BASE_URL}/api/v1/search/image`, {
    method: 'POST',
    body: formData,
    signal,
  })

  let payload = null

  try {
    payload = await response.json()
  } catch {
    throw new Error('Backend returned an invalid response.')
  }

  if (!response.ok || payload?.success !== true) {
    throw new Error(
      payload?.error ||
        payload?.message ||
        `Image search failed with status ${response.status}.`
    )
  }

  if (!Array.isArray(payload.data) || payload.data.some(product =>
    typeof product?.product_id !== 'string' ||
    typeof product?.image_url !== 'string' || !product.image_url ||
    !Number.isFinite(product?.similarity_score) ||
    product.similarity_score < -1 || product.similarity_score > 1
  )) {
    throw new Error('Backend returned invalid search results. Please try again.')
  }

  return payload.data
}

export function buildBackendImageUrl(imageUrl) {
  if (!imageUrl) {
    return ''
  }

  if (
    imageUrl.startsWith('http://') ||
    imageUrl.startsWith('https://') ||
    imageUrl.startsWith('blob:') ||
    imageUrl.startsWith('data:')
  ) {
    return imageUrl
  }

  return `${API_BASE_URL}${imageUrl.startsWith('/') ? '' : '/'}${imageUrl}`
}
