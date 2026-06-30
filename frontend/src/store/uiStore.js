import { create } from 'zustand'

const useUIStore = create((set) => ({
  sidebarOpen: true,
  loading: false,
  modalOpen: false,
  modalContent: null,
  setSidebarOpen: (v) => set({ sidebarOpen: v }),
  setLoading: (v) => set({ loading: v }),
  openModal: (content) => set({ modalOpen: true, modalContent: content }),
  closeModal: () => set({ modalOpen: false, modalContent: null }),
}))

export default useUIStore
