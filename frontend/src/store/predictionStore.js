import { create } from 'zustand'

const usePredictionStore = create((set) => ({
  latestPrediction: null,
  predictionHistory: [],
  twinData: null,
  setLatestPrediction: (p) => set({ latestPrediction: p }),
  setPredictionHistory: (h) => set({ predictionHistory: h }),
  setTwinData: (t) => set({ twinData: t }),
  clearPrediction: () => set({ latestPrediction: null, twinData: null }),
  clearAll: () => set({ latestPrediction: null, predictionHistory: [], twinData: null }),
}))

export default usePredictionStore
