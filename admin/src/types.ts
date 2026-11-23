export type Reservation = {
  reservationId: string
  date: string
  startTime: string
  endTime: string
  partySize: number
  customerName: string
  customerPhone?: string
  tableId?: string
  status: string
  source: string
  note?: string
  createdAt?: string
}

export type StoreHours = {
  dow: string
  label: string
  openTime: string
  closeTime: string
  lastStartTime?: string
  isClosed: boolean
}

export type StoreTable = {
  tableId: string
  label: string
  capacity: number
  aiBookable: boolean
  active: boolean
  sortOrder: number
}

export type StoreFaq = {
  faqId: string
  question: string
  answer: string
  tags: string[]
  enabled: boolean
  sortOrder: number
}

export type Store = {
  status: string
  tenantId: string
  name: string
  timezone: string
  standardDurationMin: number
  reservationSlotMin: number
  inboundId?: string
  transferPhoneNumber?: string
  hours: StoreHours[]
  tables: StoreTable[]
  faqs: StoreFaq[]
}

export type ListReservationsResponse = {
  status: string
  tenantId: string
  date: string
  count: number
  partyTotal: number
  reservations: Reservation[]
  reason?: string
}
