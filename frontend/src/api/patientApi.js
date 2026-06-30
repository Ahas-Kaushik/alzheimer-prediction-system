import client from './axiosClient'

export const createPatient = (data) => client.post('/patients', data).then((r) => r.data)
export const listPatients = () => client.get('/patients').then((r) => r.data)
export const getPatient = (id) => client.get(`/patients/${id}`).then((r) => r.data)
export const updatePatient = (id, data) => client.put(`/patients/${id}`, data).then((r) => r.data)
