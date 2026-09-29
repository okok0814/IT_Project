const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:5000'

export async function searchByImage(file, topK = 8) {
  const formData = new FormData()

  formData.append('image', file)
  formData.append('top_k', String(topK))

  const response = await fetch(`${API_BASE_URL}/search/image`, {
    method: 'POST',
    body: formData,
  })

  let payload = null

  try {
    payload = await response.json()
  } catch {
    throw new Error('Backend returned an invalid response.')
  }

  if (!response.ok || payload?.success === false) {
    throw new Error(
      payload?.error ||
        payload?.message ||
        `Image search failed with status ${response.status}.`
    )
  }

  return payload?.data ?? []
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
