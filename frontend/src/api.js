import axios from 'axios'
import { ElMessage } from 'element-plus'

const api = axios.create({ baseURL: '/', timeout: 60000 })

api.interceptors.response.use(
  (resp) => resp,
  (error) => {
    const detail = error.response?.data?.detail
    const message =
      typeof detail === 'string'
        ? detail
        : detail
          ? JSON.stringify(detail)
          : error.message || '请求失败'
    ElMessage.error(message)
    return Promise.reject(error)
  },
)

export async function downloadBlob(promise, filename) {
  const resp = await promise
  const blob = new Blob([resp.data], {
    type: resp.headers['content-type'] || 'application/octet-stream',
  })
  const url = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.download = filename
  document.body.appendChild(link)
  link.click()
  document.body.removeChild(link)
  URL.revokeObjectURL(url)
}

export default api
