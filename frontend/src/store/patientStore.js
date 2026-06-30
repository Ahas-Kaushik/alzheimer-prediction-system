import { create } from 'zustand'

const usePatientStore = create((set) => ({
  patients: [],
  currentPatient: null,
  setPatients: (patients) => set({ patients }),
  setCurrentPatient: (patient) => set({ currentPatient: patient }),
  clearCurrentPatient: () => set({ currentPatient: null }),
}))

export default usePatientStore
