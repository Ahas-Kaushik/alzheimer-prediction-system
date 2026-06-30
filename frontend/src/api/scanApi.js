import client from './axiosClient'

export const uploadMRI = (patientId, file) => {
  const form = new FormData()
  form.append('patient_id', patientId)
  form.append('file', file)
  return client.post('/scans/upload', form, { headers: { 'Content-Type': 'multipart/form-data' } }).then((r) => r.data)
}

export const synthesizePET = (scanId, patientId) => {
  const form = new FormData()
  form.append('patient_id', patientId)
  return client.post(`/scans/${scanId}/synthesize`, form).then((r) => r.data)
}

export const getLatestScan = (patientId) =>
  client.get(`/scans/${patientId}/latest`).then((r) => r.data)

export const getAllScans = (patientId) =>
  client.get(`/scans/${patientId}/all`).then((r) => r.data)

export const deleteScan = (scanId, patientId) =>
  client.delete(`/scans/${scanId}?patient_id=${patientId}`).then((r) => r.data)
