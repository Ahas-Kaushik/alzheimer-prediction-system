import client from './axiosClient'

export const runPrediction = (payload) =>
  client.post('/predictions/run', payload).then((r) => r.data)

export const getPredictions = (patientId) =>
  client.get(`/predictions/${patientId}`).then((r) => r.data)

export const getLatestPrediction = (patientId) =>
  client.get(`/predictions/${patientId}/latest`).then((r) => r.data)

export const getTwin = (patientId) =>
  client.get(`/twin/${patientId}`).then((r) => r.data)

export const getTwinHistory = (patientId) =>
  client.get(`/twin/${patientId}/history`).then((r) => r.data)
