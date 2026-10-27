import client from './axiosClient'

// GraphRAG can call an LLM, so allow a generous timeout.
export const askAI = (patientId, question) =>
  client.post('/rag/ask', { patient_id: patientId, question }, { timeout: 30000 }).then((r) => r.data)

export const explainPrediction = (patientId) =>
  client.get(`/rag/explain/${patientId}`, { timeout: 30000 }).then((r) => r.data)

export const ragStatus = () => client.get('/rag/status').then((r) => r.data)

export const getKnowledgeGraph = (cap = 3) =>
  client.get('/rag/graph', { params: { cap } }).then((r) => r.data)

export const getVectorProjection = () => client.get('/rag/vectors').then((r) => r.data)
