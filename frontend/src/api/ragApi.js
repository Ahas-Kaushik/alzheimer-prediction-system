import client from './axiosClient'

// GraphRAG can call an LLM, so allow a generous timeout.
export const askAI = (patientId, question) =>
  client.post('/rag/ask', { patient_id: patientId, question }, { timeout: 120000 }).then((r) => r.data)

export const explainPrediction = (patientId) =>
  client.get(`/rag/explain/${patientId}`, { timeout: 120000 }).then((r) => r.data)

export const ragStatus = () => client.get('/rag/status').then((r) => r.data)
