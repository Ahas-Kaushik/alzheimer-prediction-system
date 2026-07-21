import client from './axiosClient'

export const startTest = (patientId) =>
  client.post('/cognitive/start', { patient_id: patientId }).then((r) => r.data)

export const submitResponse = (sessionId, correct, gazeMetrics = {}, extra = {}) =>
  client.post(`/cognitive/${sessionId}/result`, {
    correct,
    gaze_stability: gazeMetrics.gaze_stability ?? 1.0,
    saccade_count: gazeMetrics.saccade_count ?? 0,
    gaze_on_screen: gazeMetrics.gaze_on_screen ?? true,
    reaction_time_ms: extra.reaction_time_ms ?? null,
  }).then((r) => r.data)

export const getScores = (sessionId) =>
  client.get(`/cognitive/${sessionId}/scores`).then((r) => r.data)

export const getCognitiveHistory = (patientId) =>
  client.get(`/cognitive/history/${patientId}`).then((r) => r.data)
